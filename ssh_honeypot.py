"""SSH honeypot server — accepts any credentials, routes sessions to LLMShell."""
import asyncio
import asyncssh
import json
import time
from datetime import datetime
from pathlib import Path
from llm_shell import LLMShell

LOG_DIR = Path.home() / "honeypot" / "logs"
HOST_KEY_PATH = Path(__file__).parent / "host_key"
PROMPT = "admin@srv-prod-01:~$ "


def _log_connection(ip, port, username, password):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "ip": ip,
        "port": port,
        "username": username,
        "password": password,
    }
    with open(LOG_DIR / "connections.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")


class HoneypotSession(asyncssh.SSHServerSession):
    def __init__(self, shell):
        self._shell = shell
        self._chan = None

    def connection_made(self, chan):
        self._chan = chan

    def pty_requested(self, term_type, term_size, term_modes):
        return True

    def shell_requested(self):
        return True

    def session_started(self):
        self._chan.write(PROMPT)

    def data_received(self, data, datatype):
        command = data.rstrip("\r\n").strip()
        if not command:
            self._chan.write(PROMPT)
            return
        if command in ("exit", "logout", "quit"):
            self._chan.write("logout\r\n")
            self._chan.close()
            return
        output, _ = self._shell.execute(command)
        self._chan.write(output.replace("\n", "\r\n") + "\r\n" + PROMPT)

    def eof_received(self):
        self._chan.close()


class HoneypotServer(asyncssh.SSHServer):
    def __init__(self):
        self._username = None
        self._password = None
        self._peer = None

    def connection_made(self, conn):
        self._peer = conn.get_extra_info("peername")

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        self._username = username
        self._password = password
        ip, port = self._peer if self._peer else ("unknown", 0)
        _log_connection(ip, port, username, password)
        return True

    def session_requested(self):
        ip = self._peer[0] if self._peer else "unknown"
        session_id = f"{ip}_{int(time.time())}"
        shell = LLMShell(session_id)
        return HoneypotSession(shell)


async def main():
    if not HOST_KEY_PATH.exists():
        key = asyncssh.generate_private_key("ssh-rsa")
        HOST_KEY_PATH.write_bytes(key.export_private_key())

    await asyncssh.create_server(
        HoneypotServer,
        host="",
        port=2222,
        server_host_keys=[str(HOST_KEY_PATH)],
    )
    print("Honeypot listening on port 2222")
    await asyncio.get_event_loop().create_future()


asyncio.run(main())
