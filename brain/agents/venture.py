"""
Friday V2.5 :: Company-Level Orchestration
Coordinates multiple RoleAgents to execute high-level business objectives using a BabyAGI-inspired loop.
"""
import json
from typing import List, Dict
from friday.brain.agents.roles import CEOAgent, EngineerAgent, GrowthAgent
from friday.skills.registry import get_registry
from friday.brain.v2_memory import VectorMemory
from friday.brain.state_relay import update_hud_state

class VentureOrchestrator:
    def __init__(self, objective: str):
        self.objective = objective
        self.ceo = CEOAgent()
        self.eng = EngineerAgent()
        self.growth = GrowthAgent()
        self.memory = VectorMemory()
        self.skills = get_registry()
        self.tasks: List[Dict] = []
        
    def generate_plan(self) -> List[Dict]:
        """CEO Agent breaks the objective down into actionable tasks."""
        update_hud_state(status="VENTURE", friday_output=f"CEO Agent planning: {self.objective}")
        
        prompt = (
            f"OBJECTIVE: {self.objective}\n\n"
            "Break this down into 3-5 high-level autonomous tasks. "
            "For each task, assign it to either 'Lead Engineer' or 'Growth Marketer'. "
            "Output ONLY valid JSON in this format:\n"
            '[\n  {"task": "string", "assignee": "Lead Engineer" | "Growth Marketer"}\n]'
        )
        
        res, model = self.ceo.reason(prompt, heavy=True) # Planning is complex
        try:
            # Clean up potential markdown blocks
            clean_res = res.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            
            tasks = json.loads(clean_res.strip())
            for t in tasks:
                t['status'] = 'pending'
            return tasks
        except Exception as e:
            print(f"[Venture] Failed to parse CEO plan: {e}\nRaw output: {res}")
            return []

    def execute_task(self, task: Dict) -> str:
        """Assigns the task to the correct agent for execution."""
        assignee = task.get('assignee')
        description = task.get('task')
        
        agent = None
        if assignee == "Lead Engineer":
            agent = self.eng
        elif assignee == "Growth Marketer":
            agent = self.growth
        else:
            # Fallback to CEO
            agent = self.ceo
            
        update_hud_state(status="VENTURE", friday_output=f"{agent.role_name} executing: {description[:30]}...")
        
        # Retrieve recent venture memory for context
        context_docs = self.memory.search(description, limit=2)
        context_str = "\n".join([d['text'] for d in context_docs])
        
        exec_prompt = (
            f"You are executing a task for the objective: {self.objective}\n"
            f"Your specific task: {description}\n\n"
            "Perform the task and provide a concise summary of what you 'did' or 'concluded'. "
            "If you need to use tools, just describe the output you would produce."
        )
        
        result, model = agent.reason(exec_prompt, context=context_str, heavy=False) # Execution uses local if possible
        
        # Save to memory
        self.memory.add(f"Venture Task Executed [{assignee}]: {description} -> {result}", category="venture")
        return result

    def run(self, max_iterations: int = 5):
        print(f"\n🚀 Starting Venture Orchestration: {self.objective}\n")
        
        # 1. Create Initial Tasks
        self.tasks = self.generate_plan()
        if not self.tasks:
            print("❌ Venture failed to generate initial plan.")
            return
            
        print("📋 CEO Plan Approved:")
        for idx, t in enumerate(self.tasks):
            print(f"  {idx+1}. [{t['assignee']}] {t['task']}")
            
        # 2. Execution Loop (BabyAGI style)
        iteration = 0
        while any(t['status'] == 'pending' for t in self.tasks) and iteration < max_iterations:
            # Get next pending task
            current_task = next(t for t in self.tasks if t['status'] == 'pending')
            
            print(f"\n🔄 Cycle {iteration+1} | Assignee: {current_task['assignee']}")
            print(f"   Task: {current_task['task']}")
            
            # Execute
            result = self.execute_task(current_task)
            current_task['status'] = 'completed'
            current_task['result'] = result
            
            print(f"   ✅ Result: {result[:100]}...\n")
            
            # (Optional in a full system: CEO reprioritizes or adds new tasks based on result here)
            
            iteration += 1
            
        print("🎉 Venture Orchestration Complete.")
        update_hud_state(status="IDLE", friday_output=f"Venture complete: {self.objective[:20]}...")
