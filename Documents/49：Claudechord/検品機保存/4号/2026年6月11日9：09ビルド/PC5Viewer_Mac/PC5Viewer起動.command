#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
lsof -ti :8765 | xargs kill -9 2>/dev/null
sleep 1
chmod +x "$DIR/PC5Viewer"
export UV_THREADPOOL_SIZE=64
exec "$DIR/PC5Viewer"
