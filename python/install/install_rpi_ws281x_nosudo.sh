#!/usr/bin/env bash
# install_rpi_ws281x_nosudo.sh
# Build rpi_ws281x locally and install Python bindings into the project's venv
# without using sudo or modifying system directories (/usr/local).
#
# Usage (from repo root):
#   chmod +x python/install/install_rpi_ws281x_nosudo.sh
#   python/install/install_rpi_ws281x_nosudo.sh
#
# Notes:
# - This script assumes core build tools (gcc/make or scons, python dev headers) are
#   already installed on the system. If they are not, you will need to install them
#   (apt install build-essential python3-dev swig pkg-config) which requires sudo.
# - The script builds the C library locally (no sudo) and installs the Python
#   package into the virtualenv located at ./venv (relative to repo root).
# - The script is idempotent and safe: it will not modify /usr/local or /usr/bin.
# - To roll back: uninstall the rpi_ws281x wheel from the venv and restore any saved
#   pre-install pip freeze output (this script records the before/after state).

set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_PY="$REPO_ROOT/venv/bin/python"
RPI_WS_REPO="$HOME/rpi_ws281x"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$REPO_ROOT/install/rpi_ws281x_nosudo_${TIMESTAMP}.log"
PREV_PKGS="$REPO_ROOT/install/pip_packages_before_${TIMESTAMP}.txt"
POST_PKGS="$REPO_ROOT/install/pip_packages_after_${TIMESTAMP}.txt"

mkdir -p "$REPO_ROOT/install"
exec > >(tee -a "$LOG") 2>&1

echo "No-sudo rpi_ws281x build/install script"
echo "Repo root: $REPO_ROOT"

# Check venv python
if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: virtualenv python not found at $VENV_PY"
  echo "Create the venv first (run the project's installer or python -m venv ./venv)"
  exit 1
fi

# Check for required build tools (non-sudo). If missing, instruct the user to
# install them using apt (requires sudo) and abort.
if ! command -v gcc >/dev/null 2>&1; then
  echo "ERROR: gcc not found. Please install build-essential (sudo apt install build-essential) and retry."
  exit 1
fi

# Detect builder: prefer scons if present
USE_SCONS=0
if command -v scons >/dev/null 2>&1 && [ -f "$RPI_WS_REPO/SConstruct" ]; then
  USE_SCONS=1
fi

# Save current venv pip packages for rollback
echo "Recording current pip packages into $PREV_PKGS"
"$VENV_PY" -m pip freeze > "$PREV_PKGS"

# Clone or update rpi_ws281x repository locally
if [ -d "$RPI_WS_REPO" ]; then
  echo "Updating existing rpi_ws281x repo at $RPI_WS_REPO"
  (cd "$RPI_WS_REPO" && git fetch --all && git reset --hard origin/master && git pull) || echo "Warning: git update failed; continuing with local copy"
else
  echo "Cloning rpi_ws281x into $RPI_WS_REPO"
  git clone https://github.com/jgarff/rpi_ws281x.git "$RPI_WS_REPO"
fi

# Configure compile-time define to prefer gpiomem
export CFLAGS="-DUSE_GPIOMEM"
export CXXFLAGS="$CFLAGS"

# Build native library locally (no install into /usr/local)
cd "$RPI_WS_REPO"

# Try to locate a build driver (SConstruct or Makefile) anywhere under the repo
echo "Searching for SConstruct/Makefile under $RPI_WS_REPO (depth 3)"
BUILD_DRIVER_PATH=$(find "$RPI_WS_REPO" -maxdepth 3 \( -name SConstruct -o -name Makefile \) -print | head -n 1 || true)
if [ -z "$BUILD_DRIVER_PATH" ]; then
  echo "No SConstruct or Makefile found in $RPI_WS_REPO (searched depth 3)."
  echo "Listing top-level files:"; ls -la "$RPI_WS_REPO"
  echo "You can inspect the rpi_ws281x repo layout. If build files are deeper, re-run this script or adjust the depth."
  exit 1
fi

BUILD_DIR=$(dirname "$BUILD_DRIVER_PATH")
echo "Found build driver at: $BUILD_DRIVER_PATH (building in $BUILD_DIR)"
cd "$BUILD_DIR"

# Decide whether to use scons or make based on the found file and availability
if [ -f "SConstruct" ] && command -v scons >/dev/null 2>&1; then
  echo "Using scons to build in $BUILD_DIR"
  scons || { echo "scons build failed"; exit 1; }
elif [ -f "Makefile" ]; then
  echo "Using make to build in $BUILD_DIR"
  make || { echo "make build failed"; exit 1; }
else
  echo "Found build file but no supported builder available in PATH (scons/make)."; exit 1
fi

# At this point native library artifacts are built under the repo (commonly in build/) and headers are available
# We will install the Python bindings into the venv using pip; pip will compile/extension modules linking
# to the local repo files. Set environment variables so the compiler/linker can find headers/libs.
BUILD_DIR="$RPI_WS_REPO/build"
if [ ! -d "$BUILD_DIR" ]; then
  # Some repo versions place built libs at the repo root or other path. Try a few common locations.
  if [ -d "$RPI_WS_REPO/ws2811" ]; then
    BUILD_DIR="$RPI_WS_REPO"
  else
    echo "Warning: expected build dir $RPI_WS_REPO/build not found. Continuing; pip build may still find sources."
  fi
fi

# Export library/header search paths to help extension build
export LIBRARY_PATH="$BUILD_DIR:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="$BUILD_DIR:${LD_LIBRARY_PATH:-}"
export CPATH="$RPI_WS_REPO:${CPATH:-}"
export C_INCLUDE_PATH="$RPI_WS_REPO:${C_INCLUDE_PATH:-}"

# Install python bindings into venv using pip (editable install avoids touching system)
# Locate the python bindings directory (where setup.py lives). Repo layouts vary.
echo "Locating python bindings (setup.py) under $RPI_WS_REPO"
PY_SETUP_PATH=$(find "$RPI_WS_REPO" -maxdepth 4 -type f -name setup.py -print | head -n 1 || true)
if [ -n "$PY_SETUP_PATH" ]; then
  PY_DIR=$(dirname "$PY_SETUP_PATH")
  echo "Found python setup at: $PY_SETUP_PATH (using $PY_DIR)"
else
  # Fallback to conventional location
  if [ -d "$RPI_WS_REPO/python" ]; then
    PY_DIR="$RPI_WS_REPO/python"
    echo "Using conventional python dir: $PY_DIR"
  else
    echo "ERROR: Could not find setup.py or python/ directory in rpi_ws281x repo."
    echo "Repo contents:"; ls -la "$RPI_WS_REPO"
    exit 1
  fi
fi
cd "$PY_DIR"
# Ensure pip/setuptools are recent inside venv
"$VENV_PY" -m pip install --upgrade pip setuptools wheel

# Build & install into venv. Use pip to record metadata so uninstall is easy.
echo "Installing rpi_ws281x Python package into venv using pip (no sudo)"
"$VENV_PY" -m pip install . || { echo "pip install failed"; exit 1; }

# Record packages after install
"$VENV_PY" -m pip freeze > "$POST_PKGS"

echo "Installation complete. Verifying module import inside venv..."
"$VENV_PY" -c "import rpi_ws281x; print('rpi_ws281x module loaded from', rpi_ws281x.__file__)" || { echo "Import test failed"; exit 1; }

cat <<EOF

SUCCESS: rpi_ws281x appears installed into the venv without modifying system directories.

Rollback instructions (if you want to undo the pip install):
  "$VENV_PY" -m pip uninstall rpi-ws281x rpi_ws281x -y || true
  # Optionally restore previous pip packages state (reinstall from $PREV_PKGS):
  # "$VENV_PY" -m pip install -r "$PREV_PKGS"

Notes:
- This script did not run sudo and did not modify /usr/local. If the extension build fails due to missing system development packages
  (e.g. python3-dev, build-essential, swig), install them with sudo (or run the script I provided earlier which can install deps).
- If runtime still tries to use /dev/mem, you may still need to run the system-level build/install with sudo to place libraries in system paths,
  or use pigpio as an alternative backend.

Log file: $LOG

EOF

exit 0
