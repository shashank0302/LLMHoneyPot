# Project Guardrails

## Scope
- Full permissions to read/write/delete/create files within the repo root only
- Do NOT modify OS-level config, WSL shell config, or any system files — ask first
- Do NOT run system-level installs (apt, pip outside venv) — provide the command and ask

## Files
- Every file must serve a specific purpose — no boilerplate, scaffolding, or placeholder files
- Do not create test files — provide test code as chat output for me to run manually

## Responses
- Keep responses concise — one or two sentences unless I ask for elaboration
- No lengthy explanations unless I explicitly ask "why" or "explain more"

## Code Principles
- Keep it simple — no abstractions beyond what the immediate task requires
- No unused code, future-proofing, or error handling for impossible scenarios
