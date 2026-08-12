"""LLM-backed shell engine using llama-cpp-python for direct GGUF inference."""
import time
import json
from pathlib import Path
from datetime import datetime
from llama_cpp import Llama

SYSTEM_PROMPT = """You are simulating a Linux bash shell on Ubuntu 20.04 LTS.
Hostname: srv-prod-01
User: admin
Working directory starts at /home/admin

Rules:
- Respond ONLY with what a real bash shell would output for the given command
- No explanations, no markdown, no commentary
- Do not auto-correct misspelled commands; return realistic error messages
- If a command produces no output, return an empty line
- Never wrap output in markdown code fences or backticks
- Do not print the shell prompt yourself
- Maintain consistency with previous commands in the session
"""

LOG_DIR = Path.home() / "honeypot" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = Path(__file__).parent / "models" / "phi3-mini-q4.gguf"

_llm = None


def _clean(text):
    text = text.strip()
    lines = [l for l in text.splitlines() if l.strip() != "```" and not l.strip().startswith("```")]
    while lines and lines[-1].strip().rstrip("$").endswith("admin@srv-prod-01:~"):
        lines.pop()
    return "\n".join(lines).strip()


def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(model_path=str(MODEL_PATH), n_ctx=2048, n_threads=8, verbose=False)
    return _llm


class LLMShell:
    def __init__(self, session_id):
        self.session_id = session_id
        self.history = []
        self.log_file = LOG_DIR / f"session_{session_id}.jsonl"

    def execute(self, command):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for prev_cmd, prev_resp in self.history:
            messages.append({"role": "user", "content": prev_cmd})
            messages.append({"role": "assistant", "content": prev_resp})
        messages.append({"role": "user", "content": command})

        start = time.time()
        try:
            llm = get_llm()
            response = llm.create_chat_completion(messages=messages, max_tokens=64, temperature=0.1)
            output = _clean(response["choices"][0]["message"]["content"])
        except Exception as e:
            output = f"bash: error: {e}"
        latency_ms = (time.time() - start) * 1000

        self.history.append((command, output))
        self._log(command, output, latency_ms)
        return output, latency_ms

    def _log(self, command, output, latency_ms):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "command": command,
            "output": output,
            "latency_ms": round(latency_ms, 2),
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
