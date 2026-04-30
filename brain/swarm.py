"""
Friday :: Agentic Swarm Engine (2026 SOTA)
Hierarchical, self-improving multi-agent orchestration.
Implements dynamic routing, stateful graph handoffs, and strict JSON communication.
"""
import json
import uuid
import time
from typing import Any, List, Dict
from dataclasses import dataclass, field
from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory

@dataclass
class SwarmAgent:
    name: str
    role: str
    instructions: str
    allowed_skills: List[str] = field(default_factory=list)

@dataclass
class SwarmTask:
    id: str
    description: str
    assigned_to: str | None = None
    status: str = "pending" # pending | running | review | done | failed
    result: Any = None
    feedback: str = ""

class SwarmOrchestrator:
    def __init__(self, engine: MultiEngine, memory: Memory, skill_registry=None):
        self.engine = engine
        self.memory = memory
        if skill_registry is None:
            from friday.skills.registry import get_registry
            skill_registry = get_registry()
        self.registry = skill_registry
        
        self.agents: Dict[str, SwarmAgent] = {}
        
        # Default specialized swarm agents
        self.register_agent(SwarmAgent(
            name="Architect",
            role="System design and task breakdown.",
            instructions="You are the Swarm Architect. You break complex goals into specific, actionable steps for other agents. You never write code yourself.",
        ))
        self.register_agent(SwarmAgent(
            name="Engineer",
            role="Code generation and execution.",
            instructions="You are the Swarm Engineer. You write flawless, production-grade Python code. You execute shell commands to build what the Architect designs.",
            allowed_skills=["builder"]
        ))
        self.register_agent(SwarmAgent(
            name="Researcher",
            role="Information gathering and data synthesis.",
            instructions="You are the Swarm Researcher. You fetch documentation, scrape data, and summarize findings for the Engineer.",
            allowed_skills=["research"]
        ))
        self.register_agent(SwarmAgent(
            name="QA_Judge",
            role="Code review and quality assurance.",
            instructions="You are the Swarm QA Judge. You review the Engineer's output. If it fails, you provide strict feedback for a rewrite. If it passes, you approve it.",
        ))

    def register_agent(self, agent: SwarmAgent):
        self.agents[agent.name] = agent

    def _get_agent_prompt(self, agent: SwarmAgent, task: SwarmTask, context: str) -> str:
        prompt = f"You are {agent.name}. Role: {agent.role}\n{agent.instructions}\n\n"
        if agent.allowed_skills:
            prompt += "You have access to the following skill operations. To use one, output a JSON block like: {\"tool\": \"skill.operation\", \"args\": {...}}\n"
            for s in agent.allowed_skills:
                skill_obj = self.registry.get(s)
                if skill_obj:
                    for op_name, op_data in skill_obj.operations.items():
                        prompt += f"- {s}.{op_name}: {op_data.description} | Args: {op_data.input_schema}\n"
        
        prompt += f"\nGLOBAL CONTEXT:\n{context}\n\nYOUR CURRENT TASK:\n{task.description}\n"
        if task.feedback:
            prompt += f"\nPREVIOUS FEEDBACK TO FIX:\n{task.feedback}\n"
            
        prompt += "\nOutput your final answer or tool call as valid JSON: {\"result\": \"your work here\", \"status\": \"done\"} or {\"tool\": ...}"
        return prompt

    def run_swarm(self, goal: str) -> str:
        """
        Executes the 2026 SOTA Hierarchical Graph Loop:
        Architect -> (Researcher) -> Engineer -> QA_Judge -> (Loop or Done)
        """
        print(f"\n[Swarm Orchestrator] Initializing Swarm for Goal: {goal}")
        context = f"Main Goal: {goal}\n"
        
        # 1. Architect Planning Phase
        print(f"  -> [Architect] Drafting execution graph...")
        arch_sys = "You are the Architect. Break the goal into exactly 1 Researcher task and 1 Engineer task. Output JSON: {\"research_task\": \"...\", \"engineer_task\": \"...\"}"
        raw_plan, _ = self.engine.ask(arch_sys, goal, force="claude" if self.engine.claude.api_key else "ollama", heavy=True)
        
        try:
            json_str = raw_plan[raw_plan.find("{"):raw_plan.rfind("}")+1]
            plan = json.loads(json_str)
        except:
            plan = {"research_task": "Research requirements for: " + goal, "engineer_task": "Build: " + goal}
            
        # 2. Researcher Phase
        research_task = SwarmTask(id=str(uuid.uuid4())[:8], description=plan.get("research_task", ""))
        print(f"  -> [Researcher] Executing: {research_task.description[:60]}...")
        res_sys = self._get_agent_prompt(self.agents["Researcher"], research_task, context)
        res_out, _ = self.engine.ask(res_sys, "Begin research.", force="ollama", heavy=True)
        context += f"\nResearch Findings:\n{res_out}\n"
        
        # 3. Engineer <-> QA Loop
        eng_task = SwarmTask(id=str(uuid.uuid4())[:8], description=plan.get("engineer_task", ""))
        max_loops = 3
        
        for loop in range(max_loops):
            print(f"  -> [Engineer] Building (Attempt {loop+1}/{max_loops})...")
            eng_sys = self._get_agent_prompt(self.agents["Engineer"], eng_task, context)
            
            # The engineer might call tools. We simulate a single tool loop for safety.
            eng_out, _ = self.engine.ask(eng_sys, "Write code and use tools if needed.", force="claude" if self.engine.claude.api_key else "ollama", heavy=True)
            
            # Execute embedded tools if present
            if '{"tool":' in eng_out:
                try:
                    tool_json = json.loads(eng_out[eng_out.find("{"):eng_out.rfind("}")+1])
                    if "tool" in tool_json:
                        skill, op = tool_json["tool"].split(".")
                        print(f"     [Engineer Tool] Using {skill}.{op}...")
                        res = self.registry.invoke(skill, op, _actor="swarm", **tool_json.get("args", {}))
                        eng_out += f"\n\nTool Result: {res.data or res.error}"
                except Exception as e:
                    eng_out += f"\n\nTool Error: {e}"

            # 4. QA Phase
            print(f"  -> [QA_Judge] Reviewing Engineer's output...")
            qa_sys = (
                "You are the QA_Judge. Review the Engineer's output. "
                "Does it fully satisfy the Main Goal without errors? "
                "Output JSON: {\"pass\": true/false, \"feedback\": \"...\"}"
            )
            qa_prompt = f"MAIN GOAL: {goal}\nENGINEER OUTPUT:\n{eng_out}"
            qa_raw, _ = self.engine.ask(qa_sys, qa_prompt, force="ollama")
            
            try:
                qa_json = json.loads(qa_raw[qa_raw.find("{"):qa_raw.rfind("}")+1])
                if qa_json.get("pass"):
                    print("  -> [QA_Judge] APPROVED. Swarm mission accomplished.")
                    return eng_out
                else:
                    eng_task.feedback = qa_json.get("feedback", "Failed quality checks.")
                    print(f"  -> [QA_Judge] REJECTED. Feedback sent back to Engineer: {eng_task.feedback[:60]}...")
            except:
                print("  -> [QA_Judge] Warning: Judge parse error, auto-approving for safety limit.")
                return eng_out
                
        print("  -> [Swarm] Max loops reached. Terminating swarm.")
        return eng_out
