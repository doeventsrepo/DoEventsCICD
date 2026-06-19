# IAM dedicado para GitHub Actions deploy DEV (sa-east-1). NO usa credenciales admin.
param(
  [string]$UserName = "cicd-github-dev",
  [string]$PolicyName = "DoEventsCICD-GitHub-Dev-Deploy",
  [string]$Region = "sa-east-1"
)

$ErrorActionPreference = "Stop"
$PolicyFile = Join-Path $PSScriptRoot "iam-cicd-github-dev-policy.json"
$OutFile = Join-Path $PSScriptRoot "cicd-github-dev-credentials.json"

if (-not (Test-Path $PolicyFile)) { throw "Falta $PolicyFile" }

Write-Host "=== IAM user GitHub DEV: $UserName ===" -ForegroundColor Cyan

$policyArn = "arn:aws:iam::519010577666:policy/$PolicyName"
try {
  aws iam get-policy --policy-arn $policyArn 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    aws iam create-policy --policy-name $PolicyName --policy-document "file://$($PolicyFile -replace '\\','/')" | Out-Null
  }
} catch {
  aws iam create-policy --policy-name $PolicyName --policy-document "file://$($PolicyFile -replace '\\','/')" | Out-Null
}

try {
  aws iam get-user --user-name $UserName 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    aws iam create-user --user-name $UserName --tags Key=Purpose,Value=GitHubActionsDevDeploy | Out-Null
  }
} catch {
  aws iam create-user --user-name $UserName | Out-Null
}

aws iam attach-user-policy --user-name $UserName --policy-arn $policyArn | Out-Null

# Rotar key: max 2 keys
$keys = aws iam list-access-keys --user-name $UserName --output json | ConvertFrom-Json
foreach ($k in $keys.AccessKeyMetadata) {
  if ($keys.AccessKeyMetadata.Count -ge 2) {
    aws iam delete-access-key --user-name $UserName --access-key-id $k.AccessKeyId | Out-Null
  }
}

$keyJson = aws iam create-access-key --user-name $UserName --output json | ConvertFrom-Json
$creds = @{
  userName = $UserName
  accessKeyId = $keyJson.AccessKey.AccessKeyId
  secretAccessKey = $keyJson.AccessKey.SecretAccessKey
  cloudFrontDistributionIdDev = "E1AIDTCT83PAW5"
  s3BucketDev = "doevents-web-dev"
  region = $Region
  note = "Subir a GitHub environment dev como AWS_ACCESS_KEY_ID_DEV y AWS_SECRET_ACCESS_KEY_DEV. NO commitear."
}
$creds | ConvertTo-Json | Set-Content $OutFile -Encoding UTF8

Write-Host "Credenciales guardadas en: $OutFile" -ForegroundColor Green
Write-Host "Ejecuta despues: .\scripts\setup-github-secrets-dev.ps1 (con gh auth login)" -ForegroundColor Yellow
