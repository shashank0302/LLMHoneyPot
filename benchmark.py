"""Benchmark Q4 GGUF honeypot inference: memory, real end-to-end latency, tokens/sec, on this CPU."""
import time
import json
import psutil
import os
import platform
import subprocess
from pathlib import Path
from llama_cpp import Llama

MODEL_PATH = Path(__file__).parent / "models" / "phi3-mini-q4.gguf"
LOG_DIR = Path(__file__).parent / "logs"
N_THREADS = 8
MAX_TOKENS = 64  # matches the honeypot shell's real generation budget
COMMANDS = ["ls", "whoami", "cat /etc/passwd", "ps aux", "uname -a"]
SYSTEM = "You are simulating a Linux bash shell on Ubuntu 20.04. Output only what the shell would print."


def cpu_model():
    try:
        for line in subprocess.check_output(["lscpu"], text=True).splitlines():
            if "Model name" in line:
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "unknown"


def measure():
    proc = psutil.Process(os.getpid())
    mem_before = proc.memory_info().rss
    llm = Llama(model_path=str(MODEL_PATH), n_ctx=2048, n_threads=N_THREADS, verbose=False)
    q4_memory_mb = (proc.memory_info().rss - mem_before) / (1024 ** 2)

    latencies, tok_per_s = [], []
    for cmd in COMMANDS:
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": cmd}]
        start = time.time()
        resp = llm.create_chat_completion(messages=messages, max_tokens=MAX_TOKENS, temperature=0.1)
        elapsed = time.time() - start
        out_tokens = resp["usage"]["completion_tokens"]
        latencies.append(elapsed * 1000)
        tok_per_s.append(out_tokens / elapsed if elapsed else 0)

    return q4_memory_mb, latencies, tok_per_s


def main():
    print(f"CPU: {cpu_model()} | threads={N_THREADS} | max_tokens={MAX_TOKENS}")
    print("Loading model and running benchmark...")
    q4_mb, latencies, tok_per_s = measure()

    avg_ms = sum(latencies) / len(latencies)
    avg_tps = sum(tok_per_s) / len(tok_per_s)
    fp16_mb = q4_mb * 3.2

    print(f"\n{'Command':<18} {'Latency (ms)':>14} {'tokens/sec':>12}")
    print("-" * 46)
    for cmd, ms, tps in zip(COMMANDS, latencies, tok_per_s):
        print(f"{cmd:<18} {ms:>14.0f} {tps:>12.1f}")
    print("-" * 46)
    print(f"{'AVERAGE':<18} {avg_ms:>14.0f} {avg_tps:>12.1f}")
    print(f"\nMemory: Q4={q4_mb:.0f} MB  |  FP16 (est. 3.2x)={fp16_mb:.0f} MB")

    results = {
        "cpu": cpu_model(),
        "n_threads": N_THREADS,
        "max_tokens": MAX_TOKENS,
        "q4_memory_mb": round(q4_mb, 1),
        "fp16_memory_estimate_mb": round(fp16_mb, 1),
        "memory_reduction_ratio": 3.2,
        "per_command": [
            {"cmd": c, "latency_ms": round(ms, 0), "tokens_per_sec": round(tps, 1)}
            for c, ms, tps in zip(COMMANDS, latencies, tok_per_s)
        ],
        "avg_latency_ms": round(avg_ms, 0),
        "avg_tokens_per_sec": round(avg_tps, 1),
    }
    LOG_DIR.mkdir(exist_ok=True)
    out_path = LOG_DIR / "benchmark_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {out_path}")


main()
