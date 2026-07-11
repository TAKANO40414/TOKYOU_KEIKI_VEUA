@echo off
chcp 65001 >nul
title PC5 ビューア - インストーラー

echo ============================================================
echo   PC5 ビューア  インストール
echo ============================================================
echo.

:: 管理者権限チェック
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [情報] 管理者権限で再起動します...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set DEST=%ProgramFiles%\PC5Viewer

echo インストール先: %DEST%
echo.

:: フォルダ作成
if not exist "%DEST%" mkdir "%DEST%"

:: ファイルコピー
echo ファイルをコピー中...
copy /Y "%~dp0PC5Viewer.exe"     "%DEST%\PC5Viewer.exe"     >nul
copy /Y "%~dp0viewer.html"       "%DEST%\viewer.html"       >nul
copy /Y "%~dp0使い方.txt"        "%DEST%\使い方.txt"        >nul
copy /Y "%~dp0アンインストール.bat" "%DEST%\アンインストール.bat" >nul
echo [完了] ファイルコピー

:: デスクトップショートカット
echo デスクトップにショートカットを作成中...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\PC5ビューア.lnk'); ^
   $s.TargetPath = '%DEST%\PC5Viewer.exe'; ^
   $s.WorkingDirectory = '%DEST%'; ^
   $s.Description = 'PC5 検品データ ビューア'; ^
   $s.Save()"
echo [完了] デスクトップショートカット

:: スタートメニュー
echo スタートメニューに登録中...
set SMENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs
if not exist "%SMENU%\PC5Viewer" mkdir "%SMENU%\PC5Viewer"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SMENU%\PC5Viewer\PC5ビューア.lnk'); ^
   $s.TargetPath = '%DEST%\PC5Viewer.exe'; ^
   $s.WorkingDirectory = '%DEST%'; ^
   $s.Description = 'PC5 検品データ ビューア'; ^
   $s.Save()"
echo [完了] スタートメニュー登録

:: ファイアウォール
echo ファイアウォール例外を追加中...
netsh advfirewall firewall delete rule name="PC5Viewer" >nul 2>&1
netsh advfirewall firewall add rule ^
  name="PC5Viewer" ^
  dir=in action=allow ^
  program="%DEST%\PC5Viewer.exe" ^
  enable=yes >nul
echo [完了] ファイアウォール例外

:: アンインストール情報
set REGKEY=HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\PC5Viewer
reg add "%REGKEY%" /v "DisplayName"     /t REG_SZ    /d "PC5 ビューア"               /f >nul
reg add "%REGKEY%" /v "DisplayVersion"  /t REG_SZ    /d "2.1"                        /f >nul
reg add "%REGKEY%" /v "Publisher"       /t REG_SZ    /d "PC5Viewer"                  /f >nul
reg add "%REGKEY%" /v "InstallLocation" /t REG_SZ    /d "%DEST%"                     /f >nul
reg add "%REGKEY%" /v "UninstallString" /t REG_SZ    /d "%DEST%\アンインストール.bat" /f >nul
reg add "%REGKEY%" /v "NoModify"        /t REG_DWORD /d 1                            /f >nul
reg add "%REGKEY%" /v "NoRepair"        /t REG_DWORD /d 1                            /f >nul
echo [完了] アンインストール情報登録

echo.
echo ============================================================
echo   インストール完了！
echo   デスクトップの「PC5ビューア」をダブルクリックして起動してください。
echo   Python・Node.js 等のインストールは不要です。
echo ============================================================
echo.
pause
