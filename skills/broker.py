"""
Friday :: Resource Broker Skill (v2.0)
Acts as a librarian/architect. Manages the "Knowledge Vault" (Obsidian-style).
Encapsulates "Discovery-Driven Design".
"""
from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path
from .registry import Skill, Operation, SkillResult
from friday.brain.memory import Memory

VAULT_DIR = Path(os.path.expanduser("~/AI/friday/vault"))
VAULT_DIR.mkdir(parents=True, exist_ok=True)

class BrokerSkill(Skill):
    name = "broker"
    description = "Discover and suggest the best APIs, tools, or frameworks from the Knowledge Vault."

    def _register_operations(self) -> None:
        self.register_op(Operation("lookup_tool", "Search the vault for a tool or API.",
                                   fn=self.op_lookup_tool, risk="low"))
        self.register_op(Operation("suggest_stack", "Propose a tech stack for a given goal using the vault.",
                                   fn=self.op_suggest_stack, risk="low"))
        self.register_op(Operation("apply_methodology", "Apply a framework (Pocock, Superpowers) to the current task.",
                                   fn=self.op_apply_methodology, risk="low"))
        self.register_op(Operation("ingest_repo", "Fetch a GitHub repo, distill its knowledge, and save to the Vault.",
                                   fn=self.op_ingest_repo, risk="medium"))
        self.register_op(Operation("batch_ingest", "Ingest multiple repos from a list or file.",
                                   fn=self.op_batch_ingest, risk="medium"))
        self.register_op(Operation("map_vault", "Generate a web/map of the current Knowledge Vault.",
                                   fn=self.op_map_vault, risk="low"))
        self.register_op(Operation("deep_refine", "Initiate a multi-LLM debate to refine a topic in the Vault.",
                                   fn=self.op_deep_refine, risk="medium"))

    def op_lookup_tool(self, query: str = "", **_) -> SkillResult:
        if not query:
            return SkillResult(ok=False, error="query required")
        
        from friday.skills.research import ResearchSkill
        rs = ResearchSkill()
        # Search both memory.json (legacy) and the Vault
        matches = []
        
        # 1. Search Vault
        for p in VAULT_DIR.glob("*.md"):
            try:
                content = p.read_text(errors="ignore")
                if query.lower() in content.lower() or query.lower() in p.name.lower():
                    matches.append({"source": "vault", "file": p.name, "preview": content[:300]})
            except Exception: continue
            
        # 2. Search legacy facts
        mem = Memory()
        facts = mem._data.get("facts", {})
        for k, v in facts.items():
            if query.lower() in k.lower() or query.lower() in str(v).lower():
                matches.append({"source": "legacy_memory", "key": k, "value": v})
                
        if not matches:
            return SkillResult(ok=True, data={"found": False, "message": f"No matches for '{query}'."})
            
        return SkillResult(ok=True, data={"found": True, "matches": matches[:10]})

    def op_suggest_stack(self, goal: str = "", **_) -> SkillResult:
        if not goal:
            return SkillResult(ok=False, error="goal required")
            
        # Scan vault for potential tools
        vault_items = []
        for p in VAULT_DIR.glob("*.md"):
            vault_items.append(f"FILE: {p.name}\nCONTENT: {p.read_text()[:500]}")
            
        from friday.brain.engine import MultiEngine
        from friday.brain.personality import system_prompt
        eng = MultiEngine()
        sysp = system_prompt(task_hint="Architect. Use the Vault to propose a stack.")
        
        prompt = (
            f"GOAL: {goal}\n\n"
            f"VAULT CONTENT:\n" + "\n---\n".join(vault_items[:15]) + "\n\n"
            "INSTRUCTION:\n"
            "1. Recommend 2-3 tools from the vault.\n"
            "2. Mandate a methodology (Pocock/Superpowers) if applicable."
        )
        
        try:
            out, used = eng.ask(sysp, prompt, force="ollama")
            return SkillResult(ok=True, data={"recommendation": out, "engine": used})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_apply_methodology(self, framework: str = "", task: str = "", **_) -> SkillResult:
        # Check vault first, then legacy memory
        f_file = VAULT_DIR / f"{framework.lower().replace(' ', '_')}.md"
        concepts = ""
        if f_file.exists():
            concepts = f_file.read_text()
        else:
            mem = Memory()
            facts = mem._data.get("facts", {})
            f_key = next((k for k in facts if framework.lower() in k.lower() and "concepts" in k.lower()), None)
            if f_key:
                concepts = str(facts[f_key])
        
        if not concepts:
            return SkillResult(ok=False, error=f"Framework '{framework}' not found.")
            
        from friday.brain.engine import MultiEngine
        eng = MultiEngine()
        prompt = f"TASK: {task}\nFRAMEWORK: {framework}\nCONCEPTS: {concepts}\n\nPLAN:"
        try:
            out, used = eng.ask("Senior Engineer.", prompt, force="ollama")
            return SkillResult(ok=True, data={"plan": out, "engine": used})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_ingest_repo(self, url: str = "", **_) -> SkillResult:
        if not url or "github.com" not in url:
            return SkillResult(ok=False, error="Valid GitHub URL required.")
            
        repo_path = url.replace("https://github.com/", "").strip("/").replace(".git", "")
        name = repo_path.split("/")[-1].replace("-", "_").lower()
        
        from friday.skills.research import ResearchSkill
        rs = ResearchSkill()
        
        readme_text = ""
        for branch in ["main", "master"]:
            for filename in ["README.md", "readme.md", "README.mdx"]:
                u = f"https://raw.githubusercontent.com/{repo_path}/{branch}/{filename}"
                res = rs.op_fetch_page(url=u, max_chars=15000)
                if res.ok and len(res.data.get("text", "")) > 100 and "404" not in res.data["text"]:
                    readme_text = res.data["text"]
                    break
            if readme_text: break
            
        if not readme_text:
            res = rs.op_fetch_page(url=url, max_chars=10000)
            readme_text = res.data.get("text", "") if res.ok else ""
                 
        if not readme_text:
             return SkillResult(ok=False, error=f"Failed to fetch {repo_path}")
             
        from friday.brain.engine import MultiEngine
        eng = MultiEngine()
        prompt = (
            f"REPO: {url}\nREADME: {readme_text[:8000]}\n\n"
            "Format as an Obsidian-style Markdown file. Include:\n"
            "# Title\n"
            "## Description\n"
            "## Tech Stack\n"
            "## Links to other topics if applicable (using [[Topic]])\n"
            "## Usage Examples"
        )
        
        try:
            out, used = eng.ask("Technical Librarian.", prompt)
            # Save to Vault
            p = VAULT_DIR / f"{name}.md"
            p.write_text(out)
            return SkillResult(ok=True, data={"file": p.name, "engine": used})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_batch_ingest(self, source_file: str = "data/awesome_master.md", limit: int = 5, **_) -> SkillResult:
        """Parses a markdown file for GitHub links and ingests them into the Vault."""
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 5
            
        p = Path(os.path.expanduser(f"~/AI/friday/{source_file}"))
        if not p.exists():
            return SkillResult(ok=False, error=f"Source file {source_file} not found.")
            
        content = p.read_text()
        # Find all github links like [name](https://github.com/user/repo)
        links = re.findall(r'\[(.*?)\]\((https://github.com/.*?)\)', content)
        
        if not links:
            return SkillResult(ok=False, error="No GitHub links found in source.")
            
        results = []
        ingested_count = 0
        for name, url in links:
            if ingested_count >= limit:
                break
            
            repo_path = url.replace("https://github.com/", "").strip("/").replace(".git", "")
            repo_name = repo_path.split("/")[-1].replace("-", "_").lower()
            vault_file = VAULT_DIR / f"{repo_name}.md"
            
            if vault_file.exists():
                results.append({"name": name, "status": "skipped", "reason": "already in vault"})
                continue
                
            print(f"DEBUG: Batch ingesting {name} ({url})...")
            res = self.op_ingest_repo(url=url)
            if res.ok:
                results.append({"name": name, "status": "ingested"})
                ingested_count += 1
                # Small delay to avoid rate limits
                time.sleep(1.5)
            else:
                results.append({"name": name, "status": "failed", "error": res.error})
                
        return SkillResult(ok=True, data={"results": results, "ingested": ingested_count})

    def op_map_vault(self, **_) -> SkillResult:
        """Generates a graph of the vault based on [[links]]."""
        nodes = []
        edges = []
        for p in VAULT_DIR.glob("*.md"):
            name = p.stem
            nodes.append(name)
            content = p.read_text()
            links = re.findall(r"\[\[(.*?)\]\]", content)
            for l in links:
                edges.append({"from": name, "to": l.lower().replace(" ", "_")})
        return SkillResult(ok=True, data={"nodes": nodes, "edges": edges, "total_files": len(nodes)})

    def op_deep_refine(self, topic: str = "", **_) -> SkillResult:
        """Initiates a 'Synthetic Council' debate between LLMs to find deep knowledge/hacks."""
        if not topic:
            return SkillResult(ok=False, error="Topic required.")
            
        file_path = VAULT_DIR / f"{topic.lower().replace(' ', '_')}.md"
        if not file_path.exists():
            return SkillResult(ok=False, error=f"Topic '{topic}' not found in Vault.")
            
        current_knowledge = file_path.read_text()
        
        from friday.brain.engine import MultiEngine
        eng = MultiEngine()
        
        # 1. The Expert/Griller (e.g. Llama 3.2) critiques the current knowledge
        griller_system = (
            "You are a World-Class Technical Auditor and Hacker. Your goal is to find the hidden edge cases, "
            "undocumented hacks, and architectural weaknesses in the technical documentation provided."
        )
        griller_prompt = (
            f"SUBJECT: {topic}\n"
            f"CURRENT KNOWLEDGE BASE:\n{current_knowledge}\n\n"
            "INSTRUCTION: Critique this understanding. What is missing? What are the 'unwritten rules' or "
            "special hacks that only a senior engineer would know? Ask 3 deep, challenging questions."
        )
        
        try:
            critique, c_engine = eng.ask(griller_system, griller_prompt, force="ollama")
            
            # 2. The Student/Friday (e.g. Gemma 3) researches and synthesizes the answers
            student_system = (
                "You are F.R.I.D.A.Y., Bhargav's sovereign AI. You are evolving your understanding by listening "
                "to a technical expert's critique."
            )
            student_prompt = (
                f"THE CRITIQUE:\n{critique}\n\n"
                "INSTRUCTION: Synthesize these insights. Provide a 'Deep Knowledge' section that includes "
                "the hacks, remedies, and advanced optimizations identified. Format as high-density Markdown."
            )
            
            deep_insights, s_engine = eng.ask(student_system, student_prompt, heavy=True)
            
            # 3. Update the Vault note
            updated_content = current_knowledge + f"\n\n## 🧠 Deep Knowledge (Synthetic Council)\n*Refined via debate between {c_engine} and {s_engine}*\n\n{deep_insights}"
            file_path.write_text(updated_content)
            
            return SkillResult(ok=True, data={
                "topic": topic,
                "critique": critique,
                "synthesis": deep_insights,
                "engines_used": [c_engine, s_engine]
            })
            
        except Exception as e:
            return SkillResult(ok=False, error=f"Deep refinement failed: {str(e)}")

