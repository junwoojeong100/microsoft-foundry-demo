"""에이전트가 호출하는 '사내 시스템' 도구 (데모용 목업) — 함수 호출(Function calling) 시연에 쓰입니다.

실제 도입 시에는 이 함수들을 ERP·그룹웨어 API 호출로 바꾸거나, MCP 서버/OpenAPI 도구로 노출하면 됩니다.
"""
from __future__ import annotations

import itertools
from datetime import datetime
from typing import Any

from .i18n import pick

_EMPLOYEES_KO = {
    "C20231": {"employee_id": "C20231", "name": "김서연", "team": "영업1팀", "grade": "대리", "team_lead": "박준호 팀장", "division_head": "정태윤 영업본부장"},
    "C20587": {"employee_id": "C20587", "name": "이도현", "team": "영업2팀", "grade": "과장", "team_lead": "최민정 팀장", "division_head": "정태윤 영업본부장"},
    "H19877": {"employee_id": "H19877", "name": "한지우", "team": "IT운영팀", "grade": "책임", "team_lead": "오세훈 팀장", "division_head": "윤서아 IT본부장"},
}
_EMPLOYEES_EN = {
    "C20231": {"employee_id": "C20231", "name": "Seoyeon Kim", "team": "Sales Team 1", "grade": "Assistant Manager", "team_lead": "Junho Park (Team Lead)", "division_head": "Taeyun Jung (Sales Division Head)"},
    "C20587": {"employee_id": "C20587", "name": "Dohyun Lee", "team": "Sales Team 2", "grade": "Manager", "team_lead": "Minjeong Choi (Team Lead)", "division_head": "Taeyun Jung (Sales Division Head)"},
    "H19877": {"employee_id": "H19877", "name": "Jiwoo Han", "team": "IT Operations Team", "grade": "Senior Specialist", "team_lead": "Sehoon Oh (Team Lead)", "division_head": "Seoa Yoon (IT Division Head)"},
}
EMPLOYEES = pick(_EMPLOYEES_KO, _EMPLOYEES_EN)

_seq = itertools.count(41)


def approver_for(amount_krw: int, emp: dict[str, Any] | None) -> str:
    """FIN-002 의 승인 권한표(건당 금액 기준)."""
    lead = (emp or {}).get("team_lead", pick("팀장", "Team Lead"))
    head = (emp or {}).get("division_head", pick("본부장", "Division Head"))
    if amount_krw <= 300_000:
        return lead
    if amount_krw <= 1_000_000:
        return head
    if amount_krw <= 3_000_000:
        return pick("담당 임원", "Executive in charge")
    return pick("대표이사", "CEO")


def get_employee_profile(employee_id: str) -> dict[str, Any]:
    emp = EMPLOYEES.get(employee_id.strip().upper())
    if not emp:
        return {"found": False, "message": pick(f"사번 {employee_id} 를 찾을 수 없습니다.", f"Employee ID {employee_id} was not found.")}
    return {"found": True, **emp}


def submit_expense_report(**args: Any) -> dict[str, Any]:
    emp = EMPLOYEES.get(str(args.get("employee_id", "")).strip().upper())
    claimed = int(args.get("claimed_amount_krw", 0))
    today = datetime.now().strftime("%Y%m%d")
    return {
        "status": "SUBMITTED",
        "ticket": f"EXP-{today}-{next(_seq):04d}",
        "claimed_amount_krw": claimed,
        "approver": approver_for(claimed, emp),
        "payment_sla": pick("승인 완료 후 영업일 3일 이내 급여 계좌로 지급", "Paid to your payroll account within 3 business days after approval"),
        "system": pick("Contoso Pay (데모 목업)", "Contoso Pay (demo mock)"),
    }


REGISTRY = {
    "get_employee_profile": get_employee_profile,
    "submit_expense_report": submit_expense_report,
}


def execute(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": pick(f"알 수 없는 도구: {name}", f"Unknown tool: {name}")}
    try:
        return fn(**arguments)
    except Exception as exc:  # 도구 오류는 모델에게 돌려줘 스스로 복구하게 한다
        return {"error": f"{type(exc).__name__}: {exc}"}
