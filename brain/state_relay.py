"""
Friday :: State Relay
Bridges the Python Daemon and the Native SwiftUI HUD via local JSON state.
"""
import json
import os
from pathlib import Path

STATE_FILE = Path("/Users/bhargav/AI/friday/native_hud/Resources/hud_state.json")
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

def update_hud_state(status="IDLE", user_input="", friday_output="", telemetry=None, intel_card=None):
    state = {
        "status": status,
        "user_input": user_input,
        "friday_output": friday_output,
        "intel_card": intel_card,
        "telemetry": telemetry or {
            "cpu": 10,
            "ram": 45,
            "stability": 99.1
        }
    }
    # Atomic write
    temp_file = STATE_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(state, f)
    os.rename(temp_file, STATE_FILE)

if __name__ == "__main__":
    update_hud_state(status="IDLE", user_input="", friday_output="SYSTEM_READY")
    print(f"HUD State Initialized at {STATE_FILE}")
