#!/bin/sh
set -eu
cd "$(dirname "$0")"
echo "=== $(date -Is) : forecast refresh ==="
source ".venv/bin/activate"
python3 MonsoonCast_Backend_and_Server/main.py --locations MonsoonCast_Backend_and_Server/locations.json --output-dir MonsoonCast_Backend_and_Server/data
echo "=== refresh complete ==="
echo "you can now start the server"