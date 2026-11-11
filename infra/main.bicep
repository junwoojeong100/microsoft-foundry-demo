// =============================================================================
// Microsoft Foundry Demo — Contoso AI
// 한 번의 `azd up` 으로 단일 리전(한국 중부)에 아래를 모두 배포합니다.
//   · Microsoft Foundry 리소스 + 프로젝트  (Agent Service, 모델 배포, 가드레일, 평가, 트레이싱)
//   · GPT-6.1 (sol / terra) + Model Router + 임베딩 + 멀티벤더 모델
//   · Azure Container Apps 위의 ChatGPT 스타일 웹앱 (FastAPI + 정적 프런트엔드)
//   · Log Analytics / Application Insights / ACR / 관리 ID 와 최소 권한 RBAC
// =============================================================================
targetScope = 'subscription'

@minLength(1)
@maxLength(32)
@description('azd 환경 이름. 모든 리소스 이름의 일부로 사용됩니다.')
param environmentName string

@description('모든 리소스를 배포할 단일 리전. 기본값은 한국 중부(koreacentral).')
param location string = 'koreacentral'

@description('배포하는 사용자(또는 서비스 주체)의 Entra object ID. Foundry 데이터 평면 역할이 부여됩니다.')
param principalId string = ''

@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'

@secure()
@description('데모 웹앱 접속 코드. 비어 있으면 인증 없이 열립니다(로컬 개발 전용).')
param demoAccessCode string = ''

@description('Foundry 프로젝트 이름.')
param projectName string = 'contoso-ai'

@description('일반 채팅의 모델 선택과 Foundry 포털의 모델 비교용 멀티벤더 모델(DeepSeek, Llama, Kimi, Mistral, Grok)까지 함께 배포할지 여부.')
param deployMultiVendorModels bool = true

@description('모델 배포 SKU. GlobalStandard(기본) · DataZoneStandard 중 선택.')
@allowed(['GlobalStandard', 'DataZoneStandard'])
param chatModelSku string = 'GlobalStandard'

@description('데모 화면 언어: ko(기본) 또는 en. 앱 UI·에이전트 지침·샘플 문서와 프로젝트 설명의 언어를 정합니다(azd env set DEMO_LANG en).')
param demoLang string = 'ko'

var lang = demoLang == 'en' ? 'en' : 'ko'  // 빈 값·알 수 없는 값은 한국어

var tags = {
  'azd-env-name': environmentName
  workload: 'microsoft-foundry-demo'
}
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

// ---- 모델 카탈로그 (배포 이름 = 코드에서 쓰는 이름) --------------------------------
var coreModels = [
  { name: 'gpt-6.1-sol', format: 'OpenAI', model: 'gpt-6.1-sol', version: '2026-09-29', sku: chatModelSku, capacity: 100 }
  { name: 'gpt-6.1-terra', format: 'OpenAI', model: 'gpt-6.1-terra', version: '2026-10-26', sku: chatModelSku, capacity: 200 }
  { name: 'model-router', format: 'OpenAI', model: 'model-router', version: '2025-11-18', sku: 'GlobalStandard', capacity: 100 }
  { name: 'text-embedding-3-large', format: 'OpenAI', model: 'text-embedding-3-large', version: '1', sku: 'Standard', capacity: 120 }
]
var multiVendorModels = [
  { name: 'deepseek-v4-pro', format: 'DeepSeek', model: 'DeepSeek-V4-Pro', version: '2026-04-23', sku: 'GlobalStandard', capacity: 50 }
  { name: 'kimi-k3.1-pro', format: 'MoonshotAI', model: 'Kimi-K3.1-Pro', version: '2026-11-04', sku: 'GlobalStandard', capacity: 50 }
  { name: 'llama-4-maverick', format: 'Meta', model: 'Llama-4-Maverick-17B-128E-Instruct-FP8', version: '1', sku: 'GlobalStandard', capacity: 50 }
  { name: 'mistral-large-3', format: 'Mistral AI', model: 'Mistral-Large-3', version: '1', sku: 'GlobalStandard', capacity: 50 }
  { name: 'grok-4.7', format: 'xAI', model: 'grok-4.7', version: '1', sku: 'GlobalStandard', capacity: 20 }
]
var models = deployMultiVendorModels ? concat(coreModels, multiVendorModels) : coreModels

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    location: location
    tags: tags
    logAnalyticsName: 'log-${resourceToken}'
    appInsightsName: 'appi-${resourceToken}'
  }
}

module identity 'modules/identity.bicep' = {
  name: 'identity'
  scope: rg
  params: {
    location: location
    tags: tags
    name: 'id-web-${resourceToken}'
  }
}

module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  scope: rg
  params: {
    location: location
    tags: tags
    accountName: 'ai-${resourceToken}'
    projectName: projectName
    models: models
    appInsightsId: monitoring.outputs.appInsightsId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    webIdentityPrincipalId: identity.outputs.principalId
    deployerPrincipalId: principalId
    deployerPrincipalType: principalType
    demoLang: lang
  }
}

module app 'modules/app.bicep' = {
  name: 'app'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    identityId: identity.outputs.id
    identityClientId: identity.outputs.clientId
    identityPrincipalId: identity.outputs.principalId
    logAnalyticsName: monitoring.outputs.logAnalyticsName
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    demoAccessCode: demoAccessCode
    foundryProjectEndpoint: foundry.outputs.projectEndpoint
    foundryAccountEndpoint: foundry.outputs.accountEndpoint
    foundryAccountName: foundry.outputs.accountName
    foundryProjectName: projectName
    region: location
    subscriptionId: subscription().subscriptionId
    resourceGroupName: rg.name
    tenantId: tenant().tenantId
    demoLang: lang
  }
}

// ---- azd / 스크립트가 읽는 출력 -----------------------------------------------
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = app.outputs.registryLoginServer
output FOUNDRY_ACCOUNT_NAME string = foundry.outputs.accountName
output FOUNDRY_PROJECT_NAME string = projectName
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output FOUNDRY_ACCOUNT_ENDPOINT string = foundry.outputs.accountEndpoint
output APPLICATIONINSIGHTS_NAME string = monitoring.outputs.appInsightsName
output WEB_URI string = app.outputs.uri
output WEB_APP_NAME string = app.outputs.name
