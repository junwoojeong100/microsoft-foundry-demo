#!/usr/bin/env bash
# 로컬 개발 서버 — 배포된 Foundry 프로젝트(또는 azd 환경)에 붙어서 웹앱을 localhost 에서 실행합니다.
#
#   ./scripts/dev_local.sh            # azd 환경 값(.azure/<env>/.env)을 읽어 실행
#   PORT=8765 AUTH_MODE=none ./scripts/dev_local.sh
#   FOUNDRY_PROJECT_ENDPOINT=https://… ./scripts/dev_local.sh   # azd 없이 직접 지정
#
# 사전 조건: az login (Entra ID 로 Foundry 에 접속하므로 키가 필요 없습니다)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -z "${FOUNDRY_PROJECT_ENDPOINT:-}" ] && command -v azd >/dev/null 2>&1; then
  while IFS='=' read -r key value; do
    case "$key" in
      FOUNDRY_PROJECT_ENDPOINT|FOUNDRY_ACCOUNT_NAME|FOUNDRY_PROJECT_NAME|AZURE_RESOURCE_GROUP|AZURE_SUBSCRIPTION_ID|AZURE_LOCATION|APPLICATIONINSIGHTS_CONNECTION_STRING)
        export "$key=${value//\"/}" ;;
    esac
  done < <(azd env get-values 2>/dev/null || true)
fi
: "${FOUNDRY_PROJECT_ENDPOINT:?FOUNDRY_PROJECT_ENDPOINT 가 필요합니다 (azd up 후 실행하거나 직접 지정하세요)}"

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "가상환경이 없습니다: uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt"; exit 1; }

export AUTH_MODE="${AUTH_MODE:-none}"
export AUTO_BOOTSTRAP="${AUTO_BOOTSTRAP:-true}"
export AZURE_REGION="${AZURE_LOCATION:-koreacentral}"
cd "$ROOT/src/web"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" --log-level "${LOG_LEVEL:-info}"
