"""
Friday :: Native Mac Motor (PyObjC Edition)
Deep system control via native Cocoa and Accessibility APIs.
"""
from __future__ import annotations
import objc
from AppKit import NSWorkspace, NSScreen
from Accessibility import (
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementPerformAction,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXTitleAttribute,
    kAXValueAttribute,
    kAXPressAction
)
from .registry import Skill, Operation, SkillResult
import subprocess
import json

class MacSkill(Skill):
    name = "mac"
    description = "God-Tier macOS control using native Accessibility and AppKit APIs."

    def _register_operations(self) -> None:
        self.register_op(Operation("get_active_app", "Get info about the frontmost application.",
                                   fn=self.op_get_active_app, risk="low"))
        self.register_op(Operation("read_ui_tree", "Read the semantic UI tree of the active app.",
                                   fn=self.op_read_ui_tree, risk="medium"))
        self.register_op(Operation("click_element", "Click a UI element by its title or role.",
                                   fn=self.op_click_element, risk="high"))
        self.register_op(Operation("get_sys_telemetry", "Get native system stats (Battery, CPU, Memory).",
                                   fn=self.op_get_sys_telemetry, risk="low"))

    def op_get_active_app(self, **_) -> SkillResult:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return SkillResult(ok=True, data={
            "name": app.localizedName(),
            "bundle_id": app.bundleIdentifier(),
            "pid": app.processIdentifier()
        })

    def op_read_ui_tree(self, max_depth: int = 2, **_) -> SkillResult:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        app_ref = AXUIElementCreateApplication(app.processIdentifier())
        
        def traverse(element, depth):
            if depth > max_depth: return []
            nodes = []
            error, children = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute, None)
            if error == 0 and children:
                for child in children:
                    _, role = AXUIElementCopyAttributeValue(child, kAXRoleAttribute, None)
                    _, title = AXUIElementCopyAttributeValue(child, kAXTitleAttribute, None)
                    nodes.append({
                        "role": str(role),
                        "title": str(title) if title else "",
                        "children": traverse(child, depth + 1)
                    })
            return nodes

        tree = traverse(app_ref, 0)
        return SkillResult(ok=True, data={"app": app.localizedName(), "ui_tree": tree})

    def op_click_element(self, target_title: str = "", target_role: str = "", **_) -> SkillResult:
        if not target_title and not target_role:
            return SkillResult(ok=False, error="Target title or role required.")
            
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        app_ref = AXUIElementCreateApplication(app.processIdentifier())
        
        found = []
        def find(element):
            error, children = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute, None)
            if error == 0 and children:
                for child in children:
                    _, role = AXUIElementCopyAttributeValue(child, kAXRoleAttribute, None)
                    _, title = AXUIElementCopyAttributeValue(child, kAXTitleAttribute, None)
                    
                    match = True
                    if target_title and str(target_title).lower() not in str(title).lower(): match = False
                    if target_role and str(target_role).lower() not in str(role).lower(): match = False
                    
                    if match:
                        found.append(child)
                        return
                    find(child)
        
        find(app_ref)
        if found:
            err = AXUIElementPerformAction(found[0], kAXPressAction)
            return SkillResult(ok=(err == 0), data={"status": "Action performed" if err == 0 else f"Error: {err}"})
            
        return SkillResult(ok=False, error="Element not found.")

    def op_get_sys_telemetry(self, **_) -> SkillResult:
        # Using NSScreen and native Cocoa-friendly calls
        screens = NSScreen.screens()
        main_screen = NSScreen.mainScreen()
        
        # CPU/Battery fallback to shell for simplicity, but wrapped in native context
        bat = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout.strip()
        
        return SkillResult(ok=True, data={
            "screen_count": len(screens),
            "resolution": f"{main_screen.frame().size.width}x{main_screen.frame().size.height}",
            "battery": bat
        })
