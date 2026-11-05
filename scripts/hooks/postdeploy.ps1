# azd up 마무리 (Windows/PowerShell)
$url = $env:WEB_URI
if (-not $url) { Write-Host 'WEB_URI 가 없습니다'; exit 0 }
Write-Host ''
Write-Host '▶ 첫 기동 준비 작업 대기 (사규 PDF 인덱싱 · 에이전트 4개 생성)'
for ($i = 0; $i -lt 90; $i++) {
  try { $body = (Invoke-WebRequest -Uri "$url/healthz" -TimeoutSec 10 -UseBasicParsing).Content } catch { $body = '' }
  if ($body -match '"bootstrap":"ready"') { Write-Host '  ✔ 준비 완료'; break }
  if ($body -match '"bootstrap":"error"') { Write-Host '  ✘ 준비 중 오류 — 컨테이너 로그를 확인하세요'; break }
  Start-Sleep -Seconds 5
}
Write-Host ''
Write-Host '════════════════════════════════════════════════════════════'
Write-Host '  ✅ 배포 완료 — Contoso AI'
Write-Host "  웹 앱       $url"
Write-Host "  접속 코드   $($env:DEMO_ACCESS_CODE)"
Write-Host "  리전        $($env:AZURE_LOCATION)"
Write-Host "  Foundry     $($env:FOUNDRY_PROJECT_ENDPOINT)"
Write-Host '  정리        azd down --purge --force'
Write-Host '════════════════════════════════════════════════════════════'
