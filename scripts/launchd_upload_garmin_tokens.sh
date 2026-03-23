#!/bin/bash
# launchd から呼ばれるラッパースクリプト
# .zprofile から export 行を抽出して環境変数をロードする

set -euo pipefail

LOG_FILE="/tmp/upload-garmin-tokens.log"
PROJECT_DIR="$HOME/Personal_Projects/run-coach"

{
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="

    # .zprofile から export 文のみ抽出してロード（zsh固有コマンドを回避）
    eval "$(grep '^export ' "$HOME/.zprofile")"

    # homebrew の PATH を設定
    eval "$(/opt/homebrew/bin/brew shellenv)"

    cd "$PROJECT_DIR"
    /opt/homebrew/bin/uv run python -m scripts.upload_garmin_tokens

    echo "完了"
    echo ""
} >> "$LOG_FILE" 2>&1
