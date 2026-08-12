# LLM Honeypot

An SSH honeypot that accepts any credentials and hands the attacker a fake shell backed by a locally-run quantized LLM. Every command they type is answered by Phi-3-mini generating plausible Linux output — no real filesystem, no real command execution, nothing to escape from.

Connection attempts and full command transcripts are logged to JSONL.

## How it works

```
attacker ──ssh:22──> nginx (stream proxy) ──> :2222 asyncssh server ──> LLMShell ──> phi3-mini Q4 (llama.cpp)
                                                     │                      │
                                              connections.jsonl      session_<ip>_<ts>.jsonl
```

- **`ssh_honeypot.py`** — asyncssh server on port 2222. `validate_password()` always returns `True` and logs the attempt, so every credential pair gets in. Each session gets its own `LLMShell`.
- **`llm_shell.py`** — the shell simulator. Holds a system prompt pinning the persona (Ubuntu 20.04, hostname `srv-prod-01`, user `admin`) and replays the session's command history into each request so the fake filesystem stays self-consistent. Strips markdown fences and echoed prompts out of the model's output.
- **`benchmark.py`** — measures resident memory, end-to-end latency and tokens/sec for the Q4 model on the host CPU.
- **`nginx.conf`** — stream proxy so the honeypot can sit on port 22 without running as root.

The model runs through `llama-cpp-python` directly against the GGUF file, not through an API — so it works offline and nothing leaves the box.

## Setup

Requires Python 3.10+.

```bash
python3 -m venv venv
venv/bin/pip install asyncssh llama-cpp-python psutil
```

Then provide the model at `models/phi3-mini-q4.gguf`. If you already have it via ollama:

```bash
mkdir -p models
ln -s ~/.ollama/models/blobs/<phi3-mini-q4-blob> models/phi3-mini-q4.gguf
```

Otherwise download a Phi-3-mini 4k-instruct Q4 GGUF from Hugging Face and drop it there under that name.

## Running

```bash
venv/bin/python ssh_honeypot.py
```

Listens on `0.0.0.0:2222`. On first run it generates an RSA `host_key` in the repo root.

Connect to it:

```bash
ssh admin@localhost -p 2222        # any username and password will work
```

To front it on port 22:

```bash
sudo nginx -c /path/to/honeypot/nginx.conf
```

## Logs

Written to `~/honeypot/logs/`. Both files are JSONL, one object per line.

`connections.jsonl` — one entry per auth attempt:

```json
{"timestamp": "...", "ip": "127.0.0.1", "port": 43640, "username": "admin", "password": "12345678"}
```

`session_<ip>_<timestamp>.jsonl` — one entry per command, with the model's response time:

```json
{"timestamp": "...", "session_id": "...", "command": "ls", "output": "...", "latency_ms": 2055.0}
```

## Benchmarks

`venv/bin/python benchmark.py`, on an AMD Ryzen 9 4900HS, 8 threads, 64-token cap:

| Command | Latency (ms) | tokens/sec |
|---|---:|---:|
| `ls` | 2055 | 10.7 |
| `whoami` | 2720 | 0.4 |
| `cat /etc/passwd` | 4300 | 14.9 |
| `ps aux` | 3996 | 16.0 |
| `uname -a` | 3896 | 16.4 |
| **average** | **3393** | **11.7** |

Q4 resident memory is ~4.8 GB, roughly 3.2x smaller than the FP16 estimate of ~15.4 GB.

The honest caveat: ~3.4s average latency is far slower than a real shell, where these commands return in single-digit milliseconds. That timing gap is the most obvious tell, and closing it means a smaller model, GPU inference, or caching responses for the common commands.

## Caveats

- **Not a sandbox boundary.** Nothing is executed, so there's no escape — but the process itself is a normal network service. Run it in a VM or container you're willing to lose, never on a host you care about.
- Session memory is the LLM's context window. Long sessions drift, and a patient attacker can get it to contradict itself.
- `host_key` and `logs/` are gitignored. The logs capture real credentials people try; treat them as sensitive.
- This repo documents the deception surface — persona, prompt, and generation settings. Anyone reading it can fingerprint a deployment.
