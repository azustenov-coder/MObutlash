@echo off
if "%~1"=="" (
    set commit_message=Auto-update
) else (
    set commit_message=%*
)

git add .
git commit -m "%commit_message%"
git push
echo ✅ GitHub-ga muvaffaqiyatli yuklandi!
