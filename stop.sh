#!/bin/bash

echo "🛑 Stopping Women's Safety System..."

if [ -f server.pid ]; then
    PID=$(cat server.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "✅ Server stopped (PID: $PID)"
    else
        echo "⚠️  Process $PID not running"
    fi
    rm -f server.pid
else
    echo "⚠️  No server.pid found"
    # Fallback: find process on port 8000
    PID=$(lsof -t -i:8000 2>/dev/null)
    if [ -n "$PID" ]; then
        kill "$PID"
        echo "✅ Killed process on port 8000 (PID: $PID)"
    else
        echo "ℹ️  No process found on port 8000"
    fi
fi
