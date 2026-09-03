#!/usr/bin/env bash
# Low-res sweep of every cover concept, for side-by-side comparison.
#   ./sweep_cover.sh [test|preview|4k]
set -u
BLENDER="/c/Program Files/Blender Foundation/Blender 4.5/blender.exe"
export SCIBLEND_DIR="C:\\Users\\crg17\\OneDrive - Imperial College London\\meshes\\HCM\\sciblend"
QUALITY="${1:-test}"

run() {
  echo "--- $1 floor=$2 ($QUALITY)"
  "$BLENDER" --background --factory-startup --python cover_render.py -- "$1" "floor=$2" "$QUALITY" \
    2>&1 | grep -E "^\[geom\]|^\[mirror\]|^COVER DONE|Error"
}

run arc    grid
run tree   grid
run tree   tree
run mirror grid
echo "=== sweep complete ==="
