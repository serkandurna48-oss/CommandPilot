# CommandPilot — Local Development
# Usage: .\start-dev.ps1
# Opens backend and frontend in separate terminals.
# Vercel deployment is unaffected (uses its own env vars from the Vercel dashboard).

$root = $PSScriptRoot

# Clear any shell-level env var overrides that shadow the .env file
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:SUPABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:SUPABASE_SERVICE_ROLE_KEY -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "CommandPilot — starting local dev environment" -ForegroundColor Cyan
Write-Host ""

# Backend — must run from backend/ so backend/.env is loaded by pydantic-settings
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$root\backend'; `$Host.UI.RawUI.WindowTitle = 'CP Backend :8000'; Write-Host 'Backend starting...' -ForegroundColor Cyan; '$root\.venv\Scripts\uvicorn.exe' app.main:app --reload --port 8000"
)

Start-Sleep -Seconds 1

# Frontend
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$root\frontend'; `$Host.UI.RawUI.WindowTitle = 'CP Frontend :3000'; Write-Host 'Frontend starting...' -ForegroundColor Green; npm run dev"
)

Write-Host "  Backend  -> http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Frontend -> http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "Both terminals are opening. Press Ctrl+C in each to stop." -ForegroundColor Gray
