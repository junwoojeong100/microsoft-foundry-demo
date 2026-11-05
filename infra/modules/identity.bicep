// 웹앱이 키 없이(Entra ID) Foundry 와 ACR 에 접근하기 위한 사용자 할당 관리 ID
param location string
param tags object
param name string

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

output id string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId
