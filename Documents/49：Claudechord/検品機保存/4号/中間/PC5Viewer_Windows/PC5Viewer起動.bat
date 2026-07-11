@echo off
chcp 65001 >nul
title PC5 ビューア

:: ─── ポート解放 ───
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8765 "') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: ─── Python を探す ───
set PYTHON=
for %%p in (python3.exe python.exe) do (
    where %%p >nul 2>&1 && set PYTHON=%%p && goto :found_python
)
:: py ランチャー
where py >nul 2>&1 && set PYTHON=py && goto :found_python

echo [エラー] Python が見つかりません。
echo.
echo Python をインストールしてください:
echo   https://www.python.org/downloads/
echo.
echo インストール時に「Add Python to PATH」にチェックを入れてください。
pause
exit /b 1

:found_python
echo [OK] Python: %PYTHON%

:: ─── Flask インストール確認 ───
%PYTHON% -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [情報] Flask をインストール中...
    %PYTHON% -m pip install flask --quiet
    if %errorlevel% neq 0 (
        echo [エラー] Flask のインストールに失敗しました。
        pause
        exit /b 1
    )
    echo [OK] Flask インストール完了
)

:: ─── サーバー起動 ───
set SCRIPT=%~dp0pc5_web_viewer.py
if not exist "%SCRIPT%" (
    echo [エラー] pc5_web_viewer.py が見つかりません。
    echo 場所: %SCRIPT%
    pause
    exit /b 1
)

echo [起動] PC5 ビューア を起動中...
start "" %PYTHON% "%SCRIPT%"
