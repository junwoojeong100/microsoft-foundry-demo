# azd up 직전 (Windows/PowerShell): 배포자 ID 설정 + 접속 코드 생성 + 공급자 등록
$ErrorActionPreference = 'Stop'
# DEMO_LANG=en(azd env set DEMO_LANG en)이면 영어 메시지를 출력합니다
$en = $env:DEMO_LANG -eq 'en'
$mStart = if ($en) { '▶ Pre-flight checks' } else { '▶ 사전 점검' }
$mNoAz = if ($en) { 'Azure CLI (az) is required: https://aka.ms/installazurecli' } else { 'Azure CLI(az)가 필요합니다: https://aka.ms/installazurecli' }
$mRegOk = if ($en) { '  ✔ Resource providers verified' } else { '  ✔ 리소스 공급자 확인' }
$mPid = if ($en) { '  ✔ Deployer identity set' } else { '  ✔ 배포자 ID 설정' }
$mCode = if ($en) { '  ✔ Access code generated (show it with: azd env get-value DEMO_ACCESS_CODE)' } else { '  ✔ 접속 코드 생성 (azd env get-value DEMO_ACCESS_CODE 로 확인)' }
Write-Host $mStart
if (-not (Get-Command az -ErrorAction SilentlyContinue)) { Write-Error $mNoAz }

$sub = if ($env:AZURE_SUBSCRIPTION_ID) { $env:AZURE_SUBSCRIPTION_ID } else { az account show --query id -o tsv }
foreach ($ns in 'Microsoft.CognitiveServices','Microsoft.App','Microsoft.ContainerRegistry','Microsoft.OperationalInsights','Microsoft.Insights','Microsoft.ManagedIdentity') {
  $state = az provider show -n $ns --subscription $sub --query registrationState -o tsv 2>$null
  if ($state -ne 'Registered') { Write-Host $(if ($en) { "  · Registering $ns…" } else { "  · $ns 등록 중…" }); az provider register -n $ns --subscription $sub --wait | Out-Null }
}
Write-Host $mRegOk

if (-not $env:AZURE_PRINCIPAL_ID) {
  $oid = az ad signed-in-user show --query id -o tsv 2>$null
  if ($oid) { azd env set AZURE_PRINCIPAL_ID $oid | Out-Null; Write-Host $mPid }
}
if (-not $env:DEMO_ACCESS_CODE) {
  $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'.ToCharArray()
  $code = -join (1..8 | ForEach-Object { $chars | Get-Random })
  azd env set DEMO_ACCESS_CODE $code | Out-Null
  Write-Host $mCode
}
