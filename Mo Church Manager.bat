@echo off
rem Double-click to start Church Manager. Keep this window open while you work.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py app.py %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Khong tim thay Python. Hay cai Python theo Buoc 1 trong README.md.
    pause
    exit /b 1
  )
  python app.py %*
)
pause
