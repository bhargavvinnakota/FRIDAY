"""
Friday :: Computer Control
Shell execution (allowlist-gated) + macOS AppleScript bridge.
Safety: destructive commands blocked, high-risk commands require confirmation.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path


DESTRUCTIVE_PATTERNS = [
    "rm -rf", "rm -r /", "> /", ":(){ :|:& };:", "mkfs", "dd if=",
    "curl | sh", "wget | sh", "chmod -R 777 /", "shutdown", "reboot",
    "sudo rm", "format", "diskutil eraseDisk",
]

SAFE_COMMANDS = {
    "ls", "pwd", "whoami", "date", "uptime", "df", "du", "ps", "top",
    "cat", "head", "tail", "grep", "find", "which", "echo",
    "python3", "python", "pip", "pip3", "node", "npm",
    "ollama", "git", "pm2",
}


def _is_safe(cmd: str) -> tuple[bool, str]:
    low = cmd.lower().strip()
    for pat in DESTRUCTIVE_PATTERNS:
        if pat in low:
            return False, f"blocked: destructive pattern '{pat}'"
    first = low.split()[0] if low else ""
    first_bin = first.split("/")[-1]
    if first_bin not in SAFE_COMMANDS and not first_bin.startswith("git"):
        return False, f"blocked: '{first_bin}' not in allowlist. Ask Bhargav to confirm."
    return True, "ok"


def shell(cmd: str, timeout: int = 30, force: bool = False) -> dict:
    """Run a shell command. Returns {ok, stdout, stderr, code}."""
    if not force:
        safe, reason = _is_safe(cmd)
        if not safe:
            return {"ok": False, "stdout": "", "stderr": reason, "code": -1}
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": r.returncode == 0,
            "stdout": r.stdout[:4000],
            "stderr": r.stderr[:2000],
            "code": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "code": -2}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "code": -3}


def applescript(script: str, timeout: int = 15) -> dict:
    """Run an AppleScript. macOS only."""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
        return {"ok": r.returncode == 0, "output": r.stdout.strip(), "error": r.stderr.strip()}
    except Exception as e:
        return {"ok": False, "output": "", "error": str(e)}


def notify(title: str, message: str, sound: str = "default") -> dict:
    """macOS notification."""
    safe_title = title.replace('"', "'")
    safe_msg = message.replace('"', "'")
    script = f'display notification "{safe_msg}" with title "{safe_title}" sound name "{sound}"'
    return applescript(script)


def open_app(app_name: str) -> dict:
    """Open a macOS application by name (e.g. 'Terminal', 'Slack', 'Cursor')."""
    safe = app_name.replace('"', "")
    return applescript(f'tell application "{safe}" to activate')


def say(text: str, voice: str = "Moira", rate: int = 160) -> dict:
    """Use macOS `say` for quick TTS (no extra deps). Defaults to Moira (Irish female)."""
    safe = text.replace('"', "'")
    try:
        subprocess.run(["say", "-v", voice, "-r", str(rate), safe], timeout=60)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def take_screenshot(filepath: str) -> dict:
    """Capture the main screen to a file."""
    try:
        r = subprocess.run(["screencapture", "-x", filepath], capture_output=True, text=True, timeout=10)
        return {"ok": r.returncode == 0, "error": r.stderr}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def type_text(text: str) -> dict:
    """Type text via AppleScript."""
    safe_text = text.replace('\\', '\\\\').replace('"', '\\"')
    script = f'tell application "System Events" to keystroke "{safe_text}"'
    return applescript(script)


def press_key(key: str) -> dict:
    """Press a key via AppleScript."""
    k = key.lower()
    if k in ["return", "enter"]:
        script = 'tell application "System Events" to keystroke return'
    elif k == "tab":
        script = 'tell application "System Events" to keystroke tab'
    elif k == "space":
        script = 'tell application "System Events" to keystroke space'
    elif k in ["esc", "escape"]:
        script = 'tell application "System Events" to key code 53'
    elif k in ["delete", "backspace"]:
        script = 'tell application "System Events" to key code 51'
    elif k == "up":
        script = 'tell application "System Events" to key code 126'
    elif k == "down":
        script = 'tell application "System Events" to key code 125'
    elif k == "left":
        script = 'tell application "System Events" to key code 123'
    elif k == "right":
        script = 'tell application "System Events" to key code 124'
    else:
        script = f'tell application "System Events" to keystroke "{k}"'
    return applescript(script)


if __name__ == "__main__":
    print(shell("ls ~/AI/friday"))
    print(shell("rm -rf /"))  # should block
    notify("Friday", "Boot sequence complete.")
