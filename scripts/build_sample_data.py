#!/usr/bin/env python3
"""데모용 가상 데이터를 만듭니다 (모두 가상: Contoso 판매 실적, 고객 VOC, 영수증 이미지, 평가 데이터셋).

    python scripts/build_sample_data.py

결과(src/web/seed/):
  samples/sales_2025_2026.csv   월×지역×제품×채널 판매 실적 (부산·경남 로봇청소기에 이상 신호를 심어 둠)
  samples/voc_2026.csv          고객 VOC 700건 (같은 지역·제품에 '배터리' 불만이 늘어남)
  receipts/*.png                경비 정산 에이전트용 영수증 이미지 2장
  evals/dataset.jsonl           사규 질문/정답 22건 (평가 데모용)
"""
from __future__ import annotations

import csv
import json
import math
import pathlib
import random
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED = ROOT / "src/web/seed"
rng = random.Random(20261105)

# ----------------------------------------------------------------------------- 판매 실적
MONTHS = [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13) if not (y == 2026 and m > 10)]
REGIONS = {"서울": 1.35, "경기·인천": 1.25, "부산·경남": 0.9, "대구·경북": 0.62, "광주·전라": 0.5, "대전·충청": 0.58}
PRODUCTS = {
    "공기청정기": dict(base=420, price=0.52, margin=0.32, season={1: 1.15, 2: 1.2, 3: 1.35, 4: 1.3, 5: 1.0, 6: 0.8, 7: 0.7, 8: 0.7, 9: 0.9, 10: 1.05, 11: 1.25, 12: 1.3}),
    "에어프라이어": dict(base=300, price=0.18, margin=0.28, season={1: 1.0, 2: 0.9, 3: 0.85, 4: 0.85, 5: 0.9, 6: 0.9, 7: 0.85, 8: 0.9, 9: 1.0, 10: 1.15, 11: 1.4, 12: 1.5}),
    "로봇청소기": dict(base=210, price=0.89, margin=0.30, season={1: 0.95, 2: 0.9, 3: 1.0, 4: 1.0, 5: 1.05, 6: 1.1, 7: 1.0, 8: 0.95, 9: 1.0, 10: 1.1, 11: 1.35, 12: 1.3}),
    "스마트조명": dict(base=140, price=0.09, margin=0.4, season={m: 1.0 for m in range(1, 13)}),
}
CHANNELS = {"온라인": 0.52, "오프라인": 0.33, "B2B": 0.15}


def build_sales() -> list[dict]:
    rows = []
    for idx, month in enumerate(MONTHS):
        year, mon = map(int, month.split("-"))
        growth = 1 + 0.011 * idx
        for region, rw in REGIONS.items():
            for product, p in PRODUCTS.items():
                for channel, cw in CHANNELS.items():
                    units = p["base"] * rw * cw * p["season"][mon] * growth * rng.uniform(0.93, 1.07)
                    ret = rng.uniform(1.6, 3.1)
                    # 이상 신호: 2026-07 이후 부산·경남 로봇청소기 — 매출 급락 + 반품률 급등
                    if region == "부산·경남" and product == "로봇청소기" and month >= "2026-07":
                        k = {"2026-07": 0.78, "2026-08": 0.62, "2026-09": 0.55, "2026-10": 0.5}[month]
                        units *= k
                        ret = rng.uniform(9.5, 12) + (idx - MONTHS.index("2026-07")) * 1.6
                    # 긍정적 이상치: 2026-08 서울 에어프라이어 프로모션
                    if region == "서울" and product == "에어프라이어" and month == "2026-08" and channel == "온라인":
                        units *= 1.55
                    units = max(1, round(units))
                    revenue = round(units * p["price"], 1)  # 백만원
                    cost = round(revenue * (1 - p["margin"]) * rng.uniform(0.97, 1.03), 1)
                    rows.append(dict(month=month, region=region, product_line=product, channel=channel,
                                     units=units, revenue_mkrw=revenue, cost_mkrw=cost, return_rate_pct=round(ret, 1)))
    return rows


# ----------------------------------------------------------------------------- VOC
VOC = {
    "공기청정기": {
        "pos": ["공기가 확실히 맑아진 느낌이에요. 수면모드 소음도 거의 없어요.", "필터 교체 알림이 정확해서 관리하기 편합니다.", "앱으로 공기질을 볼 수 있어서 좋아요."],
        "neg": ["필터 가격이 조금 부담됩니다.", "와이파이 연결이 자주 끊겨요.", "작동할 때 소음이 생각보다 큽니다."],
    },
    "에어프라이어": {
        "pos": ["튀김이 바삭하고 세척이 쉬워요.", "앱 레시피가 다양해서 요리가 즐거워졌어요.", "6.5L라 4인 가족도 충분합니다."],
        "neg": ["코팅이 벗겨지는 것 같아요.", "예열할 때 냄새가 나요.", "바스켓이 약간 뻑뻑합니다."],
    },
    "로봇청소기": {
        "pos": ["장애물을 잘 피하고 청소 범위가 꼼꼼해요.", "앱으로 구역 지정이 편해요.", "물걸레 성능이 만족스럽습니다."],
        "neg": ["턱을 잘 못 넘어요.", "충전대 복귀가 가끔 실패해요.", "소음이 조금 큰 편이에요."],
        "battery": ["충전이 안 돼요. 충전대에 올려도 불이 안 들어옵니다.", "배터리가 10분도 안 가서 청소를 끝까지 못 합니다.", "충전 중에 전원이 자꾸 꺼져요. 배터리 문제 같아요.", "구매 두 달 만에 배터리가 방전됩니다. 교환 요청합니다.", "배터리 팽창이 의심돼서 사용을 멈췄어요. 불안합니다.", "A/S 접수했는데 배터리 재고가 없다고 2주째 대기 중입니다."],
    },
    "스마트조명": {
        "pos": ["설치가 간단하고 색감이 좋아요.", "음성 비서 연동이 매끄럽습니다."],
        "neg": ["가끔 앱과 연결이 끊겨요.", "밝기 조절 단계가 거칠어요."],
    },
}
OTHER_NEG = ["배송이 예정일보다 3일 늦었어요.", "고객센터 연결이 오래 걸렸습니다.", "A/S 방문 일정을 잡기가 어려웠어요.", "포장이 훼손되어 도착했습니다."]


def build_voc() -> list[dict]:
    rows = []
    start = date(2026, 1, 1)
    days = (date(2026, 10, 31) - start).days
    for _ in range(700):
        d = start + timedelta(days=rng.randint(0, days))
        region = rng.choices(list(REGIONS), weights=list(REGIONS.values()))[0]
        product = rng.choices(list(VOC), weights=[3, 2.5, 3, 1.2])[0]
        channel = rng.choices(list(CHANNELS), weights=list(CHANNELS.values()))[0]
        battery_issue = product == "로봇청소기" and region == "부산·경남" and d >= date(2026, 7, 1) and rng.random() < 0.7
        if battery_issue:
            text, rating = rng.choice(VOC["로봇청소기"]["battery"]), rng.choice([1, 1, 2])
        elif rng.random() < 0.62:
            text, rating = rng.choice(VOC[product]["pos"]), rng.choice([4, 5, 5])
        elif rng.random() < 0.75:
            text, rating = rng.choice(VOC[product]["neg"]), rng.choice([2, 3, 3])
        else:
            text, rating = rng.choice(OTHER_NEG), rng.choice([2, 3])
        rows.append(dict(date=d.isoformat(), region=region, product=product, channel=channel, rating=rating, text=text))
    # 이상 신호를 또렷하게: 부산·경남 로봇청소기의 7~10월 배터리 불만을 추가로 심는다
    for _ in range(70):
        d = date(2026, 7, 1) + timedelta(days=rng.randint(0, 122))
        rows.append(dict(date=d.isoformat(), region="부산·경남", product="로봇청소기", channel=rng.choices(list(CHANNELS), weights=list(CHANNELS.values()))[0],
                         rating=rng.choice([1, 1, 2]), text=rng.choice(VOC["로봇청소기"]["battery"])))
    rows.sort(key=lambda r: r["date"])
    return rows


# ----------------------------------------------------------------------------- 영수증
FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def receipt(path: pathlib.Path, title: str, biz: str, addr: str, when: str, items: list[tuple[str, int, int]], card: str, approve: str):
    W = 640
    f = lambda s, bold=False: ImageFont.truetype(FONT, s, index=(6 if bold else 0))  # noqa: E731
    lines = []
    total = sum(q * p for _, q, p in items)
    vat = round(total / 11)
    H = 520 + 38 * len(items) + 40
    im = Image.new("RGB", (W + 80, H + 80), (226, 229, 235))
    paper = Image.new("RGB", (W, H), (255, 255, 253))
    d = ImageDraw.Draw(paper)
    y = 34
    d.text((W // 2, y), title, font=f(34, True), fill=(20, 20, 20), anchor="mt"); y += 58
    for t in (f"사업자번호 {biz}   대표 김○○", addr, "TEL 000-0000-0000 (가상)"):
        d.text((W // 2, y), t, font=f(20), fill=(70, 70, 70), anchor="mt"); y += 30
    y += 10
    d.line((30, y, W - 30, y), fill=(120, 120, 120), width=2); y += 14
    d.text((30, y), f"일시  {when}", font=f(22), fill=(30, 30, 30)); y += 36
    d.line((30, y, W - 30, y), fill=(160, 160, 160), width=1); y += 12
    d.text((30, y), "품목", font=f(20, True), fill=(60, 60, 60))
    d.text((W - 260, y), "수량", font=f(20, True), fill=(60, 60, 60), anchor="rt")
    d.text((W - 150, y), "단가", font=f(20, True), fill=(60, 60, 60), anchor="rt")
    d.text((W - 30, y), "금액", font=f(20, True), fill=(60, 60, 60), anchor="rt"); y += 34
    for name, q, p in items:
        d.text((30, y), name, font=f(22), fill=(20, 20, 20))
        d.text((W - 260, y), f"{q}", font=f(22), fill=(20, 20, 20), anchor="rt")
        d.text((W - 150, y), f"{p:,}", font=f(22), fill=(20, 20, 20), anchor="rt")
        d.text((W - 30, y), f"{q * p:,}", font=f(22), fill=(20, 20, 20), anchor="rt"); y += 38
    y += 4
    d.line((30, y, W - 30, y), fill=(120, 120, 120), width=2); y += 14
    d.text((30, y), "부가세(포함)", font=f(21), fill=(70, 70, 70)); d.text((W - 30, y), f"{vat:,}", font=f(21), fill=(70, 70, 70), anchor="rt"); y += 34
    d.text((30, y), "합  계", font=f(30, True), fill=(10, 10, 10)); d.text((W - 30, y), f"{total:,}원", font=f(34, True), fill=(10, 10, 10), anchor="rt"); y += 58
    d.line((30, y, W - 30, y), fill=(160, 160, 160), width=1); y += 14
    d.text((30, y), f"결제  신용카드(법인)   {card}", font=f(21), fill=(50, 50, 50)); y += 32
    d.text((30, y), f"승인번호  {approve}   일시불", font=f(21), fill=(50, 50, 50)); y += 32
    d.text((W // 2, H - 42), "★ 데모용 가상 영수증입니다 ★", font=f(19), fill=(150, 150, 150), anchor="mt")
    # 영수증 하단 톱니 모양
    for x in range(0, W, 16):
        d.polygon([(x, H), (x + 8, H - 9), (x + 16, H)], fill=(226, 229, 235))
    im.paste(paper, (40, 40))
    im.save(path, optimize=True)
    return total


def build_receipts() -> None:
    out = SEED / "receipts"
    out.mkdir(parents=True, exist_ok=True)
    a = receipt(out / "receipt_A_점심_영업1팀.png", "해오름식당 판교점", "123-45-67890", "경기 성남시 분당구 판교역로 000", "2026-11-03 (화) 12:21",
                [("김치찌개정식", 4, 9000), ("계란말이", 1, 8000), ("음료", 4, 1000)], "5421-****-****-5678", "30458812")
    b = receipt(out / "receipt_B_회식_영업2팀.png", "고기명가 강남점", "987-65-43210", "서울 강남구 테헤란로 000", "2026-11-04 (수) 20:08",
                [("삼겹살(200g)", 12, 18000), ("목살(200g)", 6, 19000), ("소주", 10, 5000), ("맥주", 8, 5500), ("공기밥", 12, 1000), ("된장찌개", 4, 6000), ("냉면", 4, 5000)],
                "5421-****-****-5678", "30771204")
    print("receipts:", a, b)


# ----------------------------------------------------------------------------- 평가 데이터셋
EVAL_QA = [
    ("HR-001", "근속 4년인 직원의 연차는 며칠인가요?", "16일 (근속 3년 이상 5년 미만)"),
    ("HR-001", "연차를 반차나 반반차로 나누어 쓸 수 있나요? 각각 몇 시간인가요?", "가능하며 반차는 4시간, 반반차는 2시간"),
    ("HR-001", "연차 신청은 언제까지 어디에서 하나요?", "사용 예정일 1영업일 전까지 그룹웨어 '근태' 메뉴에서 신청하고 팀장이 승인합니다. 긴급한 경우 당일 오전 10시까지 사후 등록할 수 있습니다."),
    ("HR-001", "연차의 최대 일수는 며칠인가요?", "25일 (근속 21년 이상)"),
    ("HR-001", "배우자 출산휴가는 며칠이고 언제까지 쓸 수 있나요?", "유급 20일이며 출산일부터 120일 이내에 분할 사용할 수 있습니다."),
    ("HR-001", "재택근무는 주 몇 일까지 가능하고 별도 승인이 필요한가요?", "주 2일까지이며 전날까지 그룹웨어에 등록하면 되고 팀장 별도 승인은 필요 없습니다."),
    ("FIN-002", "석식 식대의 1인당 한도는 얼마인가요?", "30,000원 (부가세 포함)"),
    ("FIN-002", "팀 회식에서 주류 비용도 정산할 수 있나요?", "원칙적으로 정산할 수 없고, 접대비 사전 품의가 승인된 경우에만 인정됩니다."),
    ("FIN-002", "30만 원을 초과하고 100만 원 이하인 지출은 누가 승인하나요?", "본부장"),
    ("FIN-002", "간이영수증은 얼마까지 인정되고 정산은 언제까지 신청하나요?", "30,000원 이하만 인정하며 지출일로부터 7일 이내에 신청합니다."),
    ("FIN-002", "국내 출장 시 서울 숙박비 상한은 얼마인가요?", "1박 150,000원"),
    ("SEC-003", "고객 연락처가 들어 있는 엑셀을 생성형 AI에 넣어도 되나요?", "고객 개인정보는 입력 금지이며, 꼭 필요하면 마스킹·비식별화한 뒤 사내 승인 서비스(Contoso AI)에서만 사용해야 합니다."),
    ("SEC-003", "개인정보 유출이 의심되면 언제 어디에 신고하나요?", "1시간 이내에 정보보호팀(내선 7777)에 신고하고 24시간 이내에 사고 보고서를 제출합니다."),
    ("CS-004", "AirPure AP-500의 헤파 필터 교체 주기는?", "12개월 (프리필터는 6개월마다 물세척)"),
    ("CS-004", "로보클린 R7 배터리 보증 기간과 무상 교체 기준은?", "배터리 보증은 1년이며 용량이 구매 당시의 70% 미만이면 보증 기간 안에 무상 교체합니다."),
    ("CS-004", "제품 하자가 있으면 며칠 안에 교환·환불할 수 있나요?", "구매 후 30일 이내에 신품 교환 또는 환불 (단순 변심은 7일 이내, 미사용·미개봉)"),
    ("LEG-005", "납품 지연 시 지체상금 비율과 상한은?", "지연 1일당 계약금액의 0.1%이며 상한은 계약금액의 10%"),
    ("LEG-005", "법무팀 검토가 필수인 계약 금액 기준은?", "5,000만원 이상 (5억원 이상은 CFO 승인 추가)"),
    ("PUR-008", "5,000만 원 이상 구매는 어떤 방식으로 진행하나요?", "전자 경쟁입찰"),
    ("PUR-008", "협력사가 C등급을 2회 연속 받으면 어떻게 되나요?", "거래 중지를 검토합니다."),
    ("(문서에 없음)", "우리 회사의 사내 주차 지원금은 얼마인가요?", "제공된 사규에서 확인되지 않으므로 답할 수 없고 담당 부서에 문의해야 합니다."),
    ("(문서에 없음)", "Contoso의 올해 영업이익은 얼마인가요?", "제공된 사규에서 확인되지 않으므로 답할 수 없습니다."),
]


def build_eval() -> None:
    out = SEED / "evals"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "dataset.jsonl", "w", encoding="utf-8") as f:
        for doc, q, a in EVAL_QA:
            f.write(json.dumps({"query": q, "ground_truth": a, "source": doc}, ensure_ascii=False) + "\n")
    print("eval items:", len(EVAL_QA))


def main() -> None:
    (SEED / "samples").mkdir(parents=True, exist_ok=True)
    sales = build_sales()
    with open(SEED / "samples/sales_2025_2026.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(sales[0]))
        w.writeheader(); w.writerows(sales)
    voc = build_voc()
    with open(SEED / "samples/voc_2026.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(voc[0]))
        w.writeheader(); w.writerows(voc)
    print("sales rows:", len(sales), "voc rows:", len(voc))
    build_receipts()
    build_eval()


if __name__ == "__main__":
    main()
