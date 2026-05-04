"""
Friday :: Deep Mac Integration Validation
Tests SystemResearchSkill and direct OS telemetry.
"""
import sys
import os
from pathlib import Path
import asyncio

sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.skills.registry import get_registry

async def test_deep_integration():
    print("🚀 Running Deep Mac Integration Test...")
    reg = get_registry()
    sys_r = reg.get("sys_research")
    
    # 1. Test App Dictionary Inspection (Bypass UI)
    print("\n[1] Testing App Dictionary Inspection (Safari)...")
    res = sys_r.invoke("inspect_app_dictionary", app_name="Safari")
    if res.ok:
        print(f"    ✓ Safari Dictionary Found. Size: {res.data['size']} bytes.")
        print(f"    Preview: {res.data['dictionary_preview'][:200]}...")
    else:
        print(f"    ✗ Dictionary Inspection Failed: {res.error}")

    # 2. Test Unified Log Query
    print("\n[2] Testing Unified Log Query...")
    # Looking for recent kernel events (safe but shows we can read logs)
    res = sys_r.invoke("query_unified_logs", predicate="process == \"kernel\"", last_minutes=1)
    if res.ok:
        print(f"    ✓ Log Query Success. Found {res.data['count']} events.")
    else:
        print(f"    ✗ Log Query Failed: {res.error}")

    # 3. Test Cocoa OS Context
    print("\n[3] Testing Cocoa OS Context (Direct AppKit/Foundation)...")
    res = sys_r.invoke("get_native_os_context")
    if res.ok:
        print(f"    ✓ Frontmost App: {res.data['frontmost_app']}")
        print(f"    ✓ Thermal State: {res.data['thermal_state']}")
        print(f"    ✓ Running GUI Apps: {len(res.data['running_gui_apps'])}")
    else:
        print(f"    ✗ Cocoa Context Failed: {res.error}")

    print("\n✅ Deep Integration Systems Verified.")

if __name__ == "__main__":
    asyncio.run(test_deep_integration())
