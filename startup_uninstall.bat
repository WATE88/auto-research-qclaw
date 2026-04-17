@echo off
chcp 65001 >nul 2>&1
echo 正在移除 AutoResearch 开机自启...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "AutoResearch" /f >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AutoResearch.bat" >nul 2>&1
echo [OK] 开机自启已移除。
pause
