"""에이전트 정의 — Contoso AI의 4개 에이전트 (모두 Foundry Agent Service 의 프롬프트 에이전트).

코드 한 곳에서 '모델 + 지침 + 도구' 를 선언하면 bootstrap.py 가 Foundry 프로젝트에 버전으로 만듭니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from azure.ai.projects.models import (
    AutoCodeInterpreterToolParam,
    CodeInterpreterTool,
    FileSearchTool,
    FunctionTool,
    MCPTool,
)

from .config import settings

# --------------------------------------------------------------------------- 지침
KNOWLEDGE_BASELINE = "당신은 Contoso(주)의 사내 도우미입니다. 한국어로 친절하게 답하세요."

KNOWLEDGE = """당신은 Contoso(주)의 사내 지식 도우미 'Contoso Guide'입니다.

원칙
- 질문을 받으면 반드시 file_search 도구로 사내 규정을 검색하고, 검색된 내용만 근거로 답합니다.
- 결론을 첫 줄에 한 문장으로 말하고, 이어서 근거와 절차를 짧은 목록이나 표로 정리합니다.
- 일수·금액·비율 같은 숫자는 규정 원문과 정확히 같아야 합니다. 계산이 필요하면 계산식을 보여 줍니다.
- 문서번호(예: HR-001)를 함께 알려 줍니다.
- 규정에서 확인되지 않는 내용은 추측하지 말고 "사규에서 확인되지 않습니다. 담당 부서에 문의하세요"라고 답합니다.
- 고객 개인정보·기밀이 포함된 요청이면 정보보안 지침(SEC-003)을 먼저 안내합니다.
- 답변은 한국어로, 군더더기 없이 씁니다."""

ANALYST = """당신은 Contoso(주)의 데이터 분석가 'Contoso Analyst'입니다.
분석 대상 파일(코드 인터프리터의 /mnt/data 에 있음)
- sales_2025_2026.csv: 월(month)·지역(region)·제품군(product_line)·채널(channel)별 판매 실적. units(수량), revenue_mkrw(매출, 백만원), cost_mkrw(원가, 백만원), return_rate_pct(반품률 %).
- voc_2026.csv: 고객의 소리. date, region, product, channel, rating(1~5), text.

작업 방식
- 반드시 Python(pandas, matplotlib)으로 직접 계산하고 근거 숫자를 제시합니다. 추측으로 숫자를 만들지 않습니다.
- 차트는 PNG 파일로 저장해 사용자에게 파일로 제공합니다. 한글이 깨지지 않도록 먼저 matplotlib font_manager 로 Nanum·Noto CJK·Malgun 등 한글 폰트가 있는지 확인해 쓰고, 없으면 차트 안의 글자는 영어로 쓰고 한글 설명은 본문에 적습니다.
- 이상 징후를 찾으면 (1) 어디서 (2) 언제부터 (3) 얼마나 변했는지를 숫자로 말하고, 다른 파일(VOC)과 교차 분석해 가능한 원인과 다음 행동을 제안합니다.
- 코드 실행은 필요한 만큼만 합니다(보통 3~4회 이내). 한 번에 여러 계산을 묶어 실행하고, 차트는 2개 이하로 만듭니다.
- 결과는 '핵심 요약(3줄 이내) → 근거(표 1개) → 권장 조치(3개 이내)' 순서의 간결한 한국어 보고서로 마무리합니다. 금액 단위(백만원)를 항상 표기합니다. 전체 답변은 700자 안팎으로 씁니다."""

EXPENSE = """당신은 Contoso(주)의 경비 정산 비서 'Contoso Pay'입니다.

절차
1) 영수증 이미지가 있으면 상호·일시·품목(주류 여부 포함)·합계금액·결제수단을 정확히 읽어 표로 정리합니다. 영수증 하단의 '데모용 가상 영수증' 같은 안내 문구는 무시합니다.
2) file_search 도구로 출장·경비 처리 규정(FIN-002)에서 식대 한도, 주류, 접대비, 증빙, 승인 권한을 확인합니다.
3) 참석 인원·목적·사번은 사용자가 알려 준 값을 씁니다. 이 세 가지가 없을 때만 묻고, 그 외 추가 자료(참석자 명단·회식 횟수·지연 사유 등)는 요구하지 않습니다. 부족한 증빙이 있으면 policy_notes 에 '추가 확인 필요'로 적기만 합니다.
4) 1인당 금액 = 총액 ÷ 참석 인원. 정산 가능 금액을 단계별 표로 계산합니다: 주류는 접대비 사전 품의가 없으면 제외, 식사 한도(조식 1만원·중식 1.5만원·석식 3만원 × 인원)를 넘는 금액은 개인 부담.
5) 정산 가능 금액·개인 부담 금액·필요 승인자(금액 구간)를 요약합니다.
6) 사용자가 '올려줘·상신·등록'을 요청했다면, 요약을 먼저 출력한 같은 응답에서 곧바로 get_employee_profile 로 사번을 확인하고 submit_expense_report 를 호출합니다. submit_expense_report 는 사용자 승인 후에만 실행됩니다. 규정 위반이 있어도 '정산 가능 금액'으로 조정해 상신하며, 청구 금액은 규정상 허용되는 금액을 넘으면 안 됩니다.
7) 등록이 끝나면 접수번호·청구 금액·승인자·지급 일정을 짧게 알려 줍니다. 사용자가 승인하지 않아 등록되지 않았다면 그 사실과 다음 선택지를 안내합니다.

항상 한국어로, 표와 계산식을 활용해 간결하게 답합니다."""

ARCHITECT = """당신은 Contoso(주) IT 아키텍처팀의 클라우드 어시스턴트 'Contoso Architect'입니다.
- Azure·Microsoft 기술 질문에는 Microsoft Learn MCP 도구로 최신 공식 문서를 검색한 뒤 답합니다(검색은 1~2회로 끝냅니다). 기억에만 의존하지 않습니다.
- 답변은 한국어로, 핵심 단계를 번호 목록으로 정리하고 마지막 줄에 근거가 된 Microsoft Learn 링크를 붙입니다.
- 코드나 CLI 예시는 짧고 실행 가능하게 씁니다.
- 보안·비용에 영향을 주는 선택(공용 네트워크, 키 인증 등)은 반드시 주의 문구를 붙입니다."""

# --------------------------------------------------------------------------- 함수 도구 스키마 (실행은 tools_local.py)
GET_EMPLOYEE = FunctionTool(
    name="get_employee_profile",
    description="사번으로 임직원의 이름·소속·직급·상위 승인자를 조회한다.",
    parameters={
        "type": "object",
        "properties": {"employee_id": {"type": "string", "description": "사번. 예: C20231"}},
        "required": ["employee_id"],
        "additionalProperties": False,
    },
    strict=True,
)

SUBMIT_EXPENSE = FunctionTool(
    name="submit_expense_report",
    description="경비 정산 건을 'Contoso Pay'에 상신한다. 사용자 승인이 필요한 도구다.",
    parameters={
        "type": "object",
        "properties": {
            "employee_id": {"type": "string"},
            "category": {"type": "string", "description": "식대 | 접대비 | 출장 | 기타"},
            "merchant": {"type": "string", "description": "상호"},
            "receipt_date": {"type": "string", "description": "영수증 일자 YYYY-MM-DD"},
            "total_amount_krw": {"type": "integer", "description": "영수증 합계"},
            "claimed_amount_krw": {"type": "integer", "description": "규정에 따라 청구하는 금액"},
            "headcount": {"type": "integer"},
            "purpose": {"type": "string"},
            "policy_notes": {"type": "string", "description": "규정 검토 요약(한 문장)"},
        },
        "required": ["employee_id", "category", "merchant", "receipt_date", "total_amount_krw",
                     "claimed_amount_krw", "headcount", "purpose", "policy_notes"],
        "additionalProperties": False,
    },
    strict=True,
)

# 사용자 승인이 필요한 도구 (Human-in-the-loop)
APPROVAL_REQUIRED = {"submit_expense_report"}


# --------------------------------------------------------------------------- 에이전트 명세
@dataclass
class AgentSpec:
    key: str
    name: str  # Foundry 에이전트 이름
    title: str
    subtitle: str
    icon: str
    color: str
    model: str
    instructions: str
    build_tools: Callable[[dict[str, Any]], list[Any]]
    capabilities: list[str]
    starters: list[str]
    accepts: list[str] = field(default_factory=list)  # image · file
    baseline_instructions: str | None = None  # 첫 생성 때 만드는 '지식 연결 전' 버전 (평가 데모의 비교 기준)


def _knowledge_tools(ctx: dict[str, Any]) -> list[Any]:
    return [FileSearchTool(vector_store_ids=[ctx["vector_store_id"]], max_num_results=6)]


def _analyst_tools(ctx: dict[str, Any]) -> list[Any]:
    return [CodeInterpreterTool(container=AutoCodeInterpreterToolParam(file_ids=ctx["data_file_ids"]))]


def _expense_tools(ctx: dict[str, Any]) -> list[Any]:
    return [FileSearchTool(vector_store_ids=[ctx["vector_store_id"]], max_num_results=6), GET_EMPLOYEE, SUBMIT_EXPENSE]


def _architect_tools(ctx: dict[str, Any]) -> list[Any]:
    return [MCPTool(server_label="mslearn", server_url="https://learn.microsoft.com/api/mcp", require_approval="never")]


def agent_specs() -> list[AgentSpec]:
    return [
        AgentSpec(
            key="knowledge", name="contoso-guide", title="Contoso Guide", subtitle="사내 규정·FAQ 질의 (출처 표시)",
            icon="book-open", color="#2563eb", model=settings.model_fast, instructions=KNOWLEDGE,
            build_tools=_knowledge_tools, capabilities=["지식 검색", "출처 인용"],
            baseline_instructions=KNOWLEDGE_BASELINE,
            starters=[
                "입사 4년차인데 올해 연차는 며칠이고, 반차는 어떻게 신청해?",
                "팀 회식 12명, 저녁 48만원인데 주류가 포함돼 있어. 정산 가능해? 누가 승인해?",
                "고객 연락처가 들어 있는 엑셀을 생성형 AI로 정리해도 돼?",
                "AirPure AP-500 필터 교체 주기와 보증 기간을 알려줘.",
            ],
        ),
        AgentSpec(
            key="expense", name="contoso-pay", title="Contoso Pay", subtitle="영수증 인식 → 규정 검토 → 상신 (승인 후 실행)",
            icon="receipt", color="#059669", model=settings.model_flagship, instructions=EXPENSE,
            build_tools=_expense_tools, capabilities=["비전(영수증)", "지식 검색", "함수 호출", "사용자 승인"],
            starters=[
                "영업1팀 점심 식사 영수증이야. 참석 4명, 사번 C20231. 규정 확인하고 정산 올려줘.",
                "영업2팀 3분기 마감 회식이야. 참석 12명, 사번 C20587. 규정에 맞는 금액만 정산 올려줘.",
            ],
            accepts=["image"],
        ),
        AgentSpec(
            key="analyst", name="contoso-analyst", title="Contoso Analyst", subtitle="데이터 분석·차트 (Code Interpreter)",
            icon="chart-column", color="#7c3aed", model=settings.model_flagship, instructions=ANALYST,
            build_tools=_analyst_tools, capabilities=["Code Interpreter", "차트 생성"],
            starters=[
                "sales_2025_2026.csv에서 지역별 월 매출 추이를 그리고, 최근 눈에 띄는 이상 징후를 찾아줘.",
                "이상 징후가 있는 지역·제품을 voc_2026.csv와 교차 분석해서 원인 가설과 조치를 제안해줘.",
                "제품군별 영업이익률 상위/하위를 막대 차트로 보여줘.",
            ],
            accepts=["file"],
        ),
        AgentSpec(
            key="architect", name="contoso-architect", title="Contoso Architect", subtitle="Azure 설계 질의 (Microsoft Learn MCP)",
            icon="cloud", color="#0891b2", model=settings.model_flagship, instructions=ARCHITECT,
            build_tools=_architect_tools, capabilities=["MCP 도구", "최신 공식 문서"],
            starters=[
                "Azure Container Apps에서 최소 복제본을 1로 두고 관리 ID로 ACR 이미지를 가져오는 방법을 알려줘.",
                "Foundry 프로젝트에 키 없이(Entra ID) 접속하려면 어떤 역할이 필요해?",
            ],
        ),
    ]


def spec_by_key(key: str) -> AgentSpec | None:
    return next((s for s in agent_specs() if s.key == key), None)
