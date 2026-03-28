#!/usr/bin/env python3
# install.py
# Version: 1.0.0
# Installs dependences needed for Dancy Pi (updated for Python 3 / Debian 12)
# Author: Nazmus Nasir
# Website: https://www.easyprogramming.net

import os
import sys
import subprocess
from datetime import datetime
import getpass

import platform
# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
LOG_PATH = os.path.join(REPO_ROOT, 'install.log')


def write_log(message: str):
    """Append a timestamped message to the install log."""
    ts = datetime.utcnow().isoformat() + 'Z'
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        # Best-effort logging; don't fail the installer if logging cannot write
        pass


def log_print(*args, **kwargs):
    """Print to stdout and also write the same message to the install log."""
    # Print to console
    print(*args, **kwargs)
    # Build a single-line message similar to print()
    sep = kwargs.get('sep', ' ')
    end = kwargs.get('end', '\n')
    try:
        message = sep.join(str(a) for a in args) + ('' if end == '\n' else end)
        write_log(message)
    except Exception:
        # Best-effort logging
        pass


def run_cmd(cmd: str, cwd: str = None):
    """Run shell command, log stdout/stderr and return CompletedProcess-like result.

    This uses subprocess.run to capture output so we can write a concise log entry.
    """
    write_log(f"RUN: {cmd}")
    try:
        completed = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        # Log return code and a short snippet of stdout/stderr
        out = (completed.stdout or '').strip()
        err = (completed.stderr or '').strip()
        write_log(f"RETURN {completed.returncode}: {cmd}")
        if out:
            write_log(f"STDOUT: {out}")
        if err:
            write_log(f"STDERR: {err}")
        return completed
    except Exception as exc:
        write_log(f"EXCEPTION running {cmd}: {exc}")
        # Mimic CompletedProcess with returncode 1
        class Dummy:
            def __init__(self):
                self.returncode = 1
                self.stdout = ''
                self.stderr = str(exc)

        return Dummy()


def install_dependencies():
    log_print("================== Start Installer (Debian 12 / Raspberry Pi checks) ==================")
    write_log("START install_dependencies")

    # Create venv early (preferred). create_venv will attempt to install python3-venv
    # via apt only if venv creation fails initially.
    write_log("STEP: create_venv")
    create_venv()

    # Log platform/architecture
    arch = platform.machine()
    write_log(f"PLATFORM: {platform.system()} {platform.release()} {arch}")

    # Update apt and install required system packages in one command
    write_log("STEP: apt update/install system packages")
    run_cmd("sudo apt update -y")
    apt_pkgs = [
        "build-essential",
        "python3-dev",
        "python3-venv",
        "python3-pip",
        "python3-setuptools",
        "python3-numpy",
        "python3-scipy",
        "python3-pyqt5",
        "python3-pyaudio",
        "python3-pyqtgraph",
        "libatlas-base-dev",
        "libatlas3-base",
        "libgfortran5",
        "portaudio19-dev",
        "libportaudio2",
        "libasound2-dev",
        "libffi-dev",
        "git",
    ]
    apt_cmd = "DEBIAN_FRONTEND=noninteractive sudo apt install -y " + " ".join(apt_pkgs)
    cp = run_cmd(apt_cmd)
    write_log(f"STEP_COMPLETE: apt install system packages (rc={cp.returncode})")

    log_print("================== System packages installed (see log for details) ==================")

    # Install/upgrades via pip inside the venv (preferred)
    pip_cmd = f"{VENV_PYTHON} -m pip" if VENV_PYTHON else "sudo python3 -m pip"

    log_print("================== Start Installing/Upgrading Python packages ==================")
    # numpy/scipy/pyaudio/pyqtgraph
    cp = run_cmd(f"{pip_cmd} install --upgrade numpy scipy pyaudio pyqtgraph")
    write_log(f"STEP_COMPLETE: pip upgrade numpy/scipy/pyaudio/pyqtgraph (rc={cp.returncode})")

    # rpi_ws281x only on Raspberry Pi hardware
    if is_raspberry_pi():
        write_log("Detected Raspberry Pi: installing rpi_ws281x")
        cp = run_cmd(f"{pip_cmd} install rpi_ws281x")
        write_log(f"STEP_COMPLETE: pip install rpi_ws281x (rc={cp.returncode})")
    else:
        write_log("Not Raspberry Pi: skipping rpi_ws281x installation")

    log_print("================== Completed Python package installation ==================")


def create_venv():
    """Create a Python 3 venv in the repository root at ./venv and set VENV_PYTHON.

    This will install python3-venv if necessary, create the venv, and upgrade pip/setuptools
    inside the venv. The global VENV_PYTHON variable will point to the venv's python.
    """
    global VENV_PYTHON
    # Default: no venv
    VENV_PYTHON = None

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
    venv_dir = os.path.join(repo_root, 'venv')

    # Ensure python3-venv is installed so venv creation works
    log_print("================== Ensuring python3-venv is installed ==================")
    cp = run_cmd("sudo apt install python3-venv -y")
    write_log(f"STEP_COMPLETE: apt install python3-venv (rc={cp.returncode})")

    # Create venv if it doesn't exist
    if not os.path.isdir(venv_dir):
        log_print(f"================== Creating virtual environment at {venv_dir} ==================")
        cp = run_cmd(f"python3 -m venv {sh_quote(venv_dir)}")
        if cp.returncode != 0:
            log_print("Failed to create venv; continuing without virtualenv.")
            write_log(f"ERROR: failed to create venv at {venv_dir} (rc={cp.returncode})")
            return
    else:
        log_print(f"Virtual environment already exists at {venv_dir}")

    # venv python executable
    venv_python = os.path.join(venv_dir, 'bin', 'python')
    if not os.path.exists(venv_python):
        log_print("venv python not found; continuing without virtualenv.")
        return

    VENV_PYTHON = venv_python
    log_print(f"Using venv python: {VENV_PYTHON}")

    # Upgrade pip, setuptools and wheel inside venv
    cp = run_cmd(f"{VENV_PYTHON} -m pip install --upgrade pip setuptools wheel")
    write_log(f"STEP_COMPLETE: upgrade pip/setuptools/wheel in venv (rc={cp.returncode})")


def sh_quote(path):
    """Simple sh-quoting for paths used in shell commands."""
    return '"' + path.replace('"', '\\"') + '"'


def is_raspberry_pi() -> bool:
    """Return True if running on Raspberry Pi hardware (best-effort).

    Checks /proc/device-tree/model, then /proc/cpuinfo, then platform hints.
    """
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().lower()
            if 'raspberry' in model:
                return True
    except Exception:
        pass

    try:
        with open('/proc/cpuinfo', 'r') as f:
            info = f.read().lower()
            if 'raspberry' in info:
                return True
    except Exception:
        pass

    # Fallback: check architecture and uname for hints
    arch = platform.machine().lower()
    uname = ' '.join(platform.uname()).lower()
    if ('arm' in arch or 'aarch64' in arch) and 'raspberry' in uname:
        return True

    return False


def ensure_not_running_as_root():
    """Refuse to run the installer as root.

    Running the entire installer as root will make the created virtualenv owned by root
    and may cause permission problems. The script will call `sudo` for commands that
    need elevation. Exit with an explanatory message if run as root.
    """
    # Determine if running as real root (geteuid) where available
    try:
        is_root = (os.geteuid() == 0)
    except AttributeError:
        is_root = False

    # Also detect sudo invocation via environment variables set by sudo
    invoked_via_sudo = bool(os.environ.get('SUDO_UID') or os.environ.get('SUDO_USER'))

    if is_root or invoked_via_sudo:
        msg = (
            "The installer must NOT be run as root or via sudo.\n"
            "Run it as your normal user; the script will call `sudo` for system operations.\n\n"
            "Example (from the repository root):\n"
            "  python3 python/install/install.py\n\n"
            "If you invoked this with sudo by mistake, re-run the installer as your normal user.\n"
        )
        log_print(msg)
        write_log("ERROR: installer invoked as root or via sudo; aborting.")
        sys.exit(1)


def ensure_user_can_sudo():
    """Ensure the current user can run sudo.

    First try a non-interactive check (`sudo -n true`). If that fails, attempt an
    interactive `sudo -v` to allow the user to enter their password. If both fail,
    exit with a helpful message.
    """
    # Don't check on Windows
    if os.name == 'nt':
        return

    # Non-interactive check (no password prompt)
    cp = run_cmd("sudo -n true")
    if getattr(cp, 'returncode', 1) == 0:
        write_log("SUDO: non-interactive sudo available")
        return

    # Try an interactive sudo to prompt for credentials. Use subprocess.run so the
    # user can enter a password interactively in the terminal.
    log_print("Sudo requires authentication. You may be prompted for your password...")
    write_log("SUDO: attempting interactive sudo -v")
    try:
        r = subprocess.run("sudo -v", shell=True)
        if r.returncode == 0:
            write_log("SUDO: interactive sudo successful")
            return
    except Exception as exc:
        write_log(f"SUDO: interactive sudo attempt raised exception: {exc}")

    # If we reach here, sudo isn't usable for this user
    msg = (
        "This user cannot run sudo or failed to authenticate.\n"
        "The installer needs sudo to install system packages. Ensure your user is in the sudoers group\n"
        "and can run `sudo`. You can test by running `sudo -v` manually.\n"
        "If you don't have sudo access, ask your administrator to install the required packages.\n"
    )
    log_print(msg)
    write_log("ERROR: user cannot run sudo; aborting.")
    sys.exit(1)


def replace_asound():
    log_print("================== Copying asound.conf ==================")
    src = os.path.join(SCRIPT_DIR, 'asound.conf')
    if not os.path.exists(src):
        log_print(f"Source asound.conf not found at {src}; skipping copy.")
        write_log(f"ERROR: asound.conf not found at {src}")
        return
    cp = run_cmd(f"sudo cp {sh_quote(src)} /etc/asound.conf")
    write_log(f"STEP_COMPLETE: copy asound.conf (rc={cp.returncode})")
    if cp.returncode != 0:
        log_print("Failed to copy asound.conf to /etc; check install.log for details.")
    else:
        log_print("================== Completed copying to /etc/asound.conf ==================")


def edit_alsa_conf():
    log_print("================== Creating backup of alsa.conf ==================")
    cp = run_cmd("sudo cp /usr/share/alsa/alsa.conf /usr/share/alsa/alsa.conf.bak")
    write_log(f"STEP_COMPLETE: backup alsa.conf (rc={cp.returncode})")
    if cp.returncode != 0:
        log_print("Failed to backup /usr/share/alsa/alsa.conf; aborting edit.")
        return

    log_print("================== Replacing text in alsa.conf ==================")
    try:
        with open('/usr/share/alsa/alsa.conf', 'r') as file:
            filedata = file.read()
    except Exception as exc:
        write_log(f"ERROR reading /usr/share/alsa/alsa.conf: {exc}")
        log_print("Failed to read /usr/share/alsa/alsa.conf; aborting edit.")
        return
        filedata = filedata.replace("defaults.ctl.card 0", "defaults.ctl.card 1")
        filedata = filedata.replace("defaults.pcm.card 0", "defaults.pcm.card 1")
        filedata = filedata.replace("pcm.front cards.pcm.front", "# pcm.front cards.pcm.front")
        filedata = filedata.replace("pcm.rear cards.pcm.rear", "# pcm.rear cards.pcm.rear")
        filedata = filedata.replace("pcm.center_lfe cards.pcm.center_lfe", "# pcm.center_lfe cards.pcm.center_lfe")
        filedata = filedata.replace("pcm.side cards.pcm.side", "# pcm.side cards.pcm.side")
        filedata = filedata.replace("pcm.surround21 cards.pcm.surround21", "# pcm.surround21 cards.pcm.surround21")
        filedata = filedata.replace("pcm.surround40 cards.pcm.surround40", "# pcm.surround40 cards.pcm.surround40")
        filedata = filedata.replace("pcm.surround41 cards.pcm.surround41", "# pcm.surround41 cards.pcm.surround41")
        filedata = filedata.replace("pcm.surround50 cards.pcm.surround50", "# pcm.surround50 cards.pcm.surround50")
        filedata = filedata.replace("pcm.surround51 cards.pcm.surround51", "# pcm.surround51 cards.pcm.surround51")
        filedata = filedata.replace("pcm.surround71 cards.pcm.surround71", "# pcm.surround71 cards.pcm.surround71")
        filedata = filedata.replace("pcm.iec958 cards.pcm.iec958", "# pcm.iec958 cards.pcm.iec958")
        filedata = filedata.replace("pcm.spdif iec958", "# pcm.spdif iec958")
        filedata = filedata.replace("pcm.hdmi cards.pcm.hdmi", "# pcm.hdmi cards.pcm.hdmi")
        filedata = filedata.replace("pcm.modem cards.pcm.modem", "# pcm.modem cards.pcm.modem")
        filedata = filedata.replace("pcm.phoneline cards.pcm.phoneline", "# pcm.phoneline cards.pcm.phoneline")
    # Write the modified file to a temp location then move it into place with sudo
    tmp_path = os.path.join(REPO_ROOT, 'alsa.conf.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as file:
            file.write(filedata)
    except Exception as exc:
        write_log(f"ERROR writing temp alsa.conf: {exc}")
        log_print("Failed to write temporary alsa.conf; aborting edit.")
        return

    cp = run_cmd(f"sudo cp {sh_quote(tmp_path)} /usr/share/alsa/alsa.conf")
    write_log(f"STEP_COMPLETE: write new alsa.conf (rc={cp.returncode})")
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    if cp.returncode != 0:
        log_print("Failed to replace /usr/share/alsa/alsa.conf; check install.log for details.")
    else:
        log_print("================== Completed replacing text in alsa.conf ==================")


def add_user_to_groups():
    """Add the current user to gpio,video,audio,plugdev using sudo.

    This attempts to run: sudo usermod -aG gpio,video,audio,plugdev <user>
    If successful, the user is informed they must log out/reboot for changes to take
    effect and is offered an immediate reboot prompt.
    """
    log_print("================== Adding current user to gpio,video,audio,plugdev groups ==================")
    try:
        user = os.environ.get('USER') or os.environ.get('LOGNAME') or getpass.getuser()
    except Exception:
        user = ''

    if not user:
        log_print("Could not determine current username; please run the following command manually:")
        log_print("  sudo usermod -aG gpio,video,audio,plugdev <your-username>")
        write_log("INFO: could not determine username for usermod step")
        return

    # Run the usermod command to add the user to the required groups
    cmd = f"sudo usermod -aG gpio,video,audio,plugdev {sh_quote(user)}"
    cp = run_cmd(cmd)
    write_log(f"STEP_COMPLETE: usermod add groups (rc={cp.returncode})")
    if getattr(cp, 'returncode', 1) != 0:
        log_print("Failed to add user to groups automatically. Please run the following command manually:")
        log_print(f"  sudo usermod -aG gpio,video,audio,plugdev {user}")
        return

    log_print("User added to groups successfully.")
    log_print("You need to log out and back in for group membership to take effect, or you can reboot now.")
    try:
        ans = input("Reboot now? [y/N]: ").strip().lower()
    except Exception:
        ans = 'n'

    if ans in ('y', 'yes'):
        log_print("Rebooting now...")
        run_cmd("sudo reboot")
    else:
        log_print("Skipping reboot. Please log out and back in for group changes to take effect.")


if __name__ == '__main__':
    ensure_not_running_as_root()
    ensure_user_can_sudo()
    install_dependencies()
    replace_asound()
    edit_alsa_conf()
    add_user_to_groups()
