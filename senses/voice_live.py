"""
Friday :: Voice LIVE Edition
Flawless Ambient Noise Adjustment + Zero-Disk-IO NumPy Streaming.
"""
import os
import sys
import time
import queue
import threading
import numpy as np
import speech_recognition as sr
from pathlib import Path

# Friday imports
FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
sys.path.append(str(FRIDAY_ROOT.parent))

from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.orchestrator import Orchestrator, Tool
from friday.actions import computer, nexus

class FridayEars:
    def __init__(self, model, orch):
        self.model = model
        self.orch = orch
        self.recognizer = sr.Recognizer()
        
        # Friday is highly sensitive and dynamic
        self.recognizer.energy_threshold = 300 
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 1.0 # 1 second of silence marks end of sentence
        self.recognizer.non_speaking_duration = 0.5
        
        self.audio_queue = queue.Queue()
        self.friday_speaking = False
        self.state_lock = threading.Lock()

    def listen_loop(self):
        with sr.Microphone(sample_rate=16000) as source:
            print("\n[Calibrating ambient noise... please wait 2 seconds]")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            print(f"[Calibration complete. Noise floor: {self.recognizer.energy_threshold}]")
            computer.say("Calibration complete. Friday is online and listening.")
            
            while True:
                with self.state_lock:
                    if self.friday_speaking:
                        time.sleep(0.1)
                        continue
                
                try:
                    print("\r[Listening...]      ", end="", flush=True)
                    # Blocks until a phrase is spoken and followed by a pause
                    audio_data = self.recognizer.listen(source, phrase_time_limit=30)
                    
                    with self.state_lock:
                        if self.friday_speaking: continue # Ignore if she started speaking
                        
                    print("\r[Processing...]     ", end="", flush=True)
                    self.audio_queue.put(audio_data)
                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    print(f"\n[Mic error: {e}]")

    def ai_worker(self):
        while True:
            audio_data = self.audio_queue.get()
            if audio_data is None: break
            
            # Convert sr.AudioData to numpy float32 array for Whisper (ZERO DISK IO)
            try:
                wav_bytes = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
                # skip 44-byte WAV header
                audio_array = np.frombuffer(wav_bytes[44:], dtype=np.int16).astype(np.float32) / 32768.0
                
                result = self.model.transcribe(audio_array, fp16=False, language="en")
                text = result.get("text", "").strip()
            except Exception as e:
                print(f"\n[Whisper error: {e}]")
                continue
                
            if not text or len(text) < 4:
                continue
                
            print(f"\n\nBhargav: {text}")
            
            with self.state_lock:
                self.friday_speaking = True
                
            resp = self.orch.respond(text)
            reply = resp.get("reply", "")
            print(f"Friday: {reply}\n")
            
            computer.say(reply)
            
            time.sleep(0.5)
            with self.state_lock:
                self.friday_speaking = False

def load_legendary_system():
    print("╔══════════════════════════════════════╗")
    print("║  FRIDAY :: VOICE LIVE EDITION        ║")
    print("║  Dynamic Ambient Noise + VAD         ║")
    print("╚══════════════════════════════════════╝")
    
    print("[1/4] Spinning up Local Brain...")
    engine = MultiEngine()
    memory = Memory()
    
    print("[2/4] Wiring Neural Pathways...")
    from friday.skills.registry import get_registry
    reg = get_registry()
    orch = Orchestrator(engine, memory)
    
    orch.register(Tool(
        "agency_summary", "Agency clients + leads.",
        triggers=["client", "clients", "lead", "leads", "agency"],
        fn=lambda **kw: {"clients": nexus.agency_clients(), "leads": nexus.leads_summary()}
    ))
    orch.register(Tool(
        "empire_snapshot", "Full empire status.",
        triggers=["empire", "snapshot", "status"],
        fn=lambda **kw: nexus.snapshot(),
    ))

    for skill_name, skill in reg.all().items():
        for op_name, op in skill.operations.items():
            orch.register(Tool(
                name=f"{skill_name}_{op_name}",
                description=op.description,
                triggers=[op_name, f"{skill_name} {op_name}"],
                fn=lambda _sn=skill_name, _on=op_name, **kw: reg.invoke(_sn, _on, _actor="voice", **kw).to_dict()
            ))
            # 3/4 Activating Evolution Engine
            print("[3/4] Activating Evolution Engine (Continuous Learning)...")
            from friday.brain.evolution import EvolutionEngine
            evo = EvolutionEngine(engine, memory)
            evo.start()

            # 4/4 Loading Whisper
            print("[4/4] Loading Local Whisper Neural Net into RAM...")
            import whisper
            import warnings
            warnings.filterwarnings("ignore")
            model = whisper.load_model("base")

            # --- PROACTIVE EMPIRE BRIEFING ---
            try:
                emp = reg.get("empire")
                status = emp.op_mission_status().data
                sched = emp.op_check_schedule().data
                greeting = (
                    f"Friday online. We are in {status['phase']}. "
                    f"The current focus is {sched['suggested_focus']}. "
                    f"I'm listening, Boss."
                )
                computer.say(greeting)
            except Exception:
                computer.say("Friday online. I'm listening.")

            return model, orch, evo
def run_friday_engine():
    model, orch, evo = load_legendary_system()
    ears = FridayEars(model, orch)
    
    ai_thread = threading.Thread(target=ears.ai_worker, daemon=True)
    ai_thread.start()
    
    try:
        ears.listen_loop()
    except KeyboardInterrupt:
        print("\nShutting down Neural pathways.")
        ears.audio_queue.put(None)
        evo.stop()
        ai_thread.join()

if __name__ == "__main__":
    run_friday_engine()
