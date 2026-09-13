#!/usr/bin/env bash

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$APP_DIR/MonsoonCast_Backend_and_Server"
PYTHON="$APP_DIR/.venv/bin/python3"

konsole --hold -e bash -c "
    cd \"$SERVER_DIR\" || exit 1
    \"$PYTHON\" server.py
"&

sleep 2

konsole --hold -e bash -c "
    ngrok http 5000 --url https://YOUR_.ngrok-free.dev
"&

sleep 2

konsole --hold -e bash -c "
    cd \"$SERVER_DIR/wa-bridge\" || exit 1
    node server.js
"&