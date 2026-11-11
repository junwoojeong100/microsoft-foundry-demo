#!/usr/bin/env python3
"""발표 덱(PPTX)을 웹에 공개할 사본으로 slides/ 에 복사합니다 — 개인 메타데이터만 지우고 슬라이드·노트·영상은 그대로 둡니다.

    python scripts/publish_deck.py <덱.pptx> --lang ko     # → slides/Microsoft_Foundry_Demo_Deck_KO.pptx
    python scripts/publish_deck.py <덱.pptx> --lang en     # → slides/Microsoft_Foundry_Demo_Deck_EN.pptx

지우는 것(원본 덱은 건드리지 않습니다)
  · 마지막 수정자 이름 → 저장소 소유자의 GitHub 아이디로 교체 (PowerPoint 는 로그인한 사람의 실명을 파일에 남깁니다)
  · Microsoft 민감도 레이블(docMetadata/LabelInfo.xml 과 그 연결) — 사내 문서에 붙는 분류 표시라 공개용 사본에는 두지 않습니다.
    회사의 공개 절차가 'Public 레이블 지정'을 요구한다면 PowerPoint 에서 먼저 지정한 뒤 --keep-label 로 복사하세요.

복사한 파일은 scripts/build_site.py 가 사이트(GitHub Pages)에 싣고, README 의 Office 웹 뷰어 링크가 이 파일을 가리킵니다.
GitHub 는 파일당 100MB 까지만 받습니다(50MB 를 넘으면 push 때 경고만 나옵니다).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_site import DECK_NAMES, ROOT, SLIDES_DIR, die, repo_slug  # noqa: E402

LABEL_PART = "docMetadata/LabelInfo.xml"


def sanitize(src: pathlib.Path, dst: pathlib.Path, owner: str, keep_label: bool) -> dict[str, bool]:
    done = {"modifier": False, "label": False}
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
        for info in zi.infolist():
            name, data = info.filename, zi.read(info.filename)
            if name == LABEL_PART and not keep_label:
                done["label"] = True
                continue
            if name == "docProps/core.xml":
                text = data.decode("utf-8")
                new = re.sub(r"(<cp:lastModifiedBy>)[^<]*(</cp:lastModifiedBy>)", rf"\g<1>{owner}\g<2>", text)
                done["modifier"] = new != text
                data = new.encode("utf-8")
            elif name == "_rels/.rels" and not keep_label:
                data = re.sub(r'<Relationship [^>]*Target="docMetadata/LabelInfo\.xml"[^>]*/>', "", data.decode("utf-8")).encode("utf-8")
            elif name == "[Content_Types].xml" and not keep_label:
                data = re.sub(r'<Override [^>]*PartName="/docMetadata/LabelInfo\.xml"[^>]*/>', "", data.decode("utf-8")).encode("utf-8")
            zo.writestr(info, data, compress_type=info.compress_type)
    return done


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pptx", type=pathlib.Path)
    ap.add_argument("--lang", required=True, choices=sorted(DECK_NAMES))
    ap.add_argument("--keep-label", action="store_true", help="민감도 레이블을 지우지 않고 그대로 둡니다")
    args = ap.parse_args()
    if not args.pptx.is_file():
        die(f"덱을 찾지 못했습니다: {args.pptx}")
    with zipfile.ZipFile(args.pptx) as z:
        if "ppt/presentation.xml" not in z.namelist():
            die("PPTX 가 아닙니다(ppt/presentation.xml 이 없습니다)")

    owner = repo_slug(None).split("/", 1)[0]
    dst = SLIDES_DIR / DECK_NAMES[args.lang]
    SLIDES_DIR.mkdir(exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    done = sanitize(args.pptx, tmp, owner, args.keep_label)
    with zipfile.ZipFile(tmp) as z:
        bad = z.testzip()
        slides = sum(1 for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
        clips = sum(1 for n in z.namelist() if re.fullmatch(r"ppt/media/.+\.mp4", n))
    if bad:
        tmp.unlink()
        die(f"압축 파일이 손상됐습니다: {bad}")
    tmp.replace(dst)

    size = dst.stat().st_size
    print(f"✔ {dst.relative_to(ROOT)}  {size / 1e6:.1f}MB · 슬라이드 {slides}장 · 내장 영상 {clips}개")
    print(f"  마지막 수정자 → {owner}: {'교체함' if done['modifier'] else '바꿀 항목 없음'} · 민감도 레이블: {'제거함' if done['label'] else ('유지함' if args.keep_label else '원래 없음')}")
    if size > 95 * 1024 * 1024:
        print("  ⚠ 95MB 를 넘습니다 — GitHub 파일 한도(100MB)에 걸립니다. 슬라이드 속 영상 클립을 더 낮은 화질로 다시 만드세요")
    elif size > 50 * 1024 * 1024:
        print("  ℹ 50MB 를 넘어 push 할 때 GitHub 경고가 나옵니다(올라가기는 합니다)")


if __name__ == "__main__":
    main()
