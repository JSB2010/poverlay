param(
  [string]$AppExecutable = "",
  [string]$HealthUrl = "http://127.0.0.1:47981/health"
)

$ErrorActionPreference = "Stop"

function Test-WorkerHealth {
  try {
    $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
    return $response.name -eq "POVerlay Local Worker"
  } catch {
    return $false
  }
}

if (Test-WorkerHealth) {
  throw "Local worker health endpoint is already responding before app launch: $HealthUrl"
}

if (-not $AppExecutable) {
  $releaseRoot = Join-Path (Get-Location) "apps/desktop/src-tauri/target/release"
  $app = Get-ChildItem -Path $releaseRoot -File -Filter "*.exe" |
    Where-Object { $_.Name -notlike "poverlay-worker*" } |
    Select-Object -First 1
  if (-not $app) {
    throw "No desktop executable found in $releaseRoot"
  }
  $AppExecutable = $app.FullName
}

if (-not (Test-Path $AppExecutable)) {
  throw "Desktop executable not found: $AppExecutable"
}

$process = Start-Process -FilePath $AppExecutable -PassThru

try {
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    if ($process.HasExited) {
      throw "Desktop app exited before worker became healthy."
    }

    if (Test-WorkerHealth) {
      Write-Host "POVerlay Desktop launched worker successfully."
      exit 0
    }

    Start-Sleep -Seconds 1
  }

  throw "Timed out waiting for local worker health endpoint."
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  }

  Get-CimInstance Win32_Process -Filter "name = 'poverlay-worker.exe'" |
    Where-Object { $_.CommandLine -like "*serve*47981*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
