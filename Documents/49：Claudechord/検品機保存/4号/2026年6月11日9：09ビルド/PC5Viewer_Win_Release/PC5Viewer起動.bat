@echo off
chcp 65001 >nul
title PC5 ビューア

:: ─── スレッドプール拡張（ネットワークファイル高速化） ───
set UV_THREADPOOL_SIZE=64

:: ─── 既存プロセスを停止 ───
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8765 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: ─── 起動 ───
set DIR=%~dp0
start "" "%DIR%PC5Viewer.exe"
