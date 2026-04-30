from __future__ import annotations
import os
import re
import json
from pathlib import Path
from datetime import datetime
from .registry import Skill, Operation, SkillResult

PLAN_DIR = Path(os.path.expanduser("~/AI/nexus-omega"))
WAR_MAP_PATH = PLAN_DIR / "WAR_MAP_360.md"
EXECUTION_PLAN_PATH = PLAN_DIR / "MASTER_EXECUTION_PLAN.md"

class EmpireSkill(Skill):
    name = "empire"
    description = "Chief of Staff operations: monitors the Master Execution Plan, tracks mission milestones, and enforces the Daily Operating System."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            name="mission_status",
            description="Get a high-level briefing on the current phase and progress of the empire mission.",
            fn=self.op_mission_status,
            risk="low"
        ))
        self.register_op(Operation(
            name="check_schedule",
            description="Check the current time against the Daily Operating System and suggest focus.",
            fn=self.op_check_schedule,
            risk="low"
        ))
        self.register_op(Operation(
            name="milestone_report",
            description="Identify upcoming or missed milestones from the War Map.",
            fn=self.op_milestone_report,
            risk="low"
        ))
        self.register_op(Operation(
            name="the_one_question",
            description="Ask the 'One Question' that drives the mission: what's the single action today for ₹25L/month?",
            fn=self.op_one_question,
            risk="low"
        ))

    def op_mission_status(self, **_) -> SkillResult:
        if not WAR_MAP_PATH.exists():
            return SkillResult(ok=False, error="War Map (WAR_MAP_360.md) not found.")
        
        content = WAR_MAP_PATH.read_text()
        phase_match = re.search(r"## CURRENT PHASE: (.*?)\n", content)
        phase = phase_match.group(1) if phase_match else "Unknown"
        
        # Extract today's priority
        priority_match = re.search(r"\*\*Today's priority\*\*: (.*?)\.", content)
        priority = priority_match.group(1) if priority_match else "Not set"
        
        # Extract built components (quick counts)
        built_count = len(re.findall(r"\| ✅ Built", content)) + len(re.findall(r"\| ✅ Tested", content))
        
        return SkillResult(ok=True, data={
            "phase": phase,
            "priority": priority,
            "infrastructure_ready_count": built_count,
            "message": f"We are currently in {phase}. Today's priority is: {priority}. We have {built_count} infrastructure components online."
        })

    def op_check_schedule(self, **_) -> SkillResult:
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        day_of_week = now.strftime("%A")
        
        # Rules from identity.yaml and War Map
        schedule = {
            "06:00": "Morning Briefing",
            "06:15": "Content Block (LinkedIn)",
            "06:45": "Trading Check",
            "07:00": "Client Check",
            "09:00": "Day Job (SOX Coaching) - LOCKED",
            "18:00": "BUILD BLOCK",
            "20:00": "Dinner Break",
            "20:30": "SELL BLOCK (Outreach)",
            "22:00": "NEXUS Evolution",
            "22:30": "Sleep"
        }
        
        # Find the current or next block
        focus = "Off-schedule"
        for time_str, task in sorted(schedule.items()):
            if current_time_str >= time_str:
                focus = task
        
        if day_of_week == "Sunday":
            focus = "Sunday Rest (Non-negotiable)"
            
        return SkillResult(ok=True, data={
            "current_time": current_time_str,
            "day": day_of_week,
            "suggested_focus": focus,
            "message": f"It's {current_time_str} on a {day_of_week}. According to your Daily OS, you should be in the {focus} phase."
        })

    def op_milestone_report(self, **_) -> SkillResult:
        if not WAR_MAP_PATH.exists():
            return SkillResult(ok=False, error="War Map not found.")
            
        content = WAR_MAP_PATH.read_text()
        milestones = []
        # Parse Milestone Ledger table
        matches = re.findall(r"\| (.*?) \| (.*?) \| (.*?) \| (.*?) \|", content)
        for m in matches:
            name, target, actual, delta = [x.strip() for x in m]
            if name == "Milestone" or name.startswith("---"): continue
            milestones.append({"name": name, "target": target, "actual": actual or "Pending"})
            
        return SkillResult(ok=True, data={
            "milestones": milestones,
            "message": f"I've tracked {len(milestones)} major milestones. The next big target is {milestones[0]['name']} by {milestones[0]['target']}." if milestones else "No milestones found."
        })

    def op_one_question(self, **_) -> SkillResult:
        question = "What's the single action today that gets us closer to ₹25L/month?"
        return SkillResult(ok=True, data={
            "question": question,
            "voice_prompt": f"Boss, {question}"
        })
