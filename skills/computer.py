from __future__ import annotations
import os
from pathlib import Path
from .registry import Skill, Operation, SkillResult
from friday.actions import computer

class ComputerSkill(Skill):
    name = "computer"
    description = "Interact with the macOS desktop: take screenshots, open apps, type, and navigate."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            name="take_screenshot",
            description="Take a screenshot of the main display.",
            fn=self.op_take_screenshot,
            risk="low",
            input_schema={}
        ))
        self.register_op(Operation(
            name="open_app",
            description="Open a macOS application by name.",
            fn=self.op_open_app,
            risk="low",
            input_schema={"app_name": "Name of the application (e.g. 'Terminal', 'Safari', 'Cursor')"}
        ))
        self.register_op(Operation(
            name="type_text",
            description="Type text as if using the keyboard.",
            fn=self.op_type_text,
            risk="medium",
            input_schema={"text": "The text to type."}
        ))
        self.register_op(Operation(
            name="press_key",
            description="Press a special key (e.g., 'return', 'tab', 'esc').",
            fn=self.op_press_key,
            risk="medium",
            input_schema={"key": "The name of the key (return, tab, space, escape, up, down, left, right, delete)."}
        ))
        self.register_op(Operation(
            name="browser_open",
            description="Open a URL in the default browser.",
            fn=self.op_browser_open,
            risk="medium",
            input_schema={"url": "The URL to open."}
        ))

    def op_take_screenshot(self, **_) -> SkillResult:
        save_dir = Path(os.path.expanduser("~/AI/friday/data/screenshots"))
        save_dir.mkdir(parents=True, exist_ok=True)
        import time
        ts = int(time.time())
        filepath = save_dir / f"screen_{ts}.png"
        res = computer.take_screenshot(str(filepath))
        if res.get("ok"):
            return SkillResult(ok=True, data={"path": str(filepath)}, artifacts=[str(filepath)])
        return SkillResult(ok=False, error=res.get("error"))

    def op_open_app(self, app_name: str, **_) -> SkillResult:
        res = computer.open_app(app_name)
        return SkillResult(ok=res.get("ok", False), data=res, error=res.get("error"))

    def op_type_text(self, text: str, **_) -> SkillResult:
        res = computer.type_text(text)
        return SkillResult(ok=res.get("ok", False), data=res, error=res.get("error"))

    def op_press_key(self, key: str, **_) -> SkillResult:
        res = computer.press_key(key)
        return SkillResult(ok=res.get("ok", False), data=res, error=res.get("error"))

    def op_browser_open(self, url: str, **_) -> SkillResult:
        res = computer.shell(f"open '{url}'")
        return SkillResult(ok=res.get("ok", False), data=res, error=res.get("stderr"))
