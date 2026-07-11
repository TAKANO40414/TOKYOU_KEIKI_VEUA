@echo off
chcp 932 >/dev/null
title PC5Viewer - Uninstaller

net session >/dev/null 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   PC5Viewer  Uninstall
echo ============================================================

set /p CONFIRM=Uninstall PC5Viewer? (Y/N): 
if /i not "%CONFIRM%"=="Y" (
    echo Cancelled.
    pause
    exit /b
)

set DEST=%ProgramFiles%\PC5Viewer

taskkill /IM PC5Viewer.exe /F >/dev/null 2>&1
if exist "%DEST%" rd /s /q "%DEST%"
del /f "%USERPROFILE%\Desktop\PC5Viewer.lnk" >/dev/null 2>&1
rd /s /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\PC5Viewer" >/dev/null 2>&1
netsh advfirewall firewall delete rule name="PC5Viewer" >/dev/null 2>&1
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\PC5Viewer" /f >/dev/null 2>&1

echo.
echo ============================================================
echo   Uninstall complete!
echo ============================================================
pause
