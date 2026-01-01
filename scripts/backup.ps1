# === yp-ver2 remote snapshot (runtime timestamp) ===
param(
  [string]$Src = 'C:\users\user\desktop\yp-ver2',
  [string]$Dst = "$env:UserProfile\OneDrive\Backups\yp-ver2",
  [int]$Keep = 30  # keep last N archives
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Dst | Out-Null

# runtime timestamp
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$zip   = Join-Path $Dst ("yp-ver2_{0}.zip" -f $stamp)

# exclusions
$files = Get-ChildItem $Src -Recurse -File | Where-Object {
    $_.FullName -notmatch '\\venv\\' -and
    $_.FullName -notmatch '\\__pycache__\\' -and
    $_.Extension -notin '.db','.sqlite','.sqlite3','.pyc','.pyo' -and
    $_.Name -notmatch '(\.db-wal|\.db-shm|\.db-journal)$'
}

# archive
if ($files) {
    Compress-Archive -Path $files.FullName -DestinationPath $zip -Force
} else {
    Set-Content -Path $zip -Value '' -Encoding Byte
}

# log
"$([DateTime]::Now.ToString('s')) :: OK :: $zip :: $(Get-Item $zip).Length bytes" |
  Out-File -FilePath (Join-Path $Dst 'backup.log') -Append -Encoding utf8

# retention
Get-ChildItem $Dst -Filter 'yp-ver2_*.zip' |
  Sort-Object LastWriteTime -Desc |
  Select-Object -Skip $Keep |
  Remove-Item -Force -ErrorAction SilentlyContinue