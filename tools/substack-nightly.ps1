# Nightly (23:00): copy any new post from Allen Nelson's Substack to thingsabove.us, commit and push.
# Run by the Windows scheduled task "TAU Substack Import". Manual: powershell -File tools\substack-nightly.ps1 [-DryRun]
# Each new post is also listed in C:\code\quote-cards\tau\needs-quotes.md so a Claude session picks its quote cards.
# Skips the night (and says why in the log) if the repo is not clean on main, so it never commits someone else's work.
param([switch]$DryRun)

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$repo = Split-Path $PSScriptRoot -Parent
$logDir = Join-Path $env:LOCALAPPDATA "tau-substack"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "nightly.log"
$inbox = "C:\code\quote-cards\tau\needs-quotes.md"
$problems = @()
function Log($m) { $line = "{0:s} {1}" -f (Get-Date), $m; Add-Content $log $line; Write-Host $line }
function Finish {
  if ($problems.Count) {
    Log "PROBLEMS: $($problems -join '; ')"
    Add-Type -AssemblyName System.Windows.Forms
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon = [System.Drawing.SystemIcons]::Warning; $n.Visible = $true
    $n.ShowBalloonTip(15000, "TAU Substack import", "$($problems.Count) problem(s). See $log", "Warning")
    Start-Sleep 16; $n.Dispose()
  }
  Set-Content (Join-Path $logDir "last-run.txt") ("{0:s} {1}" -f (Get-Date), $(if ($problems.Count) { "PROBLEMS: $($problems -join '; ')" } else { "ok" }))
  Log "=== run done, $($problems.Count) problems"
  exit ($(if ($problems.Count) { 1 } else { 0 }))
}

Log "=== run start (DryRun=$DryRun)"
Set-Location $repo
$branch = git branch --show-current
if ($branch -ne "main") { $problems += "on branch '$branch', skipped"; Finish }
if (git status --porcelain) { $problems += "uncommitted changes in thingsabove.us, skipped tonight"; Finish }
git pull -q --rebase 2>&1 | ForEach-Object { Log "pull: $_" }
if ($LASTEXITCODE -ne 0) { git rebase --abort 2>$null; $problems += "git pull failed"; Finish }
if ([int](git rev-list --count "@{u}..HEAD") -gt 0) { $problems += "unpushed commits in thingsabove.us, skipped"; Finish }

$new = @(python tools/import_substack.py --list 2>&1)
if ($LASTEXITCODE -ne 0) { $new | ForEach-Object { Log "list: $_" }; $problems += "could not read the Substack"; Finish }
$new = @($new | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
if (-not $new.Count) { Log "nothing new"; Finish }
Log "new: $($new -join ', ')"
if ($DryRun) { Log "DRY RUN: would import $($new.Count) post(s)"; Finish }

$titles = @()
foreach ($slug in $new) {
  $out = @(python tools/import_substack.py $slug 2>&1)
  $ok = $LASTEXITCODE -eq 0
  $out | ForEach-Object { Log "${slug}: $_" }
  # add_post.py sometimes hits a briefly locked file on Windows; it is safe to re-run.
  for ($try = 1; -not $ok -and $try -le 2 -and (Test-Path (Join-Path $repo "$slug\index.html")); $try++) {
    Start-Sleep 20
    python tools/add_post.py $slug 2>&1 | ForEach-Object { Log "${slug} add_post retry ${try}: $_" }
    $ok = $LASTEXITCODE -eq 0
  }
  if (-not $ok) {
    $problems += "${slug}: import failed, nothing committed"
    git reset -q --hard HEAD; git clean -q -fd
    Finish
  }
  $m = $out | Where-Object { "$_" -like "${slug}: '*" } | Select-Object -First 1
  $titles += $(if ($m -match "^[^']*'(.+)', [A-Z][a-z]{2} \d") { $Matches[1] } else { $slug })
}

git add -A
git commit -q -m "Add from Allen Nelson's Substack: $($titles -join '; ')" 2>&1 | ForEach-Object { Log "commit: $_" }
git push -q 2>&1 | ForEach-Object { Log "push: $_" }
if ($LASTEXITCODE -ne 0) { $problems += "push failed (commit is local)" } else { Log "pushed: $($titles -join '; ')" }

if (-not (Test-Path $inbox)) { Set-Content $inbox "# TAU posts that need quote cards`n`nAdded by tools/substack-nightly.ps1 in thingsabove.us. Pick 1-2 quotes per post, get Michael's OK, make the cards, then delete the line.`n" -Encoding utf8 }
for ($i = 0; $i -lt $new.Count; $i++) { Add-Content $inbox ("- {0:yyyy-MM-dd} {1} ({2})" -f (Get-Date), $new[$i], $titles[$i]) -Encoding utf8 }
Finish
