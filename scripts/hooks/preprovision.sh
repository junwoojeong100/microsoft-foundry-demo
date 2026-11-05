#!/bin/sh
# azd up 직전: (1) 배포자의 Entra object ID 를 Foundry 역할 부여 대상으로 설정 (2) 접속 코드가 없으면 만든다
set -eu

echo "▶ 사전 점검"
command -v az >/dev/null 2>&1 || { echo "✘ Azure CLI(az)가 필요합니다: https://aka.ms/installazurecli"; exit 1; }

# 필요한 리소스 공급자 등록 (이미 등록되어 있으면 즉시 끝남)
SUB="${AZURE_SUBSCRIPTION_ID:-$(az account show --query id -o tsv)}"
for ns in Microsoft.CognitiveServices Microsoft.App Microsoft.ContainerRegistry Microsoft.OperationalInsights Microsoft.Insights Microsoft.ManagedIdentity; do
  state="$(az provider show -n "$ns" --subscription "$SUB" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)"
  if [ "$state" != "Registered" ]; then
    echo "  · $ns 등록 중…"
    az provider register -n "$ns" --subscription "$SUB" --wait >/dev/null
  fi
done
echo "  ✔ 리소스 공급자 확인"

# 배포하는 사람에게 Foundry 데이터 평면 역할을 부여하기 위한 ID
if [ -z "${AZURE_PRINCIPAL_ID:-}" ]; then
  PID="$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)"
  if [ -n "$PID" ]; then azd env set AZURE_PRINCIPAL_ID "$PID" >/dev/null; echo "  ✔ 배포자 ID 설정"; fi
fi

# 데모 웹앱 접속 코드 (공개 URL 에 GPT 호출이 무방비로 열리지 않도록)
if [ -z "${DEMO_ACCESS_CODE:-}" ]; then
  CODE="$(LC_ALL=C tr -dc 'A-HJ-NP-Z2-9' </dev/urandom | head -c 8)"
  azd env set DEMO_ACCESS_CODE "$CODE" >/dev/null
  echo "  ✔ 접속 코드 생성 (azd env get-value DEMO_ACCESS_CODE 로 확인)"
fi
