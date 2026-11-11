#!/usr/bin/env python3
"""데모용 가상 데이터를 만듭니다 (모두 가상: Contoso 판매 실적, 고객 VOC, 영수증 이미지, 평가 데이터셋).

    python scripts/build_sample_data.py             # 한국어판 → src/web/seed/
    python scripts/build_sample_data.py --lang en   # English edition → src/web/seed_en/

결과(src/web/seed/, --lang en 이면 src/web/seed_en/):
  samples/sales_2025_2026.csv   월×지역×제품×채널 판매 실적 (부산·경남 로봇청소기에 이상 신호를 심어 둠)
  samples/voc_2026.csv          고객 VOC 700건 (같은 지역·제품에 '배터리' 불만이 늘어남)
  receipts/*.png                경비 정산 에이전트용 영수증 이미지 2장
  evals/dataset.jsonl           사규 질문/정답 22건 (평가 데모용)

두 언어판은 같은 시드·같은 난수 호출 순서를 쓰므로 수치(수량·매출·평점 등)와 행 순서가 똑같고,
지역·제품·채널 이름, VOC 문장, 영수증·평가 문구만 언어별로 다릅니다.
영어판 영수증 파일명: receipt_A_lunch_sales_team_1.png, receipt_B_team_dinner_sales_team_2.png
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import random
from dataclasses import dataclass
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
rng = random.Random(20261105)


@dataclass(frozen=True)
class Lang:
    """언어판별 데이터. 같은 난수열로 같은 행이 나오도록 VOC 문장 목록의 순서·길이는 언어판끼리 같아야 합니다."""
    seed: pathlib.Path                    # 출력 폴더
    names: dict[str, dict[str, str]]      # 내부 키 → 파일에 쓰는 이름 (regions / products / channels)
    voc: dict[str, dict[str, list[str]]]  # 제품 키 → {"pos" | "neg" | "battery": [문장, …]}
    other_neg: list[str]                  # 제품과 무관한 불만 문장
    receipt_style: dict                   # 영수증 글꼴과 고정 문구
    receipts: list[dict]
    eval_qa: list[tuple[str, str, str]]   # (출처 문서, 질문, 정답)


# ----------------------------------------------------------------------------- 판매 실적
# 지역·제품·채널은 언어와 무관한 내부 키로 다루고, 파일에 쓰는 이름만 언어판(NAMES_*)에서 가져옵니다.
MONTHS = [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13) if not (y == 2026 and m > 10)]
REGIONS = {"seoul": 1.35, "gyeonggi_incheon": 1.25, "busan_gyeongnam": 0.9, "daegu_gyeongbuk": 0.62, "gwangju_jeolla": 0.5, "daejeon_chungcheong": 0.58}
PRODUCTS = {
    "air_purifier": dict(base=420, price=0.52, margin=0.32, season={1: 1.15, 2: 1.2, 3: 1.35, 4: 1.3, 5: 1.0, 6: 0.8, 7: 0.7, 8: 0.7, 9: 0.9, 10: 1.05, 11: 1.25, 12: 1.3}),
    "air_fryer": dict(base=300, price=0.18, margin=0.28, season={1: 1.0, 2: 0.9, 3: 0.85, 4: 0.85, 5: 0.9, 6: 0.9, 7: 0.85, 8: 0.9, 9: 1.0, 10: 1.15, 11: 1.4, 12: 1.5}),
    "robot_vacuum": dict(base=210, price=0.89, margin=0.30, season={1: 0.95, 2: 0.9, 3: 1.0, 4: 1.0, 5: 1.05, 6: 1.1, 7: 1.0, 8: 0.95, 9: 1.0, 10: 1.1, 11: 1.35, 12: 1.3}),
    "smart_lighting": dict(base=140, price=0.09, margin=0.4, season={m: 1.0 for m in range(1, 13)}),
}
CHANNELS = {"online": 0.52, "offline": 0.33, "b2b": 0.15}
NAMES_KO = dict(
    regions={"seoul": "서울", "gyeonggi_incheon": "경기·인천", "busan_gyeongnam": "부산·경남", "daegu_gyeongbuk": "대구·경북", "gwangju_jeolla": "광주·전라", "daejeon_chungcheong": "대전·충청"},
    products={"air_purifier": "공기청정기", "air_fryer": "에어프라이어", "robot_vacuum": "로봇청소기", "smart_lighting": "스마트조명"},
    channels={"online": "온라인", "offline": "오프라인", "b2b": "B2B"},
)
NAMES_EN = dict(
    regions={"seoul": "Seoul", "gyeonggi_incheon": "Gyeonggi-Incheon", "busan_gyeongnam": "Busan-Gyeongnam", "daegu_gyeongbuk": "Daegu-Gyeongbuk", "gwangju_jeolla": "Gwangju-Jeolla", "daejeon_chungcheong": "Daejeon-Chungcheong"},
    products={"air_purifier": "Air Purifier", "air_fryer": "Air Fryer", "robot_vacuum": "Robot Vacuum", "smart_lighting": "Smart Lighting"},
    channels={"online": "Online", "offline": "Offline", "b2b": "B2B"},
)


def build_sales(lang: Lang) -> list[dict]:
    names = lang.names
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
                    if region == "busan_gyeongnam" and product == "robot_vacuum" and month >= "2026-07":
                        k = {"2026-07": 0.78, "2026-08": 0.62, "2026-09": 0.55, "2026-10": 0.5}[month]
                        units *= k
                        ret = rng.uniform(9.5, 12) + (idx - MONTHS.index("2026-07")) * 1.6
                    # 긍정적 이상치: 2026-08 서울 에어프라이어 프로모션
                    if region == "seoul" and product == "air_fryer" and month == "2026-08" and channel == "online":
                        units *= 1.55
                    units = max(1, round(units))
                    revenue = round(units * p["price"], 1)  # 백만원
                    cost = round(revenue * (1 - p["margin"]) * rng.uniform(0.97, 1.03), 1)
                    rows.append(dict(month=month, region=names["regions"][region], product_line=names["products"][product], channel=names["channels"][channel],
                                     units=units, revenue_mkrw=revenue, cost_mkrw=cost, return_rate_pct=round(ret, 1)))
    return rows


# ----------------------------------------------------------------------------- VOC
# 언어판끼리 목록의 순서와 길이가 같아야 난수 선택(rng.choice)이 1:1로 맞습니다 — 문장만 번역하고 개수는 바꾸지 마세요.
VOC_KO = {
    "air_purifier": {
        "pos": ["공기가 확실히 맑아진 느낌이에요. 수면모드 소음도 거의 없어요.", "필터 교체 알림이 정확해서 관리하기 편합니다.", "앱으로 공기질을 볼 수 있어서 좋아요."],
        "neg": ["필터 가격이 조금 부담됩니다.", "와이파이 연결이 자주 끊겨요.", "작동할 때 소음이 생각보다 큽니다."],
    },
    "air_fryer": {
        "pos": ["튀김이 바삭하고 세척이 쉬워요.", "앱 레시피가 다양해서 요리가 즐거워졌어요.", "6.5L라 4인 가족도 충분합니다."],
        "neg": ["코팅이 벗겨지는 것 같아요.", "예열할 때 냄새가 나요.", "바스켓이 약간 뻑뻑합니다."],
    },
    "robot_vacuum": {
        "pos": ["장애물을 잘 피하고 청소 범위가 꼼꼼해요.", "앱으로 구역 지정이 편해요.", "물걸레 성능이 만족스럽습니다."],
        "neg": ["턱을 잘 못 넘어요.", "충전대 복귀가 가끔 실패해요.", "소음이 조금 큰 편이에요."],
        "battery": ["충전이 안 돼요. 충전대에 올려도 불이 안 들어옵니다.", "배터리가 10분도 안 가서 청소를 끝까지 못 합니다.", "충전 중에 전원이 자꾸 꺼져요. 배터리 문제 같아요.", "구매 두 달 만에 배터리가 방전됩니다. 교환 요청합니다.", "배터리 팽창이 의심돼서 사용을 멈췄어요. 불안합니다.", "A/S 접수했는데 배터리 재고가 없다고 2주째 대기 중입니다."],
    },
    "smart_lighting": {
        "pos": ["설치가 간단하고 색감이 좋아요.", "음성 비서 연동이 매끄럽습니다."],
        "neg": ["가끔 앱과 연결이 끊겨요.", "밝기 조절 단계가 거칠어요."],
    },
}
OTHER_NEG_KO = ["배송이 예정일보다 3일 늦었어요.", "고객센터 연결이 오래 걸렸습니다.", "A/S 방문 일정을 잡기가 어려웠어요.", "포장이 훼손되어 도착했습니다."]

VOC_EN = {
    "air_purifier": {
        "pos": ["The air feels noticeably cleaner. Sleep mode is almost silent.", "The filter replacement alerts are accurate, so upkeep is easy.", "I like being able to check the air quality in the app."],
        "neg": ["The replacement filters are a bit pricey.", "The Wi-Fi connection drops often.", "It's louder than I expected when it's running."],
    },
    "air_fryer": {
        "pos": ["Fried food comes out crispy and it's easy to clean.", "The app has plenty of recipes, so cooking has become more fun.", "At 6.5 L, it's big enough for a family of four."],
        "neg": ["The coating seems to be peeling off.", "It gives off a smell when preheating.", "The basket is a little stiff."],
    },
    "robot_vacuum": {
        "pos": ["It steers around obstacles well and covers the whole area thoroughly.", "Setting cleaning zones in the app is easy.", "I'm happy with the mopping performance."],
        "neg": ["It has trouble getting over thresholds.", "It sometimes fails to return to the charging dock.", "It's a bit on the loud side."],
        "battery": ["It won't charge. Even on the dock, the light doesn't come on.", "The battery doesn't even last 10 minutes, so it never finishes cleaning.", "It keeps shutting off while charging. I think it's a battery problem.", "The battery died just two months after purchase. I'm requesting a replacement.", "I suspect the battery is swelling, so I stopped using it. I'm worried.", "I requested after-sales service, but the battery is out of stock and I've been waiting two weeks."],
    },
    "smart_lighting": {
        "pos": ["Easy to install, and the colors look great.", "It works smoothly with my voice assistant."],
        "neg": ["It sometimes loses its connection to the app.", "The brightness steps are too coarse."],
    },
}
OTHER_NEG_EN = ["Delivery arrived three days later than scheduled.", "It took a long time to get through to the Customer Service Center.", "It was hard to schedule an after-sales service visit.", "The package arrived damaged."]


def build_voc(lang: Lang) -> list[dict]:
    names, voc = lang.names, lang.voc
    rows = []
    start = date(2026, 1, 1)
    days = (date(2026, 10, 31) - start).days
    for _ in range(700):
        d = start + timedelta(days=rng.randint(0, days))
        region = rng.choices(list(REGIONS), weights=list(REGIONS.values()))[0]
        product = rng.choices(list(PRODUCTS), weights=[3, 2.5, 3, 1.2])[0]
        channel = rng.choices(list(CHANNELS), weights=list(CHANNELS.values()))[0]
        battery_issue = product == "robot_vacuum" and region == "busan_gyeongnam" and d >= date(2026, 7, 1) and rng.random() < 0.7
        if battery_issue:
            text, rating = rng.choice(voc["robot_vacuum"]["battery"]), rng.choice([1, 1, 2])
        elif rng.random() < 0.62:
            text, rating = rng.choice(voc[product]["pos"]), rng.choice([4, 5, 5])
        elif rng.random() < 0.75:
            text, rating = rng.choice(voc[product]["neg"]), rng.choice([2, 3, 3])
        else:
            text, rating = rng.choice(lang.other_neg), rng.choice([2, 3])
        rows.append(dict(date=d.isoformat(), region=names["regions"][region], product=names["products"][product], channel=names["channels"][channel], rating=rating, text=text))
    # 이상 신호를 또렷하게: 부산·경남 로봇청소기의 7~10월 배터리 불만을 추가로 심는다
    for _ in range(70):
        d = date(2026, 7, 1) + timedelta(days=rng.randint(0, 122))
        rows.append(dict(date=d.isoformat(), region=names["regions"]["busan_gyeongnam"], product=names["products"]["robot_vacuum"],
                         channel=names["channels"][rng.choices(list(CHANNELS), weights=list(CHANNELS.values()))[0]],
                         rating=rng.choice([1, 1, 2]), text=rng.choice(voc["robot_vacuum"]["battery"])))
    rows.sort(key=lambda r: r["date"])
    return rows


# ----------------------------------------------------------------------------- 영수증
# fonts = (보통, 굵게), 각각 (글꼴 파일, 서체 번호). 영어판은 Helvetica 계열에 ★ 글리프가 없어 Arial Unicode + Arial Bold 를 씁니다.
# baseline=True 이면 같은 줄의 글자를 기준선(baseline)에 맞춥니다 (영어판). 한국어판은 기존 영수증과 똑같이 나오도록 원래 앵커를 씁니다.
RECEIPT_STYLE_KO = dict(
    fonts=(("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0), ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6)), baseline=False,
    biz="사업자번호 {biz}   대표 김○○", tel="TEL 000-0000-0000 (가상)", when="일시  {when}",
    cols=("품목", "수량", "단가", "금액"), vat="부가세(포함)", total="합  계", amount="{total:,}원",
    card="결제  신용카드(법인)   {card}", approve="승인번호  {approve}   일시불", footer="★ 데모용 가상 영수증입니다 ★",
)
RECEIPT_STYLE_EN = dict(
    fonts=(("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0), ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0)), baseline=True,
    biz="Business reg. no. {biz}   Rep. Kim", tel="TEL 000-0000-0000 (fictional)", when="Date/time  {when}",
    cols=("Item", "Qty", "Unit price", "Amount"), vat="VAT (incl.)", total="Total", amount="KRW {total:,}",
    card="Paid by: corporate credit card {card}", approve="Approval no. {approve}   Lump-sum payment", footer="★ Fictional demo receipt ★",
)
# 두 언어판의 수량·단가는 같아야 합니다 (check_alignment 가 확인).
RECEIPTS_KO = [
    dict(file="receipt_A_점심_영업1팀.png", title="해오름식당 판교점", biz="123-45-67890", addr="경기 성남시 분당구 판교역로 000", when="2026-11-03 (화) 12:21",
         items=[("김치찌개정식", 4, 9000), ("계란말이", 1, 8000), ("음료", 4, 1000)], card="5421-****-****-5678", approve="30458812"),
    dict(file="receipt_B_회식_영업2팀.png", title="고기명가 강남점", biz="987-65-43210", addr="서울 강남구 테헤란로 000", when="2026-11-04 (수) 20:08",
         items=[("삼겹살(200g)", 12, 18000), ("목살(200g)", 6, 19000), ("소주", 10, 5000), ("맥주", 8, 5500), ("공기밥", 12, 1000), ("된장찌개", 4, 6000), ("냉면", 4, 5000)],
         card="5421-****-****-5678", approve="30771204"),
]
RECEIPTS_EN = [
    dict(file="receipt_A_lunch_sales_team_1.png", title="Haeoreum Kitchen — Pangyo", biz="123-45-67890", addr="000 Pangyo-yeok-ro, Bundang-gu, Seongnam-si, Gyeonggi-do", when="2026-11-03 (Tue) 12:21",
         items=[("Kimchi stew set", 4, 9000), ("Rolled omelet", 1, 8000), ("Soft drink", 4, 1000)], card="5421-****-****-5678", approve="30458812"),
    dict(file="receipt_B_team_dinner_sales_team_2.png", title="Gogi Myeongga BBQ — Gangnam", biz="987-65-43210", addr="000 Teheran-ro, Gangnam-gu, Seoul", when="2026-11-04 (Wed) 20:08",
         items=[("Pork belly (200g)", 12, 18000), ("Pork neck (200g)", 6, 19000), ("Soju", 10, 5000), ("Beer", 8, 5500), ("Steamed rice", 12, 1000), ("Soybean paste stew", 4, 6000), ("Cold noodles", 4, 5000)],
         card="5421-****-****-5678", approve="30771204"),
]


def receipt(path: pathlib.Path, T: dict, r: dict) -> int:
    W = 640
    regular, bold_face = T["fonts"]

    def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        file, index = bold_face if bold else regular
        return ImageFont.truetype(file, size, index=index)

    def fit(text: str, size: int, bold: bool = False, max_w: int = W - 60) -> ImageFont.FreeTypeFont:
        """한 줄이 종이 폭을 넘으면 글자 크기를 줄여서 맞춥니다."""
        while size > 12 and f(size, bold).getlength(text) > max_w:
            size -= 1
        return f(size, bold)

    def put(x: int, y: int, text: str, font: ImageFont.FreeTypeFont, fill: tuple[int, int, int], h: str = "l", asc: int | None = None) -> None:
        """h = l/m/r (왼쪽·가운데·오른쪽 정렬). y 는 줄의 위쪽이며, baseline 모드의 기준선은 y + ascent (asc 로 줄 안의 가장 큰 글꼴 기준을 지정)."""
        if T["baseline"]:
            d.text((x, y + (font.getmetrics()[0] if asc is None else asc)), text, font=font, fill=fill, anchor=h + "s")
        elif h == "l":
            d.text((x, y), text, font=font, fill=fill)
        else:
            d.text((x, y), text, font=font, fill=fill, anchor=h + "t")

    items = r["items"]
    total = sum(q * p for _, q, p in items)
    vat = round(total / 11)
    H = 520 + 38 * len(items) + 40
    im = Image.new("RGB", (W + 80, H + 80), (226, 229, 235))
    paper = Image.new("RGB", (W, H), (255, 255, 253))
    d = ImageDraw.Draw(paper)
    y = 34
    put(W // 2, y, r["title"], fit(r["title"], 34, True), (20, 20, 20), "m"); y += 58
    for t in (T["biz"].format(biz=r["biz"]), r["addr"], T["tel"]):
        put(W // 2, y, t, fit(t, 20), (70, 70, 70), "m"); y += 30
    y += 10
    d.line((30, y, W - 30, y), fill=(120, 120, 120), width=2); y += 14
    when = T["when"].format(when=r["when"])
    put(30, y, when, fit(when, 22), (30, 30, 30)); y += 36
    d.line((30, y, W - 30, y), fill=(160, 160, 160), width=1); y += 12
    c_item, c_qty, c_unit, c_amount = T["cols"]
    put(30, y, c_item, f(20, True), (60, 60, 60))
    put(W - 260, y, c_qty, f(20, True), (60, 60, 60), "r")
    put(W - 150, y, c_unit, f(20, True), (60, 60, 60), "r")
    put(W - 30, y, c_amount, f(20, True), (60, 60, 60), "r"); y += 34
    for name, q, p in items:
        put(30, y, name, fit(name, 22, max_w=W - 260 - 100), (20, 20, 20))
        put(W - 260, y, f"{q}", f(22), (20, 20, 20), "r")
        put(W - 150, y, f"{p:,}", f(22), (20, 20, 20), "r")
        put(W - 30, y, f"{q * p:,}", f(22), (20, 20, 20), "r"); y += 38
    y += 4
    d.line((30, y, W - 30, y), fill=(120, 120, 120), width=2); y += 14
    put(30, y, T["vat"], f(21), (70, 70, 70)); put(W - 30, y, f"{vat:,}", f(21), (70, 70, 70), "r"); y += 34
    big = f(34, True)
    put(30, y, T["total"], f(30, True), (10, 10, 10), asc=big.getmetrics()[0]); put(W - 30, y, T["amount"].format(total=total), big, (10, 10, 10), "r"); y += 58
    d.line((30, y, W - 30, y), fill=(160, 160, 160), width=1); y += 14
    for t in (T["card"].format(card=r["card"]), T["approve"].format(approve=r["approve"])):
        put(30, y, t, fit(t, 21), (50, 50, 50)); y += 32
    put(W // 2, H - 42, T["footer"], fit(T["footer"], 19), (150, 150, 150), "m")
    # 영수증 하단 톱니 모양
    for x in range(0, W, 16):
        d.polygon([(x, H), (x + 8, H - 9), (x + 16, H)], fill=(226, 229, 235))
    im.paste(paper, (40, 40))
    im.save(path, optimize=True)
    return total


def build_receipts(lang: Lang) -> None:
    out = lang.seed / "receipts"
    out.mkdir(parents=True, exist_ok=True)
    totals = [receipt(out / r["file"], lang.receipt_style, r) for r in lang.receipts]
    print("receipts:", *totals)


# ----------------------------------------------------------------------------- 평가 데이터셋
EVAL_QA_KO = [
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

EVAL_QA_EN = [
    ("HR-001", "How many days of annual leave does an employee with 4 years of service get?", "16 days (3 to under 5 years of service)"),
    ("HR-001", "Can annual leave be taken as half-day or quarter-day leave? How many hours is each?", "Yes. Half-day leave is 4 hours and quarter-day leave is 2 hours."),
    ("HR-001", "By when and where do I request annual leave?", "Submit the request in the groupware 'Attendance' menu at least 1 business day before the planned date; the Team Lead approves it. In urgent cases, it can be registered after the fact by 10 a.m. on the day itself."),
    ("HR-001", "What is the maximum number of annual leave days?", "25 days (21 or more years of service)"),
    ("HR-001", "How many days is spouse's childbirth leave, and by when can it be used?", "20 paid days; it may be split and used within 120 days of the birth date."),
    ("HR-001", "How many days per week is remote work allowed, and is separate approval required?", "Up to 2 days per week. Register it in the groupware 'Attendance' menu by the previous day; separate approval from the Team Lead is not required."),
    ("FIN-002", "What is the per-person meal limit for dinner?", "KRW 30,000 (VAT included)"),
    ("FIN-002", "Can alcohol be reimbursed at a team dinner?", "As a rule it is not reimbursable; it is recognized only when an entertainment expense pre-approval request has been approved."),
    ("FIN-002", "Who approves an expense of more than KRW 300,000 and up to KRW 1,000,000?", "Division Head"),
    ("FIN-002", "Up to what amount are simplified receipts accepted, and by when must the expense report be submitted?", "Only amounts of KRW 30,000 or less are accepted, and the expense report must be submitted within 7 days of the expense date."),
    ("FIN-002", "What is the lodging cap per night in Seoul for a domestic business trip?", "KRW 150,000 per night"),
    ("SEC-003", "Can I put an Excel file containing customer contact details into a generative AI tool?", "Customer personal information must not be entered. If it is absolutely necessary, mask or de-identify it first and use it only in the company-approved service (Contoso AI)."),
    ("SEC-003", "If a personal information leak is suspected, when and to whom do I report it?", "Report it to the Information Security Team (ext. 7777) within 1 hour and submit an incident report within 24 hours."),
    ("CS-004", "How often should the HEPA filter of the AirPure AP-500 be replaced?", "Every 12 months (the pre-filter is washed with water every 6 months)"),
    ("CS-004", "What is the battery warranty period of the RoboClean R7, and what are the criteria for a free replacement?", "The battery warranty is 1 year. If the battery capacity drops below 70% of its capacity at the time of purchase, the battery is replaced free of charge within the warranty period."),
    ("CS-004", "Within how many days can a defective product be exchanged or refunded?", "Within 30 days of purchase, it is exchanged for a new one or refunded (for a simple change of mind: within 7 days, only if unused and unopened)."),
    ("LEG-005", "What are the liquidated damages rate and cap for late delivery?", "0.1% of the contract amount per day of delay, capped at 10% of the contract amount"),
    ("LEG-005", "At what contract value is Legal Team review required?", "KRW 50 million or more (at KRW 500 million or more, CFO approval is also required)"),
    ("PUR-008", "What purchasing method applies to purchases of KRW 50 million or more?", "Electronic competitive bidding"),
    ("PUR-008", "What happens if a supplier receives a C grade twice in a row?", "Suspension of business dealings with the supplier is considered."),
    ("(not in documents)", "How much is our company's parking subsidy for employees?", "This is not stated in the provided policies, so it cannot be answered; ask the responsible department."),
    ("(not in documents)", "What is Contoso's operating profit this year?", "This is not stated in the provided policies, so it cannot be answered."),
]


def build_eval(lang: Lang) -> None:
    out = lang.seed / "evals"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "dataset.jsonl", "w", encoding="utf-8") as f:
        for doc, q, a in lang.eval_qa:
            f.write(json.dumps({"query": q, "ground_truth": a, "source": doc}, ensure_ascii=False) + "\n")
    print("eval items:", len(lang.eval_qa))


# ----------------------------------------------------------------------------- 언어판
LANGS = {
    "ko": Lang(seed=ROOT / "src/web/seed", names=NAMES_KO, voc=VOC_KO, other_neg=OTHER_NEG_KO,
               receipt_style=RECEIPT_STYLE_KO, receipts=RECEIPTS_KO, eval_qa=EVAL_QA_KO),
    "en": Lang(seed=ROOT / "src/web/seed_en", names=NAMES_EN, voc=VOC_EN, other_neg=OTHER_NEG_EN,
               receipt_style=RECEIPT_STYLE_EN, receipts=RECEIPTS_EN, eval_qa=EVAL_QA_EN),
}


def check_alignment() -> None:
    """같은 난수열로 같은 행이 나오고 수치가 어긋나지 않도록, 언어판끼리 목록 구조·키·금액이 같은지 확인합니다."""
    ko, en = LANGS["ko"], LANGS["en"]
    shape = lambda voc: {p: {k: len(v) for k, v in d.items()} for p, d in voc.items()}  # noqa: E731
    assert list(ko.voc) == list(en.voc) == list(PRODUCTS), "VOC product keys must follow PRODUCTS order"
    assert shape(ko.voc) == shape(en.voc) and len(ko.other_neg) == len(en.other_neg), "VOC sentence lists must have the same shape"
    for part in ("regions", "products", "channels"):
        assert list(ko.names[part]) == list(en.names[part]), f"names[{part!r}] keys must match"
    assert [[(q, p) for _, q, p in r["items"]] for r in ko.receipts] == [[(q, p) for _, q, p in r["items"]] for r in en.receipts], "receipt quantities/prices must match"
    assert len(ko.eval_qa) == len(en.eval_qa), "eval datasets must have the same number of items"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=list(LANGS), default="ko", help="언어판: ko(기본) → src/web/seed, en → src/web/seed_en")
    lang = LANGS[ap.parse_args().lang]
    check_alignment()
    (lang.seed / "samples").mkdir(parents=True, exist_ok=True)
    sales = build_sales(lang)
    with open(lang.seed / "samples/sales_2025_2026.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(sales[0]))
        w.writeheader(); w.writerows(sales)
    voc = build_voc(lang)
    with open(lang.seed / "samples/voc_2026.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(voc[0]))
        w.writeheader(); w.writerows(voc)
    print("sales rows:", len(sales), "voc rows:", len(voc))
    build_receipts(lang)
    build_eval(lang)


if __name__ == "__main__":
    main()
