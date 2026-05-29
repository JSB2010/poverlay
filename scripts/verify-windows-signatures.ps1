param(
  [Parameter(Mandatory = $true)]
  [string]$Path
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Path)) {
  throw "Signature verification path does not exist: $Path"
}

$artifacts = Get-ChildItem -Path $Path -Recurse -File |
  Where-Object { $_.Extension -in @(".exe", ".msi") }

if (-not $artifacts) {
  throw "No Windows EXE/MSI artifacts found under $Path"
}

foreach ($artifact in $artifacts) {
  $signature = Get-AuthenticodeSignature -FilePath $artifact.FullName
  if ($signature.Status -ne "Valid") {
    throw "Invalid signature for $($artifact.FullName): $($signature.Status) $($signature.StatusMessage)"
  }
  Write-Host "Valid signature: $($artifact.FullName)"
}
