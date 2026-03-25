#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec "$SCRIPT_DIR/kit/kit" \
    --empty \
    --ext-path "$ROOT_DIR/source/extensions/omni.units_api" \
    --ext-folder "$SCRIPT_DIR/extscache" \
    --enable omni.kit.test \
    --enable omni.units_api \
    --/app/enableStdoutOutput=1 \
    --/app/window/enabled=false \
    --/app/asyncRendering=false \
    --/exts/omni.kit.test/testExts/0='omni.units_api' \
    --/exts/omni.kit.test/testExtOutputPath="$ROOT_DIR/_testoutput" \
    --no-window \
    "$@"
