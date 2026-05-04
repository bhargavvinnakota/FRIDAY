"""
Friday :: System R&D Skill
Deep integration with macOS via pyobjc and native system tools.
Bypasses the UI layer to interact with the OS kernel and App Dictionaries directly.
"""
from __future__ import annotations
import os
import subprocess
import json
from pathlib import Path
from typing import Any
from .registry import Skill, Operation, SkillResult

class SystemResearchSkill(Skill):
    name = "sys_research"
    description = "Deep macOS R&D: Log auditing, App API inspection, and native Cocoa interaction."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            "inspect_app_dictionary",
            "Retrieve the AppleScript dictionary (sdef) for an application to find hidden APIs.",
            fn=self.op_inspect_app_dictionary,
            risk="low",
            input_schema={"app_name": "Name of the app (e.g., 'Safari', 'Music')"}
        ))
        self.register_op(Operation(
            "query_unified_logs",
            "Query the macOS Unified Logging System for specific events.",
            fn=self.op_query_unified_logs,
            risk="medium",
            input_schema={"predicate": "Log predicate (e.g., 'process == \"Friday\"')", "last_minutes": "int"}
        ))
        self.register_op(Operation(
            "get_native_os_context",
            "Use Cocoa APIs to get deep system context (running apps, windows, energy state).",
            fn=self.op_get_native_os_context,
            risk="low"
        ))

    def op_inspect_app_dictionary(self, app_name: str = "", **_) -> SkillResult:
        if not app_name: return SkillResult(ok=False, error="app_name required")
        try:
            # Use sdef to get the dictionary
            cmd = f"sdef /Applications/{app_name}.app"
            if not Path(f"/Applications/{app_name}.app").exists():
                # Try to find it if it's not in /Applications
                cmd = f"sdef $(mdfind \"kMDItemCFBundleIdentifier == *\" | grep -i {app_name}.app | head -n 1)"
            
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                return SkillResult(ok=False, error=f"Could not find dictionary: {res.stderr}")
            
            # The output is XML. We'll return the first 5000 chars and a summary.
            return SkillResult(ok=True, data={
                "app": app_name,
                "dictionary_preview": res.stdout[:5000],
                "size": len(res.stdout)
            })
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_query_unified_logs(self, predicate: str = "", last_minutes: int = 5, **_) -> SkillResult:
        try:
            cmd = ["log", "show", "--predicate", predicate, "--last", f"{last_minutes}m", "--json"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode != 0:
                return SkillResult(ok=False, error=res.stderr)
            
            logs = json.loads(res.stdout)
            return SkillResult(ok=True, data={"count": len(logs), "events": logs[-20:]}) # Last 20 for preview
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_get_native_os_context(self, **_) -> SkillResult:
        try:
            from AppKit import NSWorkspace
            from Foundation import NSProcessInfo, NSBundle
            
            ws = NSWorkspace.sharedWorkspace()
            running_apps = [a.localizedName() for a in ws.runningApplications() if a.activationPolicy() == 0]
            front_app = ws.frontmostApplication().localizedName()
            
            pi = NSProcessInfo.processInfo()
            thermal_state = ["Nominal", "Fair", "Serious", "Critical"][pi.thermalState()]
            
            return SkillResult(ok=True, data={
                "frontmost_app": front_app,
                "running_gui_apps": running_apps,
                "thermal_state": thermal_state,
                "uptime": pi.systemUptime(),
                "is_low_power_mode": pi.isLowPowerModeEnabled() if hasattr(pi, 'isLowPowerModeEnabled') else "Unknown"
            })
        except Exception as e:
            return SkillResult(ok=False, error=str(e))
