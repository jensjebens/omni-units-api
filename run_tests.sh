#!/usr/bin/env bash
# Run Units API tests against packman USD (no Kit runtime required).
# This validates the library logic; Kit-specific integration (omni.kit.test)
# can be tested when deployed into an actual KAT workspace.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USD=/home/horde/.cache/packman/chk/usd.py312.manylinux_2_35_x86_64.stock.release/0.25.11.kit.1-gl.18239+b8f43314
PYTHON=/home/horde/.cache/packman/chk/python/3.12.10+nv1-linux-x86_64/bin/python3.12
EXT_DIR="$SCRIPT_DIR/source/extensions/omni.units_api"

export PYTHONPATH="$USD/lib/python:$EXT_DIR:$PYTHONPATH"
export LD_LIBRARY_PATH="$USD/lib:$LD_LIBRARY_PATH"
export PXR_PLUGINPATH_NAME="$USD/lib/usd"

echo "Python: $($PYTHON --version)"
echo "USD: $($PYTHON -c 'from pxr import Usd; print(Usd.GetVersion())')"
echo "Running tests..."
echo ""

$PYTHON -m pytest "$EXT_DIR/tests/" -v --tb=short "$@"
