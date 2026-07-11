@echo off
chcp 65001 >nul
title PC5Viewer - Installer

echo ============================================================
echo   PC5Viewer  Install
echo ============================================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [Info] 管理者権限で再起動中...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set DEST=%ProgramFiles%\PC5Viewer

echo インストール先: %DEST%
echo.

if not exist "%DEST%" mkdir "%DEST%"

echo ファイルをコピー中...
copy /Y "%~dp0PC5Viewer.exe"      "%DEST%\PC5Viewer.exe"      >nul
copy /Y "%~dp0PC5Viewer起動.bat"  "%DEST%\PC5Viewer起動.bat"  >nul
copy /Y "%~dp0viewer.html"        "%DEST%\viewer.html"        >nul
copy /Y "%~dp0readme.txt"         "%DEST%\readme.txt"         >nul
copy /Y "%~dp0uninstall.bat"      "%DEST%\uninstall.bat"      >nul
echo [完了] ファイルコピー

echo デスクトップショートカットを作成中...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\PC5Viewer.lnk'); ^
   $s.TargetPath = '%DEST%\PC5Viewer起動.bat'; ^
   $s.WorkingDirectory = '%DEST%'; ^
   $s.Description = 'PC5 Viewer'; ^
   $s.Save()"
echo [完了] デスクトップショートカット

echo スタートメニューに追加中...
set SMENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs
if not exist "%SMENU%\PC5Viewer" mkdir "%SMENU%\PC5Viewer"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SMENU%\PC5Viewer\PC5Viewer.lnk'); ^
   $s.TargetPath = '%DEST%\PC5Viewer起動.bat'; ^
   $s.WorkingDirectory = '%DEST%'; ^
   $s.Description = 'PC5 Viewer'; ^
   $s.Save()"
echo [完了] スタートメニュー

echo ファイアウォール例外を追加中...
netsh advfirewall firewall delete rule name="PC5Viewer" >nul 2>&1
netsh advfirewall firewall add rule ^
  name="PC5Viewer" dir=in action=allow ^
  program="%DEST%\PC5Viewer.exe" enable=yes >nul
echo [完了] ファイアウォール

set REGKEY=HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\PC5Viewer
reg add "%REGKEY%" /v "DisplayName"     /t REG_SZ    /d "PC5 Viewer"                       /f >nul
reg add "%REGKEY%" /v "DisplayVersion"  /t REG_SZ    /d "3.0"                              /f >nul
reg add "%REGKEY%" /v "Publisher"       /t REG_SZ    /d "PC5Viewer"                        /f >nul
reg add "%REGKEY%" /v "InstallLocation" /t REG_SZ    /d "%DEST%"                           /f >nul
reg add "%REGKEY%" /v "UninstallString" /t REG_SZ    /d "%DEST%\uninstall.bat"             /f >nul
reg add "%REGKEY%" /v "NoModify"        /t REG_DWORD /d 1                                  /f >nul
reg add "%REGKEY%" /v "NoRepair"        /t REG_DWORD /d 1                                  /f >nul
echo [完了] アンインストール登録

echo.
echo ============================================================
echo   インストール完了！
echo   デスクトップの「PC5Viewer」をダブルクリックして起動。
echo   Python・Node.js のインストール不要。
echo ============================================================
echo.
pause
