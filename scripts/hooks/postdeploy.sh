#!/bin/sh
# azd up 마무리: 앱이 처음 뜨면서 하는 준비 작업(벡터 스토어·에이전트 생성)이 끝날 때까지 기다리고 접속 정보를 보여 준다
set -u
URL="${WEB_URI:-}"

# DEMO_LANG=en(azd env set DEMO_LANG en)이면 영어 메시지를 출력합니다
if [ "${DEMO_LANG:-ko}" = "en" ]; then
  M_NO_URL="WEB_URI is not set"
  M_WAIT="▶ Waiting for first-boot setup (indexing policy PDFs · creating 4 agents)"
  M_READY="  ✔ Setup complete"
  M_ERR="  ✘ Setup failed — check the container logs: az containerapp logs show -n %s -g %s"
  M_DONE="  ✅ Deployment complete — Contoso AI"
  M_WEB="  Web app     "
  M_CODE="  Access code "
  M_NONE="(none)"
  M_REGION="  Region      "
  M_CLEAN="  Clean up    azd down --purge --force"
else
  M_NO_URL="WEB_URI 가 없습니다"
  M_WAIT="▶ 첫 기동 준비 작업 대기 (사규 PDF 인덱싱 · 에이전트 4개 생성)"
  M_READY="  ✔ 준비 완료"
  M_ERR="  ✘ 준비 중 오류 — 컨테이너 로그를 확인하세요: az containerapp logs show -n %s -g %s"
  M_DONE="  ✅ 배포 완료 — Contoso AI"
  M_WEB="  웹 앱       "
  M_CODE="  접속 코드   "
  M_NONE="(없음)"
  M_REGION="  리전        "
  M_CLEAN="  정리        azd down --purge --force"
fi

[ -n "$URL" ] || { echo "$M_NO_URL"; exit 0; }

echo ""
echo "$M_WAIT"
i=0
while [ $i -lt 90 ]; do
  body="$(curl -fsS -m 10 "$URL/healthz" 2>/dev/null || true)"
  case "$body" in
    *'"bootstrap":"ready"'*) echo "$M_READY"; break ;;
    *'"bootstrap":"error"'*) printf "$M_ERR\n" "${WEB_APP_NAME:-}" "${AZURE_RESOURCE_GROUP:-}"; break ;;
  esac
  i=$((i+1)); sleep 5
done

TID="${AZURE_TENANT_ID:-}"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "$M_DONE"
echo "${M_WEB}$URL"
echo "${M_CODE}${DEMO_ACCESS_CODE:-$M_NONE}"
echo "${M_REGION}${AZURE_LOCATION:-}"
echo "  Foundry     ${FOUNDRY_PROJECT_ENDPOINT:-}"
echo "$M_CLEAN"
echo "════════════════════════════════════════════════════════════"
