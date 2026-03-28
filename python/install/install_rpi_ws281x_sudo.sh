#!/usr/bin/env bash
# install_rpi_ws281x_sudo.sh
# Build and install rpi_ws281x system-wide (uses sudo) and install Python bindings
# into the project's virtualenv. This script will:
#  - create backups and snapshots for rollback
#  - install required apt build dependencies
#  - clone/update the rpi_ws281x repo
#  - build with USE_GPIOMEM (prefers /dev/gpiomem)
#  - run `sudo scons install` to install system libraries/headers
#  - install Python bindings into the project's venv
#
# Usage (from repo root):
#   chmod +x python/install/install_rpi_ws281x_sudo.sh
#   python/install/install_rpi_ws281x_sudo.sh
#
# WARNING: this script will use sudo to install system packages and write to /usr/local.
# It records installed files and creates a tar backup of your project + venv so you can
# roll back if needed.

set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RPI_WS_REPO="$HOME/rpi_ws281x"
VENV_PY="$REPO_ROOT/venv/bin/python"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$REPO_ROOT/install/rpi_ws281x_sudo_install_${TIMESTAMP}.log"
BACKUP_TAR="$HOME/dancyPi_backup_${TIMESTAMP}.tar.gz"
SNAP_BEFORE="/tmp/ws_before_${TIMESTAMP}.txt"
SNAP_AFTER="/tmp/ws_after_${TIMESTAMP}.txt"
INSTALLED_LIST="$HOME/rpi_ws281x_installed_files_${TIMESTAMP}.txt"

mkdir -p "$REPO_ROOT/install"
exec > >(tee -a "$LOG") 2>&1

echo "rpi_ws281x sudo-enabled installer"
echo "Log: $LOG"

die() { echo "ERROR: $*" >&2; exit 1; }

# Basic checks
if [ ! -x "$VENV_PY" ]; then
  die "Virtualenv python not found at $VENV_PY. Create the venv first."
fi

# Ask to continue
read -r -p "This script will install packages with sudo and modify /usr/local. Continue? [y/N]: " yn
case "$yn" in
  [Yy]|[Yy][Ee][Ss]) ;;
  *) echo "Aborted by user."; exit 0 ;;
esac

# Backup project + venv
echo "Creating tar backup of project and venv (may take some time): $BACKUP_TAR"
tar -czf "$BACKUP_TAR" -C "$HOME" "$(basename "$REPO_ROOT")" --warning=no-file-changed || die "Failed to create backup tarball"

# Snapshot current /usr/local for later diff
{
  echo "==== /usr/local/lib (matching ws2811/rpi_ws281x) ===="
  find /usr/local/lib -type f -iname '*ws2811*' -o -iname '*rpi_ws281x*' 2>/dev/null || true
  echo "==== /usr/local/include (matching ws2811) ===="
  find /usr/local/include -type f -iname '*ws2811*' -o -iname '*rpi_ws281x*' 2>/dev/null || true
  echo "==== /usr/local/bin ===="
  find /usr/local/bin -maxdepth 1 -type f -iname '*ws2811*' -o -iname '*rpi_ws281x*' 2>/dev/null || true
} > "$SNAP_BEFORE" || true

# Install apt build deps
echo "Installing build dependencies via apt (sudo required)"
sudo apt update
sudo apt install -y git build-essential python3-dev python3-pip python3-setuptools swig scons pkg-config libffi-dev || die "Failed to install build dependencies"

# Clone or update rpi_ws281x
if [ -d "$RPI_WS_REPO" ]; then
  echo "Updating existing repo at $RPI_WS_REPO"
  (cd "$RPI_WS_REPO" && git fetch --all && git reset --hard origin/master && git pull) || echo "Warning: git update failed"
else
  echo "Cloning rpi_ws281x into $RPI_WS_REPO"
  git clone https://github.com/jgarff/rpi_ws281x.git "$RPI_WS_REPO" || die "git clone failed"
fi

# Build with USE_GPIOMEM
cd "$RPI_WS_REPO"
export CFLAGS="-DUSE_GPIOMEM"
export CXXFLAGS="$CFLAGS"

# Build using scons or make
if [ -f SConstruct ] && command -v scons >/dev/null 2>&1; then
  echo "Building with scons"
  scons || die "scons build failed"
elif [ -f Makefile ]; then
  echo "Building with make"
  make || die "make build failed"
else
  die "No SConstruct or Makefile found at top-level; aborting"
fi

# Install native library into system (sudo)
echo "Installing native library into system (/usr/local)"
sudo scons install || sudo make install || die "sudo install failed"

# Install Python bindings into venv
if [ -d "$RPI_WS_REPO/python" ]; then
  PY_DIR="$RPI_WS_REPO/python"
else
  # try to find setup.py
  PY_SETUP_PATH=$(find "$RPI_WS_REPO" -maxdepth 4 -type f -name setup.py -print | head -n 1 || true)
  if [ -n "$PY_SETUP_PATH" ]; then
    PY_DIR=$(dirname "$PY_SETUP_PATH")
  else
    die "Could not find Python bindings in the rpi_ws281x repo"
  fi
fi

# Record venv pip before
echo "Recording pip packages before install"
"$VENV_PY" -m pip freeze > "$REPO_ROOT/install/pip_packages_before_${TIMESTAMP}.txt"

# Install into venv
echo "Installing Python bindings into venv"
"$VENV_PY" -m pip install --upgrade pip setuptools wheel
"$VENV_PY" -m pip install "$PY_DIR" || die "pip install of python bindings failed"

# Snapshot /usr/local after install
{
  echo "==== AFTER /usr/local/lib (matching ws2811/rpi_ws281x) ===="
  find /usr/local/lib -type f -iname '*ws2811*' -o -iname '*rpi_ws281x*' 2>/dev/null || true
  echo "==== AFTER /usr/local/include ===="
  find /usr/local/include -type f -iname '*ws2811*' -o -iname '*rpi_ws281x*' 2>/dev/null || true
  echo "==== AFTER /usr/local/bin ===="
  find /usr/local/bin -maxdepth 1 -type f -iname '*ws2811*' -o -iname '*rpi_ws281x*' 2>/dev/null || true
} > "$SNAP_AFTER" || true

# Compute installed files diff
comm -23 <(sort "$SNAP_AFTER") <(sort "$SNAP_BEFORE") > "$INSTALLED_LIST" || true

echo "Installed file list saved to: $INSTALLED_LIST"

# Verify import
"$VENV_PY" -c "import rpi_ws281x; print('rpi_ws281x module:', rpi_ws281x.__file__)" || die "Import test failed"

cat <<EOF

SUCCESS: rpi_ws281x built and installed system-wide and Python bindings installed into venv.

Rollback options:
- To uninstall the python package from venv:
    "$VENV_PY" -m pip uninstall rpi-ws281x rpi_ws281x -y || true
- To remove installed system files (review list before running):
    sudo xargs -a $INSTALLED_LIST -r rm -v
- To restore project/venv from the backup:
    tar -xzf "$BACKUP_TAR" -C "$HOME"

Log: $LOG
EOF

exit 0
