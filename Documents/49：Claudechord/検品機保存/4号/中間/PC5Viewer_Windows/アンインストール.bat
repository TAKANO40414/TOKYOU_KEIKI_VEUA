@echo off
chcp 65001 >nul
title PC5 ビューア - アンインストーラー

:: 管理者権限チェック
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   PC5 ビューア  アンインストール
echo ============================================================
echo.

set /p CONFIRM=本当にアンインストールしますか？ (Y/N):
if /i not "%CONFIRM%"=="Y" (
    echo キャンセルしました。
    pause
    exit /b
)

set DEST=%ProgramFiles%\PC5Viewer

:: プロセス終了
taskkill /IM PC5Viewer.exe /F >nul 2>&1

:: ファイル削除
if exist "%DEST%" (
    rd /s /q "%DEST%"
    echo [完了] ファイルを削除しました
)

:: ショートカット削除
del /f "%USERPROFILE%\Desktop\PC5ビューア.lnk" >nul 2>&1
rd /s /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\PC5Viewer" >nul 2>&1
echo [完了] ショートカットを削除しました

:: ファイアウォール例外削除
netsh advfirewall firewall delete rule name="PC5Viewer" >nul 2>&1
echo [完了] ファイアウォール例外を削除しました

:: レジストリ削除
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\PC5Viewer" /f >nul 2>&1
echo [完了] レジストリを削除しました

echo.
echo ============================================================
echo   アンインストール完了！
echo ============================================================
pause
