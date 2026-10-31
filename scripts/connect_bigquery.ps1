param([switch]$RunPipeline)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$cloudCommand = Get-Command gcloud.cmd -ErrorAction SilentlyContinue
$cloudPath = if ($cloudCommand) { $cloudCommand.Source } else {
    Join-Path $env:TEMP 'music-promotion-tools\google-cloud-sdk\bin\gcloud.cmd'
}
if (-not (Test-Path -LiteralPath $cloudPath)) {
    throw 'Install the Google Cloud CLI: https://cloud.google.com/sdk/docs/install'
}

& $cloudPath auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform
if ($LASTEXITCODE -ne 0) { throw 'Google sign-in did not complete.' }
$env:GCP_PROJECT_ID = 'music-promotion-experiment-lab'
& $cloudPath auth application-default set-quota-project $env:GCP_PROJECT_ID
if ($LASTEXITCODE -ne 0) { throw 'Could not set the project; check IAM permissions.' }

if ($RunPipeline) {
    Push-Location $projectRoot
    try {
        & (Join-Path $projectRoot '.venv\Scripts\python.exe') scripts/run_pipeline.py --target bigquery
        if ($LASTEXITCODE -ne 0) { throw 'BigQuery pipeline failed; inspect the error above.' }
    } finally {
        Pop-Location
    }
}
