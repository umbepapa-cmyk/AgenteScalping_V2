# Package project for FileZilla upload
# Creates a zip archive containing only necessary files (excludes .venv and .git)
# Usage: run from project root in PowerShell:
#   .\.venv\Scripts\Activate.ps1
#   .\package_for_filezilla.ps1 -OutZip ..\AgenteScalping_deploy.zip
param(
    [string]$OutZip = "..\AgenteScalping_deploy.zip",
    [string[]]$Include = @("*.py", "*.md", "requirements.txt", "config.ini", "readme.md"),
    [string[]]$ExcludeDirs = @('.venv', '.git'),
    [string[]]$ExcludeFiles = @('.env', '*.env', 'Scalping_V2.txt', '*.pem', '*.key')
)
Write-Host "Packaging project into $OutZip"
# Build list of files
$root = Get-Location
$files = @()
foreach ($pattern in $Include) {
    $files += Get-ChildItem -Path $root -Recurse -Include $pattern -File -ErrorAction SilentlyContinue | Where-Object {
        foreach ($ed in $ExcludeDirs) { if ($_.FullName -like "*\\$ed\\*") { return $false } }
        foreach ($ef in $ExcludeFiles) { if ($_.Name -like $ef) { return $false } }
        return $true
    }
}
# Ensure config and readme always included (but never include actual .env)
$config = Join-Path $root 'config.ini'
$readme = Join-Path $root 'readme.md'
if (Test-Path $config -PathType Leaf) { $files += Get-Item $config }
if (Test-Path $readme -PathType Leaf) { $files += Get-Item $readme }
$envExample = Join-Path $root '.env.example'
if (Test-Path $envExample -PathType Leaf) { $files += Get-Item $envExample }
$files = $files | Sort-Object -Unique
if (-Not $files) { Write-Error "No files found to package."; exit 1 }
# Create temp folder
$temp = Join-Path $env:TEMP ("agente_deploy_" + [System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $temp | Out-Null
foreach ($f in $files) {
    $dest = Join-Path $temp ($f.FullName.Substring($root.Path.Length).TrimStart('\'))
    New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
    Copy-Item -Path $f.FullName -Destination $dest -Force
}
Compress-Archive -Path (Join-Path $temp '*') -DestinationPath $OutZip -Force
Remove-Item -Recurse -Force $temp
Write-Host "Packaged $($files.Count) files into $OutZip"