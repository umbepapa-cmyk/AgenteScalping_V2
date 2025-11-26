<#
Create a GitHub repository using the token in environment variable GITHUB_TOKEN (or in .env)

Usage: .\scripts\create_github_repo.ps1 -RepoName AgenteScalping_V2 -Visibility private

This script calls the GitHub REST API to create a repo under the authenticated user,
then configures the local git remote and pushes the code. It expects `git` and `curl`.
Be careful: storing tokens in .env is convenient but treat them as secrets.
#>

param(
    [string]$RepoName = "AgenteScalping_V2",
    [ValidateSet('private','public')][string]$Visibility = 'private'
)

if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^GITHUB_TOKEN=(.*)$') { $env:GITHUB_TOKEN = $Matches[1].Trim('"') }
    }
}

if (-not $env:GITHUB_TOKEN) {
    Write-Error "GITHUB_TOKEN not found in environment or .env"; exit 2
}

$headers = @{ Authorization = "token $($env:GITHUB_TOKEN)"; Accept = 'application/vnd.github+json' }
$body = @{ name = $RepoName; private = ($Visibility -eq 'private') } | ConvertTo-Json

Write-Host "Retrieving authenticated user..."
try {
  $user = Invoke-RestMethod -Uri https://api.github.com/user -Headers $headers -Method Get
} catch {
  Write-Error "Unable to determine user from token: $($_.Exception.Message)"; exit 3
}
if (-not $user.login) { Write-Error "Unable to determine user from token"; exit 3 }
$owner = $user.login
Write-Host "Authenticated as $owner"

Write-Host "Creating repo $owner/$RepoName ($Visibility)"
$resp = Invoke-RestMethod -Method Post -Uri https://api.github.com/user/repos -Headers $headers -Body $body
if ($resp.full_name -ne "$owner/$RepoName") { Write-Warning "Unexpected response from GitHub API" }

if (-not (Test-Path .git)) { git init }
git add -A
try { git commit -m "Initial commit" } catch { Write-Host "Commit skipped" }

$remoteUrl = "https://github.com/$owner/$RepoName.git"
git remote remove origin -ErrorAction SilentlyContinue
git remote add origin $remoteUrl

Write-Host "Pushing to remote (using token for authentication)"
$authUrl = "https://$($env:GITHUB_TOKEN)@github.com/$owner/$RepoName.git"
try {
  git push -u $authUrl main
} catch {
  git push -u $authUrl master
}

Write-Host "Done. Repository: https://github.com/$owner/$RepoName"
