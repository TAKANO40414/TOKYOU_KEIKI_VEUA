#!/bin/bash
# PC5ビューア 起動スクリプト（Mac用）

DIR="$(cd "$(dirname "$0")" && pwd)"

# 既存プロセスを停止
lsof -ti :8765 | xargs kill -9 2>/dev/null
sleep 1

# 実行権限を付与（初回）
chmod +x "$DIR/PC5Viewer"

# libuvスレッドプールを拡張（ネットワークファイル並列アクセス対応）
export UV_THREADPOOL_SIZE=64

# 起動
exec "$DIR/PC5Viewer"
