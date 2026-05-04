"""
Friday :: Voice Core (v1.0 LEGENDARY)
RAM-only, zero-disk-IO audio pipeline.
Real-time energy VAD + direct NumPy array transcription.
Latency reduced to near-human speed.
"""
import os
import sys
import time
import queue
import threading
import subprocess
import numpy as np
import sounddevice as sd
from pathlib import Path

# Friday imports
FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
sys.path.append(str(FRIDAY_ROOT.parent))

from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.orchestrator import Orchestrator, Tool
from friday.actions import computer, nexus

# --- TUNING ---
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.015    # RMS energy threshold (adjust if needed)
MIN_SPEECH_SEC = 0.5         # Ignore tiny clicks/breaths
MAX_SILENCE_SEC = 1.0        # Pause to signal "end of sentence"
BUFFER_MAX_SEC = 30.0        # Hard cutoff to prevent memory leaks

class RamVAD:
    """Real-time Voice Activity Detection entirely in RAM"""
    def __init__(self, model, orchestrator):
        self.model = model
        self.orch = orchestrator
        
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.speech_buffer = []
        self.silence_frames = 0
        
        # Audio stream params
        self.frames_per_buffer = int(SAMPLE_RATE * 0.1) # 100ms chunks
        self.max_silence_frames = int(MAX_SILENCE_SEC / 0.1)
        
        # UI State
        self.state_lock = threading.Lock()
        self.friday_speaking = False

    def audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for every 100ms chunk of audio from the mic."""
        if status: print(status, file=sys.stderr)
        
        # Don't record if Friday is currently speaking
        if self.friday_speaking:
            return
            
        # Squeeze down to 1D float32 array
        chunk = indata[:, 0]
        
        # Calculate RMS energy (volume)
        rms = np.sqrt(np.mean(chunk**2))
        is_speech = rms > SILENCE_THRESHOLD
        
        if self.is_recording:
            self.speech_buffer.append(chunk)
            
            if is_speech:
                self.silence_frames = 0
                # Visual feedback for speaking
                print(f"\r[Friday: Listening " + "█" * min(int(rms*100), 20) + " " * 20 + "]", end="", flush=True)
            else:
                self.silence_frames += 1
                
            # If silence lasted long enough OR buffer got too huge -> process
            if self.silence_frames > self.max_silence_frames or len(self.speech_buffer) > (BUFFER_MAX_SEC / 0.1):
                # Save buffer and reset state
                audio_data = np.concatenate(self.speech_buffer)
                self.is_recording = False
                self.speech_buffer = []
                self.silence_frames = 0
                
                # Check if it was long enough to be a real word
                if len(audio_data) / SAMPLE_RATE > MIN_SPEECH_SEC:
                    # Put raw numpy array into queue for the AI thread
                    self.audio_queue.put(audio_data)
                else:
                    print("\r[Friday: Waiting...]" + " "*20, end="", flush=True)
                    
        else:
            if is_speech:
                # Start recording!
                self.is_recording = True
                self.speech_buffer = [chunk]
                self.silence_frames = 0

    def ai_worker(self):
        """Background thread that pops numpy arrays and talks to Whisper/Gemma."""
        while True:
            audio_data = self.audio_queue.get()
            if audio_data is None: break
            
            print("\r[Friday: Processing (RAM)]" + " "*15, end="", flush=True)
            
            # Whisper can transcribe float32 numpy arrays directly! (ZERO DISK IO)
            try:
                # pad/trim to 30s as whisper expects, or just let whisper handle the 1D array
                # fp16=False for Mac CPU
                result = self.model.transcribe(audio_data, fp16=False, language="en")
                text = result.get("text", "").strip()
            except Exception as e:
                print(f"\n[Whisper Error: {e}]")
                continue
                
            if not text or len(text) < 4:
                print("\r[Friday: Waiting...]" + " "*20, end="", flush=True)
                continue
                
            print(f"\nBhargav: {text}")
            
            # Lock mic while Friday thinks and speaks
            with self.state_lock:
                self.friday_speaking = True
                
            # Get Response from Gemma/Claude
            resp = self.orch.respond(text)
            reply = resp.get("reply", "")
            print(f"Friday:  {reply}\n")
            
            # Speak (Blocks until finished)
            computer.say(reply)
            
            # Unlock mic
            time.sleep(0.3) # small buffer so she doesn't hear her own echo
            with self.state_lock:
                self.friday_speaking = False
            
            print("\r[Friday: Waiting...]" + " "*20, end="", flush=True)


def load_legendary_system():
    print("╔══════════════════════════════════════╗")
    print("║  FRIDAY :: VOICE v1.0 (LEGENDARY)    ║")
    print("║  RAM-Only • Direct Numpy Pipeline    ║")
    print("╚══════════════════════════════════════╝")
    
    print("[1/3] Spinning up Local Brain (Gemma 4)...")
    engine = MultiEngine()
    memory = Memory()
    
    print("[2/3] Wiring Neural Pathways (Vision & Hands)...")
    from friday.skills.registry import get_registry
    reg = get_registry()
    orch = Orchestrator(engine, memory)
    
    # Map Nexus Core
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

    # Wrap Skills into Tools
    for skill_name, skill in reg.all().items():
        for op_name, op in skill.operations.items():
            orch.register(Tool(
                name=f"{skill_name}_{op_name}",
                description=op.description,
                triggers=[op_name, f"{skill_name} {op_name}"],
                fn=lambda _sn=skill_name, _on=op_name, **kw: reg.invoke(_sn, _on, _actor="voice", **kw).to_dict()
            ))
            
    print("[3/3] Loading Local Whisper Neural Net into RAM...")
    import whisper
    import warnings
    warnings.filterwarnings("ignore") # hide fp16 warnings
    model = whisper.load_model("base")
    
    return model, orch

def run_ram_engine():
    model, orch = load_legendary_system()
    vad = RamVAD(model, orch)
    
    computer.say("Systems loaded. I am online.")
    print("\n[Friday: Waiting...]", end="", flush=True)
    
    # Start AI Worker Thread
    ai_thread = threading.Thread(target=vad.ai_worker, daemon=True)
    ai_thread.start()
    
    # Start Audio Stream (Blocks main thread)
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32', blocksize=vad.frames_per_buffer, callback=vad.audio_callback):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nShutting down Neural pathways.")
        vad.audio_queue.put(None)
        ai_thread.join()

if __name__ == "__main__":
    run_ram_engine()
