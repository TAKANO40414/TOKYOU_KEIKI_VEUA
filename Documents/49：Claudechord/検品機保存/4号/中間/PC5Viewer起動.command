#!/bin/bash
# PC5ビューア 起動スクリプト

# 既存のサーバーを停止
lsof -ti :8765 | xargs kill -9 2>/dev/null
sleep 1

# スクリプトと同じ場所に移動
cd "$(dirname "$0")"

# サーバー起動
python3 "$(dirname "$0")/2026May15/pc5_web_viewer.py" "$(dirname "$0")/2026May15"
