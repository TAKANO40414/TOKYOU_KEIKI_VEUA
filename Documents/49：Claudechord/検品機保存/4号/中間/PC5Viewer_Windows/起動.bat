@echo off
chcp 65001 >nul
title PC5 ビューア

echo ============================================================
echo   PC5 ビューア  起動チェック中...
echo ============================================================
echo.

:: ─────────────────────────────────────────────
:: 1. Python の確認
:: ─────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [情報] Python が見つかりません。インストールを開始します...
    echo       （インターネット接続が必要です）
    echo.

    :: winget でインストール試行
    winget --version >nul 2>&1
    if %errorlevel% equ 0 (
        winget install --id Python.Python.3.11 ^
              --accept-source-agreements ^
              --accept-package-agreements ^
              --silent
    ) else (
        echo [エラー] winget が使用できません。
        echo 以下のURLから Python を手動でインストールしてください：
        echo   https://www.python.org/downloads/
        echo.
        echo ★ インストール時に「Add Python to PATH」に必ずチェックを入れてください ★
        echo.
        pause
        exit /b 1
    )

    :: インストール後に PATH を再読み込み
    call RefreshEnv.cmd >nul 2>&1
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo [注意] Python のインストールは完了しましたが、
        echo        このウィンドウを一旦閉じて「起動.bat」を再度実行してください。
        pause
        exit /b 0
    )
    echo [完了] Python のインストールが完了しました。
    echo.
)

:: ─────────────────────────────────────────────
:: 2. Flask の確認・インストール
:: ─────────────────────────────────────────────
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [情報] Flask をインストールしています...
    python -m pip install flask --quiet --disable-pip-version-check
    if %errorlevel% neq 0 (
        echo [エラー] Flask のインストールに失敗しました。
        echo ネットワーク接続を確認してから再度実行してください。
        pause
        exit /b 1
    )
    echo [完了] Flask のインストールが完了しました。
    echo.
)

:: ─────────────────────────────────────────────
:: 3. ポート解放（前回の残留プロセスを終了）
:: ─────────────────────────────────────────────
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8765 " 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: ─────────────────────────────────────────────
:: 4. アプリ起動
:: ─────────────────────────────────────────────
echo ============================================================
echo   PC5 ビューア を起動しています...
echo   ブラウザが自動で開きます。
echo   開かない場合 → http://localhost:8765 を手動で開いてください
echo.
echo   終了するにはこのウィンドウを閉じてください (Ctrl+C でも可)
echo ============================================================
echo.

:: このバッチファイルと同じフォルダを既定の検索フォルダとして渡す
python "%~dp0pc5_web_viewer.py" "%~dp0"

pause
