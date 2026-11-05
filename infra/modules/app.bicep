// ACR + Container Apps 환경 + 웹앱(FastAPI + 정적 프런트엔드)
param location string
param tags object
@minLength(8)
param resourceToken string
param identityId string
param identityClientId string
param identityPrincipalId string
param logAnalyticsName string
@secure()
param appInsightsConnectionString string
@secure()
param demoAccessCode string
param foundryProjectEndpoint string
param foundryAccountEndpoint string
param foundryAccountName string
param foundryProjectName string
param region string
param subscriptionId string
param resourceGroupName string
param tenantId string

var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsName
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'cr${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identityPrincipalId, roleAcrPull)
  scope: registry
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
  }
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-${resourceToken}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
  }
}

resource web 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-web-${resourceToken}'
  location: location
  // azd 가 `azd-service-name: web` 태그로 배포 대상 컨테이너 앱을 찾습니다.
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        { server: registry.properties.loginServer, identity: identityId }
      ]
      secrets: [
        { name: 'demo-access-code', value: empty(demoAccessCode) ? 'not-set' : demoAccessCode }
        { name: 'appinsights-connection-string', value: appInsightsConnectionString }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          // 첫 프로비저닝 때만 쓰는 자리표시 이미지. `azd deploy` 가 실제 이미지로 교체합니다.
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            { name: 'PORT', value: '8000' }
            { name: 'AZURE_CLIENT_ID', value: identityClientId }
            { name: 'AZURE_REGION', value: region }
            { name: 'AZURE_SUBSCRIPTION_ID', value: subscriptionId }
            { name: 'AZURE_RESOURCE_GROUP', value: resourceGroupName }
            { name: 'AZURE_TENANT_ID', value: tenantId }
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'FOUNDRY_ACCOUNT_ENDPOINT', value: foundryAccountEndpoint }
            { name: 'FOUNDRY_ACCOUNT_NAME', value: foundryAccountName }
            { name: 'FOUNDRY_PROJECT_NAME', value: foundryProjectName }
            { name: 'MODEL_FLAGSHIP', value: 'gpt-6.1-sol' }
            { name: 'MODEL_FAST', value: 'gpt-6.1-terra' }
            { name: 'MODEL_ROUTER', value: 'model-router' }
            { name: 'MODEL_EMBEDDING', value: 'text-embedding-3-large' }
            { name: 'AUTH_MODE', value: empty(demoAccessCode) ? 'none' : 'code' }
            { name: 'DEMO_ACCESS_CODE', secretRef: 'demo-access-code' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
            { name: 'AUTO_BOOTSTRAP', value: 'true' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          { name: 'http', http: { metadata: { concurrentRequests: '30' } } }
        ]
      }
    }
  }
  dependsOn: [acrPull]
}

output registryLoginServer string = registry.properties.loginServer
output name string = web.name
output uri string = 'https://${web.properties.configuration.ingress.fqdn}'
