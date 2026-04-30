import sys
import os
sys.path.insert(0, os.path.expanduser("~/AI"))
from friday.actions import comms

print("Attempting to send a test message to Telegram...")
try:
    res = comms.telegram_push("🤖 Omni-Daemon: Testing push capability.")
    print(f"Result: {res}")
except Exception as e:
    print(f"Error: {e}")
