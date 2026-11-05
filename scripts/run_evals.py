#!/usr/bin/env python3
"""에이전트 품질 평가 — Foundry 내장 평가기(관련성·정답 일치도·근거 충실도)로 'Contoso Guide' 두 버전을 같은 질문으로 채점합니다.

    python scripts/run_evals.py                 # 질문 22개 전체 (약 4~6분)
    python scripts/run_evals.py --limit 8       # 앞의 8개만
    python scripts/run_evals.py --no-wait       # 실행만 걸고 바로 종료 (결과는 Foundry 포털 → 평가에서 확인)
    python scripts/run_evals.py --resume EVAL_ID  # 이미 만든 평가의 진행·결과만 이어서 확인 (네트워크가 끊겼을 때)

버전: v1 = 모델만 연결한 초기 프로토타입(baseline), v2 = 사규 PDF 벡터 스토어(file_search)를 연결한 버전.
결과는 터미널에 요약되고, 같은 내용이 Foundry 포털의 '평가' 화면(보고서 링크 포함)에 남습니다 — 관리자는 포털에서 봅니다.

사전 조건: azd up 완료(에이전트가 만들어져 있어야 함) + az login. 엔드포인트는 azd 환경 값(FOUNDRY_PROJECT_ENDPOINT)에서 읽습니다.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AzureAIAgentTargetParam,
    TargetCompletionEvalRunDataSource,
    TestingCriterionAzureAIEvaluator,
)
from azure.identity import DefaultAzureCredential
from openai.types.eval_create_params import DataSourceConfigCustom
from openai.types.evals.create_eval_completions_run_data_source_param import SourceFileContent, SourceFileContentContent

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATASET = ROOT / "src/web/seed/evals/dataset.jsonl"
AGENT = "contoso-guide"
JUDGE_DEPLOYMENT = "gpt-6.1-terra"

EVALUATORS = [
    ("relevance", "builtin.relevance", "관련성", {"query": "{{item.query}}", "response": "{{sample.output_text}}"}),
    ("similarity", "builtin.similarity", "정답 일치도", {"query": "{{item.query}}", "response": "{{sample.output_text}}", "ground_truth": "{{item.ground_truth}}"}),
    ("groundedness", "builtin.groundedness", "근거 충실도", {"query": "{{item.query}}", "response": "{{sample.output_items}}"}),
]


def project_endpoint() -> str:
    ep = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
    if not ep:
        out = subprocess.run(["azd", "env", "get-value", "FOUNDRY_PROJECT_ENDPOINT"], capture_output=True, text=True, cwd=ROOT)
        ep = out.stdout.strip().splitlines()[-1] if out.returncode == 0 and out.stdout.strip() else ""
    if not ep.startswith("https://"):
        sys.exit("FOUNDRY_PROJECT_ENDPOINT 를 찾을 수 없습니다. azd up 이후 같은 폴더에서 실행하거나 환경 변수로 지정하세요.")
    return ep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None, help="사용할 질문 수 (기본: 전체)")
    ap.add_argument("--agent", default=AGENT)
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--resume", metavar="EVAL_ID", help="이미 만들어진 평가에 이어서 결과를 확인")
    args = ap.parse_args()

    project = AIProjectClient(endpoint=project_endpoint(), credential=DefaultAzureCredential())
    oc = project.get_openai_client()

    versions = sorted(project.agents.list_versions(agent_name=args.agent, order="desc", limit=10), key=lambda v: int(v.version))
    if len(versions) < 2:
        sys.exit(f"{args.agent} 의 버전이 2개 이상 필요합니다 (앱이 처음 기동하면서 v1·v2 를 만듭니다).")
    label = {v.version: ("v%s · 모델만 연결(초기 프로토타입)" if (v.metadata or {}).get("role") == "baseline" else "v%s · 지식(file_search) 연결") % v.version for v in versions}

    if args.resume:
        ev = oc.evals.retrieve(args.resume)
        runs = {}
        for r in oc.evals.runs.list(eval_id=ev.id):
            runs[(r.name or "").rsplit(" v", 1)[-1]] = r
        print(f"평가 이어보기: {ev.id}  · 실행 {len(runs)}개")
    else:
        rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = rows[: args.limit] if args.limit else rows
        cfg = DataSourceConfigCustom(
            type="custom",
            item_schema={"type": "object", "properties": {"query": {"type": "string"}, "ground_truth": {"type": "string"}}, "required": ["query"]},
            include_sample_schema=True,
        )
        criteria = [
            TestingCriterionAzureAIEvaluator(type="azure_ai_evaluator", name=name, evaluator_name=ev_name, data_mapping=mapping,
                                             initialization_parameters={"deployment_name": JUDGE_DEPLOYMENT})
            for name, ev_name, _, mapping in EVALUATORS
        ]
        ev = oc.evals.create(name="Contoso Guide 품질 평가 (v1 vs v2)", data_source_config=cfg, testing_criteria=criteria)
        print(f"평가 생성: {ev.id}  · 질문 {len(rows)}개 · 심판 모델 {JUDGE_DEPLOYMENT}")
        runs = {}
        for v in versions:
            ds = TargetCompletionEvalRunDataSource(
                type="azure_ai_target_completions",
                source=SourceFileContent(type="file_content", content=[SourceFileContentContent(item={"query": r["query"], "ground_truth": r["ground_truth"]}) for r in rows]),
                input_messages={"type": "template", "template": [{"type": "message", "role": "user", "content": {"type": "input_text", "text": "{{item.query}}"}}]},
                target=AzureAIAgentTargetParam(type="azure_ai_agent", name=args.agent, version=str(v.version)),
            )
            run = oc.evals.runs.create(eval_id=ev.id, name=f"{args.agent} v{v.version}", data_source=ds)
            runs[v.version] = run
            print(f"  ▶ 실행 시작 {label[v.version]}  ({run.id})")
    if args.no_wait:
        print("결과는 Foundry 포털 → 평가 에서 확인하세요.")
        return

    t0 = time.time()
    while True:
        try:
            states = {ver: oc.evals.runs.retrieve(run_id=r.id, eval_id=ev.id) for ver, r in runs.items()}
        except Exception as exc:  # noqa: BLE001 — 일시적인 네트워크 오류는 다시 시도
            print(f"  … 일시 오류({type(exc).__name__}), 다시 시도합니다")
            time.sleep(10)
            continue
        print(f"  … {int(time.time() - t0)}초  " + " · ".join(f"v{ver}: {s.status}" for ver, s in states.items()))
        if all(s.status in ("completed", "failed", "canceled") for s in states.values()):
            break
        time.sleep(12)

    print("\n평가 결과 (1~5점 평균)")
    print(f"  {'':28}" + "".join(f"{n:>14}" for _, _, n, _ in EVALUATORS))
    for ver, s in states.items():
        sums: dict[str, list[float]] = {}
        for it in oc.evals.runs.output_items.list(run_id=runs[ver].id, eval_id=ev.id, limit=100):
            for r in (it.model_dump().get("results") or []):
                if isinstance(r.get("score"), (int, float)):
                    sums.setdefault(r["name"], []).append(float(r["score"]))
        cells = "".join(f"{(sum(sums[n]) / len(sums[n])):>14.2f}" if sums.get(n) else f"{'N/A':>14}" for n, _, _, _ in EVALUATORS)
        print(f"  {label[ver]:28}{cells}   [{s.status}]")
        if getattr(s, "report_url", None):
            print(f"     보고서: {s.report_url}")
    print("\n※ 근거 충실도는 참고한 문서가 있어야 정확히 측정됩니다 — v1 은 사규를 검색하지 않으므로 낮게 나오거나 N/A 일 수 있습니다.")


if __name__ == "__main__":
    main()
