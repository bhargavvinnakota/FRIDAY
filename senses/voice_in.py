"""
Friday :: Voice Input (v0.3 - Pro)
Optimized for Apple Silicon. Persistent model loading.
Enhanced audio processing via SoX.
"""
import os
import time
import subprocess
import base64
from pathlib import Path
from datetime import datetime

# Friday imports
import sys
FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
sys.path.append(str(FRIDAY_ROOT.parent))

from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.orchestrator import Orchestrator, Tool
from friday.actions import computer, nexus

# Config
AUDIO_DIR = FRIDAY_ROOT / "data" / "voice"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

def listen_and_transcribe(model):
    """Uses SoX 'rec' to capture audio, normalizes it, and transcribes with cached model."""
    audio_path = AUDIO_DIR / "query.wav"
    
    # SoX 'rec' with Pro Signal Chain:
    # 1. Native 48k sample rate
    # 2. Silence detection for start/stop
    # 3. High-pass filter (removes low-end hum/fan noise)
    # 4. Normalization (ensures voice is loud enough for AI)
    cmd = [
        "rec", "-q", "-c", "1", "-r", "48000", str(audio_path),
        "silence", "1", "0.1", "1%", "1", "1.2", "1.5%",
        "highpass", "100",
        "norm", "-1"
    ]
    
    print(f"\r[Friday: Listening...]", end="", flush=True)
    try:
        # 30s max per turn to prevent runaways
        subprocess.run(cmd, timeout=30)
    except subprocess.TimeoutExpired:
        print("\n[Timeout]")
        return None
    except KeyboardInterrupt:
        return "EXIT"

    if not audio_path.exists() or audio_path.stat().st_size < 2000:
        return None

    print(f"\r[Friday: Processing...]", end="", flush=True)
    try:
        # Transcribe using the persistent model
        # fp16=False is safer on CPU-based whisper, but faster.
        result = model.transcribe(str(audio_path), fp16=False, language="en")
        text = result.get("text", "").strip()
        return text
    except Exception as e:
        print(f"\n[Transcription error: {e}]")
        return None

def main_loop():
    print("╔══════════════════════════════════════╗")
    print("║  FRIDAY :: VOICE v0.3 (PRO)          ║")
    print("╚══════════════════════════════════════╝")
    
    # 1. Load Brain (One-time cost)
    print("[1/3] Initializing Reasoning Engines...")
    engine = MultiEngine()
    memory = Memory()
    
    # 2. Load Tools & Skills
    print("[2/3] Mapping Capability Registry...")
    from friday.skills.registry import get_registry
    reg = get_registry()
    orch = Orchestrator(engine, memory)
    
    # Register Core Nexus Tools
    orch.register(Tool(
        "agency_summary", "Agency clients + leads + CRM.",
        triggers=["client", "clients", "lead", "leads", "outreach", "crm", "agency", "whatsapp bot"],
        fn=lambda **kw: {"clients": nexus.agency_clients(),
                         "leads": nexus.leads_summary(),
                         "crm": nexus.crm_summary()},
    ))
    orch.register(Tool(
        "trading_state", "Trading brain state.",
        triggers=["trading", "trade", "portfolio", "p&l", "pnl", "regime", "positions", "nexus omega"],
        fn=lambda **kw: {"brain": nexus.trading_state(), "portfolio": nexus.portfolio_state()},
    ))
    orch.register(Tool(
        "empire_snapshot", "Full empire status across all engines.",
        triggers=["empire", "snapshot", "status", "overview", "all engines", "dashboard"],
        fn=lambda **kw: nexus.snapshot(),
    ))

    # Wrap Skills
    for skill_name, skill in reg.all().items():
        for op_name, op in skill.operations.items():
            orch.register(Tool(
                name=f"{skill_name}_{op_name}",
                description=op.description,
                triggers=[op_name, f"{skill_name} {op_name}"],
                fn=lambda _sn=skill_name, _on=op_name, **kw: reg.invoke(_sn, _on, _actor="voice", **kw).to_dict()
            ))
    
    # 3. Load Vision/Voice AI (Heavy lifting)
    print("[3/3] Loading Whisper AI Model (Base)...")
    import whisper
    model = whisper.load_model("base")
    
    computer.say("Friday online. I'm listening.")
    print("\nREADY. Talk to me.")
    
    while True:
        text = listen_and_transcribe(model)
        
        if text == "EXIT":
            print("\nShutting down.")
            break
            
        if not text or len(text) < 4:
            # Ignore micro-sounds/breathing
            continue
            
        print(f"\rBhargav: {text: <50}")
        
        # Get Friday's response
        result = orch.respond(text)
        reply = result.get("reply", "")
        
        print(f"Friday: {reply}")
        
        # Speak the response
        computer.say(reply)
        
        # Small cooldown to prevent loopback from own voice
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nFriday shutting down.")
