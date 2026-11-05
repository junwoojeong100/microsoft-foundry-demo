#!/bin/sh
# azd up 마무리: 앱이 처음 뜨면서 하는 준비 작업(벡터 스토어·에이전트 생성)이 끝날 때까지 기다리고 접속 정보를 보여 준다
set -u
URL="${WEB_URI:-}"
[ -n "$URL" ] || { echo "WEB_URI 가 없습니다"; exit 0; }

echo ""
echo "▶ 첫 기동 준비 작업 대기 (사규 PDF 인덱싱 · 에이전트 4개 생성)"
i=0
while [ $i -lt 90 ]; do
  body="$(curl -fsS -m 10 "$URL/healthz" 2>/dev/null || true)"
  case "$body" in
    *'"bootstrap":"ready"'*) echo "  ✔ 준비 완료"; break ;;
    *'"bootstrap":"error"'*) echo "  ✘ 준비 중 오류 — 컨테이너 로그를 확인하세요: az containerapp logs show -n ${WEB_APP_NAME:-} -g ${AZURE_RESOURCE_GROUP:-}"; break ;;
  esac
  i=$((i+1)); sleep 5
done

TID="${AZURE_TENANT_ID:-}"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ 배포 완료 — Contoso AI"
echo "  웹 앱       $URL"
echo "  접속 코드   ${DEMO_ACCESS_CODE:-(없음)}"
echo "  리전        ${AZURE_LOCATION:-}"
echo "  Foundry     ${FOUNDRY_PROJECT_ENDPOINT:-}"
echo "  정리        azd down --purge --force"
echo "════════════════════════════════════════════════════════════"
