// Microsoft Foundry 리소스(AIServices) + 프로젝트 + 가드레일 + 모델 배포 + 트레이싱 연결 + RBAC
param location string
param tags object
param accountName string
param projectName string
param appInsightsId string
@secure()
param appInsightsConnectionString string
param webIdentityPrincipalId string
param deployerPrincipalId string
param deployerPrincipalType string = 'User'
param demoLang string = 'ko'

@description('배포할 모델 목록: { name, format, model, version, sku, capacity }')
param models array

var roleAzureAIUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var roleCognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var roleCognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var roleAzureAIProjectManager = 'eadc314b-1a2d-4efa-be10-5d325db5065e'

// Foundry 리소스: 키 인증 비활성화(Entra ID 전용) + 프로젝트 관리 활성화
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: accountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow' }
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'Contoso AI'
    description: demoLang == 'en' ? 'Microsoft Foundry demo — agents, knowledge search, guardrails, evaluation, observability' : 'Microsoft Foundry 데모 — 에이전트, 지식 검색, 가드레일, 평가, 관측'
  }
}

// 가드레일: 입력(프롬프트)과 출력(응답) 모두에 콘텐츠 필터 + Prompt Shields(탈옥·간접 공격) 차단
resource guardrail 'Microsoft.CognitiveServices/accounts/raiPolicies@2025-06-01' = {
  parent: account
  name: 'contoso-guardrail'
  // 같은 계정에 대한 ARM 작업은 겹치면 충돌하므로 project → guardrail → connection → deployments 순으로 직렬화합니다.
  dependsOn: [project]
  properties: {
    mode: 'Blocking'
    basePolicyName: 'Microsoft.DefaultV2'
    contentFilters: [
      { name: 'Hate', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Hate', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Sexual', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Sexual', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Violence', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Violence', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Selfharm', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Selfharm', severityThreshold: 'Medium', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Jailbreak', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Indirect Attack', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Protected Material Text', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Protected Material Code', blocking: false, enabled: true, source: 'Completion' }
    ]
  }
}

// 모델 배포 — 같은 계정에는 순차 배포가 안전합니다.
@batchSize(1)
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [for m in models: {
  parent: account
  name: m.name
  dependsOn: [appInsightsConnection]
  sku: {
    name: m.sku
    capacity: m.capacity
  }
  properties: {
    model: {
      format: m.format
      name: m.model
      version: m.version
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: (m.format == 'OpenAI' && m.model != 'text-embedding-3-large') ? guardrail.name : null
  }
}]

// Foundry 트레이싱/모니터링: 프로젝트에 Application Insights 연결
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-06-01' = {
  parent: account
  name: 'appinsights'
  dependsOn: [guardrail]
  properties: {
    category: 'AppInsights'
    target: appInsightsId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: { key: appInsightsConnectionString }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsightsId
    }
  }
}

// ---- RBAC (최소 권한) --------------------------------------------------------
// 웹앱 관리 ID: 에이전트/모델 호출 + Content Safety
resource webAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, webIdentityPrincipalId, roleAzureAIUser)
  scope: account
  properties: {
    principalId: webIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIUser)
  }
}
resource webCogUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, webIdentityPrincipalId, roleCognitiveServicesUser)
  scope: account
  properties: {
    principalId: webIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesUser)
  }
}
resource webOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, webIdentityPrincipalId, roleCognitiveServicesOpenAIUser)
  scope: account
  properties: {
    principalId: webIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesOpenAIUser)
  }
}

// 프로젝트 관리 ID: 평가(LLM judge)가 계정의 모델을 호출할 수 있도록
resource projectOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, project.id, roleCognitiveServicesOpenAIUser)
  scope: account
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesOpenAIUser)
  }
}

// 배포한 사용자: 포털/스크립트에서 에이전트를 만들고 시연할 수 있도록
resource deployerAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(account.id, deployerPrincipalId, roleAzureAIUser)
  scope: account
  properties: {
    principalId: deployerPrincipalId
    principalType: deployerPrincipalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIUser)
  }
}
resource deployerCogUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(account.id, deployerPrincipalId, roleCognitiveServicesUser)
  scope: account
  properties: {
    principalId: deployerPrincipalId
    principalType: deployerPrincipalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesUser)
  }
}
resource deployerProjectManager 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(account.id, deployerPrincipalId, roleAzureAIProjectManager)
  scope: account
  properties: {
    principalId: deployerPrincipalId
    principalType: deployerPrincipalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIProjectManager)
  }
}

output accountName string = account.name
output accountId string = account.id
output accountEndpoint string = 'https://${account.name}.services.ai.azure.com'
output projectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${projectName}'
output projectPrincipalId string = project.identity.principalId
