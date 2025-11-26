<#
Publish the current project to GitHub.

Usage:
  .\scripts\publish_github.ps1 -RepoName AgenteScalping_V2 -Visibility private

Requires:
  - Git installed and available in PATH
  - GitHub CLI `gh` (recommended) and authenticated, or create the remote manually
#>

param(
  [string]$RepoName = "AgenteScalping_V2",
  [ValidateSet('public','private')][string]$Visibility = 'private'
)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "git is required. Install git and try again."; exit 1
}

if (-not (Test-Path .git)) {
  Write-Host "Initializing local git repository..."
  git init
}

git add -A
try { git commit -m "Prepare repository for publishing" } catch { Write-Host "Commit skipped (possibly no changes)" }

if (Get-Command gh -ErrorAction SilentlyContinue) {
  Write-Host "Creating repo via gh: $RepoName ($Visibility)"
  gh repo create $RepoName --$Visibility --source=. --remote=origin --push
} else {
  Write-Host "GitHub CLI not found. Please create a repo manually and set origin remote. Example:" -ForegroundColor Yellow
  Write-Host "git remote add origin git@github.com:<youruser>/$RepoName.git" -ForegroundColor Green
  Write-Host "git push -u origin main" -ForegroundColor Green
}

Write-Host "Finish. Check GitHub for repository $RepoName."
