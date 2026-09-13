#!/usr/bin/env bash

set -e

# Always work from the directory containing this script.
APP_DIR="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1
    pwd
)"

VENV_DIR="$APP_DIR/.venv"
PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"

echo "========================================"
echo "       MonsoonCast Environment Setup"
echo "========================================"
echo
echo "Project directory: $APP_DIR"
echo

# Check that Python 3 is available.
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 was not found."
    echo "Please install Python 3 and run this script again."
    exit 1
fi

# Create the virtual environment if it does not already exist.
if [[ ! -x "$PYTHON" ]]; then
    echo "[1/3] Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/3] .venv already exists. Reusing it."
fi

# Make sure pip exists and is usable inside the venv.
echo "[2/3] Preparing pip..."
"$PYTHON" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$PYTHON" -m pip install --upgrade pip

# Run requirements.sh from inside the virtual environment.
# This means commands such as `python`, `pip`, etc. used by that script
# will resolve to the newly created .venv.
if [[ -f "$APP_DIR/requirements.sh" ]]; then
    echo
    echo "[3/3] Running requirements.sh..."
    (
        source "$VENV_DIR/bin/activate"
        bash "$APP_DIR/requirements.sh"
    )
else
    echo
    echo "WARNING: requirements.sh was not found."
    echo "Skipping it."
fi

# Install Python dependencies into THIS virtual environment.
if [[ -f "$APP_DIR/requirements.txt" ]]; then
    echo
    echo "Installing Python dependencies from requirements.txt..."
    "$PIP" install -r "$APP_DIR/requirements.txt"
else
    echo
    echo "WARNING: requirements.txt was not found."
    echo "No Python packages were installed from requirements.txt."
fi

echo
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo
echo "Virtual environment:"
echo "  $VENV_DIR"
echo
echo "Python:"
echo "  $PYTHON"
echo
echo "To activate it manually:"
echo "  source .venv/bin/activate"
echo
echo "You can now run refresh_daily.sh"