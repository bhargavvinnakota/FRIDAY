"""
Friday V2.5 :: MLX LoRA Fine-Tuning Script
Executes Phase 3 Knowledge Distillation on Apple Silicon.
Trains a LoRA adapter for a base student model using the distilled ShareGPT dataset.
"""
import os
import sys
import subprocess
from pathlib import Path

def train_student_model(dataset_path: str, model_name: str = "mlx-community/Llama-3.2-1B-Instruct-4bit"):
    print("╔══════════════════════════════════════╗")
    print("║  FRIDAY :: LOCAL MLX DISTILLATION    ║")
    print("╚══════════════════════════════════════╝\n")
    
    if not os.path.exists(dataset_path):
        print(f"❌ Dataset not found at: {dataset_path}")
        print("Please run `friday distill` first to generate a training set.")
        return

    # Ensure mlx_lm is installed
    try:
        import mlx_lm
    except ImportError:
        print("❌ mlx-lm is not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "mlx-lm"], check=True)
        
    output_adapter = os.path.expanduser("~/AI/friday/data/adapters/friday_core_adapter")
    os.makedirs(output_adapter, exist_ok=True)
    
    print(f"🧠 Base Model: {model_name}")
    print(f"📚 Dataset: {dataset_path}")
    print(f"💾 Output Adapter: {output_adapter}")
    print("\n⏳ Initiating MLX LoRA Fine-Tuning on Neural Engine / GPU...")
    print("   (This will take several minutes depending on your Mac's RAM and dataset size.)\n")
    
    # We use a subprocess to invoke mlx_lm.lora
    # Formatting the dataset path to be a directory if mlx_lm expects it, 
    # but mlx_lm can take a single jsonl file if formatted correctly in a generic dir.
    # To be robust for mlx_lm, we usually pass a directory containing train.jsonl
    
    dataset_dir = os.path.dirname(dataset_path)
    train_file = os.path.join(dataset_dir, "train.jsonl")
    
    # Move the target file to train.jsonl temporarily for mlx_lm
    original_target = None
    if dataset_path != train_file:
        original_target = dataset_path
        subprocess.run(["cp", dataset_path, train_file])
    
    try:
        cmd = [
            sys.executable, "-m", "mlx_lm", "lora",
            "--model", model_name,
            "--data", dataset_dir,
            "--train",
            "--iters", "10", # Short for demonstration
            "--batch-size", "2",
            "--num-layers", "4",
            "--adapter-path", output_adapter
        ]
        
        # Execute the training
        subprocess.run(cmd, check=True)
        print(f"\n✅ Training Complete. Adapter saved to: {output_adapter}")
        print("\nTo use this model, update engine.py to load the base model + adapter via mlx_lm.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Training failed with error code: {e.returncode}")
    finally:
        # Cleanup
        if original_target and os.path.exists(train_file):
            os.remove(train_file)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_dataset = sys.argv[1]
    else:
        # Auto-find latest dataset
        training_dir = os.path.expanduser("~/AI/friday/data/training")
        if os.path.exists(training_dir):
            files = [os.path.join(training_dir, f) for f in os.listdir(training_dir) if f.endswith(".jsonl")]
            if files:
                target_dataset = max(files, key=os.path.getctime)
            else:
                target_dataset = "UNKNOWN"
        else:
            target_dataset = "UNKNOWN"
            
    train_student_model(target_dataset)
