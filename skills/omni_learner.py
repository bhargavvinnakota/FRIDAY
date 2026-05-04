from __future__ import annotations
import urllib.request
import json
from .registry import Skill, Operation, SkillResult

class OmniLearnerSkill(Skill):
    name = "omni_learner"
    description = "Enables Friday to talk to all available open-source models, extract advanced knowledge on any topic, and synthesize it into a master insight to train herself."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            name="train_across_models",
            description="Interviews available local LLMs on a specific topic and synthesizes their insights to make Friday more powerful.",
            fn=self.op_train_across_models,
            risk="low",
            input_schema={"topic": "The advanced topic, coding paradigm, or strategy Friday needs to learn."}
        ))

    def op_train_across_models(self, topic: str, **kwargs) -> SkillResult:
        from friday.brain.engine import MultiEngine, OllamaEngine
        from friday.brain.memory import Memory
        
        eng = MultiEngine()
        mem = Memory()
        
        # 1. Get available local models
        models = []
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                models = [m["name"] for m in data.get("models", [])]
        except Exception as e:
            return SkillResult(ok=False, error=f"Failed to fetch Ollama models: {e}")

        if not models:
            return SkillResult(ok=False, error="No open-source models found locally. Install models via Ollama first.")

        print(f"[OmniLearner] Initiating training across {len(models)} models on topic: '{topic}'")
        
        # 2. Extract information from all models
        extracted_insights = []
        for model_name in models:
            try:
                print(f"[OmniLearner] Interviewing model: {model_name}...")
                model_eng = OllamaEngine(host="http://localhost:11434", model=model_name)
                
                sys_prompt = "You are an expert AI sharing your deepest knowledge, cutting-edge paradigms, and best practices."
                user_prompt = f"Provide your most advanced, concise insights and code patterns (if applicable) regarding: {topic}"
                
                response = model_eng.generate(system=sys_prompt, user=user_prompt)
                extracted_insights.append(f"--- INSIGHTS FROM {model_name} ---\n{response}\n")
            except Exception as e:
                print(f"[OmniLearner] Warning: Model {model_name} failed to respond: {e}")

        if not extracted_insights:
            return SkillResult(ok=False, error="Failed to extract insights from any model.")

        # 3. Synthesize the Master Insight
        print("[OmniLearner] Synthesizing extracted knowledge via Master AI...")
        synthesis_sys = "You are Friday's core architect. You must synthesize insights from various open-source models into a single, highly powerful, actionable Master Insight. Extract the best paradigms, ignore the fluff, and format it as a set of direct directives or core knowledge for Friday to remember."
        synthesis_user = f"Topic: {topic}\n\nRAW INSIGHTS:\n" + "\n".join(extracted_insights)
        
        master_insight, engine_used = eng.ask(system=synthesis_sys, user=synthesis_user, heavy=True)

        # 4. Save to Memory
        mem_key = f"omni_learning_{abs(hash(topic))}"
        mem.remember(mem_key, {
            "topic": topic,
            "master_insight": master_insight,
            "models_consulted": models
        }, category="omni_learning")
        
        print(f"[OmniLearner] Training complete. Memory updated. (Synthesized by {engine_used})")

        return SkillResult(ok=True, data={
            "topic": topic,
            "models_consulted": models,
            "master_insight": master_insight
        })
