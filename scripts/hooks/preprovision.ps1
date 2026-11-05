# azd up 직전 (Windows/PowerShell): 배포자 ID 설정 + 접속 코드 생성 + 공급자 등록
$ErrorActionPreference = 'Stop'
Write-Host '▶ 사전 점검'
if (-not (Get-Command az -ErrorAction SilentlyContinue)) { Write-Error 'Azure CLI(az)가 필요합니다: https://aka.ms/installazurecli' }

$sub = if ($env:AZURE_SUBSCRIPTION_ID) { $env:AZURE_SUBSCRIPTION_ID } else { az account show --query id -o tsv }
foreach ($ns in 'Microsoft.CognitiveServices','Microsoft.App','Microsoft.ContainerRegistry','Microsoft.OperationalInsights','Microsoft.Insights','Microsoft.ManagedIdentity') {
  $state = az provider show -n $ns --subscription $sub --query registrationState -o tsv 2>$null
  if ($state -ne 'Registered') { Write-Host "  · $ns 등록 중…"; az provider register -n $ns --subscription $sub --wait | Out-Null }
}
Write-Host '  ✔ 리소스 공급자 확인'

if (-not $env:AZURE_PRINCIPAL_ID) {
  $oid = az ad signed-in-user show --query id -o tsv 2>$null
  if ($oid) { azd env set AZURE_PRINCIPAL_ID $oid | Out-Null; Write-Host '  ✔ 배포자 ID 설정' }
}
if (-not $env:DEMO_ACCESS_CODE) {
  $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'.ToCharArray()
  $code = -join (1..8 | ForEach-Object { $chars | Get-Random })
  azd env set DEMO_ACCESS_CODE $code | Out-Null
  Write-Host '  ✔ 접속 코드 생성 (azd env get-value DEMO_ACCESS_CODE 로 확인)'
}
