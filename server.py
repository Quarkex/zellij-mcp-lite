#!/usr/bin/env python3
"""MCP server for Zellij session interaction over SSH."""

import os
import subprocess
import json
import re
import sys

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]?')


def run_ssh(host, command, timeout=10):
    """Run a command on remote host via SSH, or locally if host is 'local'."""
    if host == "local":
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True, text=True, timeout=timeout
        )
    else:
        result = subprocess.run(
            ["ssh", host, command],
            capture_output=True, text=True, timeout=timeout
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Exit code {result.returncode}")
    return result.stdout


def handle_tool_call(name, arguments):
    host = arguments.get("host", "local")
    session = arguments.get("session")

    if not session:
        # Auto-detect: find the only active session
        output = run_ssh(host, "zellij list-sessions 2>&1")
        active = []
        for line in output.strip().splitlines():
            if "EXITED" in line:
                continue
            clean = ANSI_RE.sub('', line).strip()
            if not clean:
                continue
            name_part = clean.split()[0] if clean.split() else ""
            # Valid session names don't start with '['
            if name_part and not name_part.startswith('['):
                active.append(name_part)
        if len(active) == 1:
            session = active[0]
        elif len(active) == 0:
            return [{"type": "text", "text": "Error: No active Zellij sessions found."}]
        else:
            return [{"type": "text", "text": f"Error: Multiple active sessions, specify one: {active}"}]

    zenv = f"ZELLIJ_SESSION_NAME={session}"

    if name == "zellij_read":
        tail = arguments.get("tail")
        full = arguments.get("full", False)
        dump_path = "/tmp/zj-mcp-dump.txt"

        full_flag = "-f " if full else ""
        cmd = f"{zenv} zellij action dump-screen {full_flag}{dump_path}"

        if tail:
            cmd += f" && tail -n {tail} {dump_path}"
        else:
            cmd += f" && cat {dump_path}"

        # Strip ANSI codes
        cmd += " | sed 's/\\x1b\\[[0-9;]*[a-zA-Z]//g'"

        output = run_ssh(host, cmd)
        return [{"type": "text", "text": output}]

    elif name == "zellij_write":
        text = arguments.get("text", "")
        enter = arguments.get("enter", False)
        speed = arguments.get("speed", "instant")

        # Resolve speed to delay in seconds
        speed_presets = {"instant": 0, "fast": 0.05, "human": 0.12, "slow": 0.25}
        if isinstance(speed, str):
            delay = speed_presets.get(speed, 0)
        else:
            delay = speed / 1000.0  # integer = milliseconds

        if enter:
            text += "\n"

        if delay == 0:
            # Instant: send all at once
            escaped = text.replace("'", "'\\''")
            cmd = f"{zenv} zellij action write-chars '{escaped}'"
            run_ssh(host, cmd)
        else:
            # Character by character with delay
            import time
            for char in text:
                escaped = char.replace("'", "'\\''")
                cmd = f"{zenv} zellij action write-chars '{escaped}'"
                run_ssh(host, cmd)
                time.sleep(delay)

        return [{"type": "text", "text": f"OK: sent {len(text)} chars to {session} (speed: {speed})"}]

    elif name == "zellij_list_sessions":
        output = run_ssh(host, "zellij list-sessions 2>&1")
        return [{"type": "text", "text": output}]

    else:
        return [{"type": "text", "text": f"Unknown tool: {name}"}]


TOOLS = [
    {
        "name": "zellij_read",
        "description": "Read/dump the content of the focused pane in a Zellij session. Returns the terminal text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "SSH host, or 'local' for local execution (default: local)", "default": "local"},
                "session": {"type": "string", "description": "Zellij session name. If omitted, auto-detects the single active session."},
                "tail": {"type": "integer", "description": "Only return the last N lines. Omit for full viewport."},
                "full": {"type": "boolean", "description": "Include full scrollback history (not just visible viewport)", "default": False},
            },
        },
    },
    {
        "name": "zellij_write",
        "description": "Write/inject text into the focused pane of a Zellij session. Like typing on the keyboard.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "SSH host, or 'local' for local execution (default: local)", "default": "local"},
                "session": {"type": "string", "description": "Zellij session name. If omitted, auto-detects the single active session."},
                "text": {"type": "string", "description": "Text to type into the terminal."},
                "enter": {"type": "boolean", "description": "Append Enter/newline after the text (execute command)", "default": False},
                "speed": {"description": "Typing speed. String presets: 'instant' (default), 'fast' (~50ms), 'human' (~120ms), 'slow' (~250ms). Or integer = milliseconds between characters.", "default": "instant"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "zellij_list_sessions",
        "description": "List all Zellij sessions on the remote host, showing which are active vs exited.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "SSH host, or 'local' for local execution (default: local)", "default": "local"},
            },
        },
    },
]


def main():
    """JSON-RPC stdio MCP server."""
    initialized = False

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method")
        req_id = request.get("id")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "zellij", "version": "1.0.0"},
                },
            }
            initialized = True

        elif method == "notifications/initialized":
            continue  # No response needed

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            }

        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                content = handle_tool_call(tool_name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": content},
                }
            except Exception as e:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"Error: {e}"}]},
                }

        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        if req_id is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
