#!/usr/bin/env python3
"""
Friday :: Neural Reflex Voice (v2.5 - God-Tier Stability)
Features: Hallucination Filtering, Silent Fallback, Robust Engine Integration.
"""
import os
import sys
import time
import queue
import threading
import subprocess
import numpy as np
import sounddevice as sd
import mlx_whisper
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.engine import MultiEngine
from friday.brain.personality import system_prompt
from friday.brain.state_relay import update_hud_state

# Upgraded Model: Base is much more stable than Tiny
MODEL = "mlx-community/whisper-base-mlx"
SAMPLE_RATE = 16000

class NeuralReflex:
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.speech_queue = queue.Queue()
        self.engine = MultiEngine()
        self.active = True
        self.is_speaking = False
        self._is_processing = False
        self._current_speech_proc = None
        self._interrupt_requested = False
        
        # Start speech worker
        threading.Thread(target=self.speech_worker, daemon=True).start()
        
    def speech_worker(self):
        while self.active:
            try:
                text = self.speech_queue.get(timeout=0.1)
            except queue.Empty: continue

            if text is None: break
            if self._interrupt_requested:
                self.speech_queue.task_done()
                continue
            
            text = text.replace('"', '').replace("'", "").strip()
            if not text or len(text) < 2: 
                self.speech_queue.task_done()
                continue
            
            # Print for Electron
            print(f"🎙️ Friday: {text}", flush=True)
            
            self.is_speaking = True
            cmd = ["say", "-v", "Samantha", text]
            self._current_speech_proc = subprocess.Popen(cmd)
            self._current_speech_proc.wait()
            self._current_speech_proc = None
            
            if self.speech_queue.empty():
                self.is_speaking = False
            
            self.speech_queue.task_done()

    def stop_speaking(self):
        self._interrupt_requested = True
        if self._current_speech_proc:
            self._current_speech_proc.terminate()
            self._current_speech_proc = None
        
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except queue.Empty: break
        
        self.is_speaking = False
        self._interrupt_requested = False
        print("🛑 Friday: Interrupted.", flush=True)

    def audio_callback(self, indata, frames, time, status):
        self.audio_queue.put(indata.copy())

    def listen_loop(self):
        print(f"🎙️ Friday 'Neural Reflex' Active. (Model: {MODEL})", flush=True)
        audio_buffer = []
        silence_count = 0
        
        # Balanced Sensitivity
        NORMAL_THRESHOLD = 0.005 
        SPEAKING_THRESHOLD = 0.02
        
        while self.active:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                if self._is_processing: continue

                energy = np.linalg.norm(chunk) / np.sqrt(len(chunk))
                current_threshold = SPEAKING_THRESHOLD if self.is_speaking else NORMAL_THRESHOLD
                
                if energy > current_threshold:
                    audio_buffer.append(chunk)
                    silence_count = 0
                else:
                    silence_count += 1
                    
                if len(audio_buffer) > 0 and silence_count > 3: # Lowered from 6 for snappier response
                    full_audio = np.concatenate(audio_buffer).flatten()
                    audio_buffer = []
                    silence_count = 0
                    threading.Thread(target=self.process_interaction, args=(full_audio,)).start()
            except queue.Empty: continue

    def is_hallucination(self, text):
        """Filters out common Whisper hallucinations on noise."""
        low_text = text.lower().strip()
        # Common patterns: "do do do", "thank you", "you", "thanks for watching"
        hallucinations = ["do do", "thank you", "thanks for watching", "bye", "you"]
        if len(low_text) < 4: return True
        # If text is extremely repetitive
        if len(set(low_text.split())) < (len(low_text.split()) / 2): return True
        return False

    def process_interaction(self, audio_data):
        if self._is_processing: return
        self._is_processing = True
        
        try:
            audio_data = audio_data.astype(np.float32)
            # MLX Whisper call
            res = mlx_whisper.transcribe(audio_data, path_or_hf_repo=MODEL)
            text = res.get("text", "").strip()
            
            if not text or self.is_hallucination(text):
                self._is_processing = False
                return
                
            print(f"👤 You: {text}", flush=True)
            update_hud_state(status="THINKING", user_input=text)
            
            # Keywords
            stop_keywords = ["stop", "shut up", "be quiet", "enough", "hold on", "cancel"]
            if self.is_speaking and any(k in text.lower() for k in stop_keywords):
                self.stop_speaking()
                self._is_processing = False
                return

            if self.is_speaking: self.stop_speaking()

            print(f"🧠 Friday Thinking...", flush=True)
            
            # Instant Acknowledgment
            ack_triggered = [False]
            def trigger_ack():
                time.sleep(1.5)
                if self._is_processing and not ack_triggered[0]:
                    self.speak_sentence("Processing...")
                    ack_triggered[0] = True
            threading.Thread(target=trigger_ack, daemon=True).start()
            
            # Unified Engine Call (Handles 429 internally now)
            world_keywords = ["world", "news", "happening", "information", "tell me about"]
            if any(k in text.lower() for k in world_keywords):
                update_hud_state(status="THINKING", user_input=text, intel_card={
                    "title": "GLOBAL_INTELLIGENCE_STREAM",
                    "body": "Analyzing real-time data feeds... Synchronizing with global news nodes... Standby for visual data."
                })
            
            tokens = self.engine.ask(system_prompt(), text, stream=True)
            
            sentence = ""
            for token in tokens:
                ack_triggered[0] = True
                if self._interrupt_requested: break
                sentence += token
                if any(punct in token for punct in [".", "!", "?", "\n"]):
                    self.speak_sentence(sentence)
                    sentence = ""
            
            if sentence and not self._interrupt_requested:
                self.speak_sentence(sentence)
            
            print("DONE_RESPONSE", flush=True)
        except Exception as e:
            print(f"❌ Reflex Error: {e}", flush=True)
            # Silent fallback: don't annoy the user if it's just a background error
        finally:
            self._is_processing = False

    def speak_sentence(self, text):
        self.speech_queue.put(text)

    def run(self):
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=self.audio_callback):
                self.listen_loop()
        except Exception as e:
            print(f"❌ Audio Hardware Error: {e}", flush=True)

if __name__ == "__main__":
    reflex = NeuralReflex()
    reflex.run()
