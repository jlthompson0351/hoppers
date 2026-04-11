$ErrorActionPreference = 'SilentlyContinue'
$projName = (Get-Item .).Name

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "      PROJECT PULSE: $projName" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Git Status
Write-Host "--- GIT HEALTH ---" -ForegroundColor Yellow
if (Test-Path ".git") {
    $branch = git branch --show-current 2>$null
    $gitStatus = git status --porcelain 2>$null
    if ([string]::IsNullOrWhiteSpace($gitStatus)) {
        Write-Host "✅ Clean ($branch)" -ForegroundColor Green
    } else {
        $changeCount = ($gitStatus | Measure-Object -Line).Lines
        Write-Host "⚠️ $changeCount uncommitted changes ($branch)" -ForegroundColor Red
        git status -s | Select-Object -First 5
        if ($changeCount -gt 5) { Write-Host "   ...and more" -ForegroundColor DarkGray }
    }
} else {
    Write-Host "❌ Not a Git repository" -ForegroundColor DarkGray
}
Write-Host ""

# 2. Next TODOs
Write-Host "--- NEXT ACTIONS (TODO.md) ---" -ForegroundColor Yellow
if (Test-Path "TODO.md") {
    # Get the first 5 unchecked boxes
    $todos = Select-String -Path "TODO.md" -Pattern "\[ \]" | Select-Object -First 5
    if ($todos) {
        foreach ($todo in $todos) {
            Write-Host $todo.Line.Trim() -ForegroundColor White
        }
    } else {
        Write-Host "No pending tasks found or TODO.md is empty." -ForegroundColor Green
    }
} else {
    Write-Host "TODO.md not found." -ForegroundColor DarkGray
}
Write-Host ""

# 3. Handoff Status
Write-Host "--- CURRENT HANDOFF STATUS ---" -ForegroundColor Yellow
if (Test-Path "HANDOFF.md") {
    # Grab the first 10 non-empty lines of HANDOFF.md
    $handoff = Get-Content "HANDOFF.md" | Select-Object -First 10
    foreach ($line in $handoff) {
        if (-not [string]::IsNullOrWhiteSpace($line)) {
            Write-Host $line -ForegroundColor Gray
        }
    }
    Write-Host "..." -ForegroundColor DarkGray
} else {
    Write-Host "HANDOFF.md not found." -ForegroundColor DarkGray
}
Write-Host ""

# 4. Recent Chat Compressions (Last 2 hours)
Write-Host "--- ACTIVE TRAIN OF THOUGHT ---" -ForegroundColor Yellow
$compressedPath = Join-Path (Get-Location) ".cursor\memory\sessions\latest-compressed-chat.md"
if (Test-Path $compressedPath) {
    $lastWrite = (Get-Item $compressedPath).LastWriteTime
    if ($lastWrite -gt (Get-Date).AddHours(-2)) {
        Write-Host "[🔔 RECENT COMPRESSED CHAT FOUND]" -ForegroundColor Magenta
        Write-Host "File: $compressedPath" -ForegroundColor White
        Write-Host "Last Updated: $($lastWrite.ToString('HH:mm'))" -ForegroundColor Gray
        Write-Host "-> The agent should read this file immediately to resume the exact train of thought." -ForegroundColor Cyan
    } else {
        Write-Host "No active compressed chats in the last 2 hours." -ForegroundColor DarkGray
    }
} else {
    Write-Host "No active compressed chats." -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
