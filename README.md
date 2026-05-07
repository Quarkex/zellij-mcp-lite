# zellij-mcp-lite

A minimalist [MCP](https://modelcontextprotocol.io/) server that lets AI agents read from and write to [Zellij](https://zellij.dev/) terminal sessions. ~200 lines of Python, zero dependencies, SSH support built-in.

## Why This Exists

The existing [zellij-mcp-server](https://github.com/GitJuhb/zellij-mcp-server) has 60+ tools, requires Node.js/TypeScript, and floods the LLM context with tool definitions it will never use. This project takes the opposite approach: **3 tools that cover 99% of real usage**.

### Comparison

- **zellij-mcp-lite**: 208 lines · 0 dependencies · 3 tools · SSH built-in · Copy one file
- **zellij-mcp-server**: ~2000+ lines · Node.js + deps · 60+ tools · No SSH · npm install

## Why Minimalist Matters

- **Token budget** — Every tool definition eats context tokens. 3 tools ≈ 40 tokens. 60 tools ≈ 800+ tokens. That's context your LLM could use for actual reasoning.
- **Less noise** — LLMs pick the right tool faster when there are fewer choices.
- **Less attack surface** — Fewer tools = fewer ways things can go wrong.
- **Zero dependencies** — No `node_modules`, no virtualenv, no supply chain risk. Just Python stdlib.

## Quick Start

### Option A: Copy the file (recommended)

```bash
curl -o server.py https://raw.githubusercontent.com/quarkex/zellij-mcp-lite/main/server.py
# That's it. Run with: python3 server.py
```

### Option B: pip install

```bash
pip install zellij-mcp-lite
# Run with: zellij-mcp-lite
```

## Configuration

### Claude Desktop (`~/.config/claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "zellij": {
      "command": "python3",
      "args": ["/path/to/server.py"]
    }
  }
}
```

### Hermes Agent (`~/.hermes/config.yaml`)

```yaml
mcp_servers:
  zellij:
    command: python3
    args:
      - /path/to/server.py
```

### Generic MCP Client

Any MCP client that supports stdio transport:

```json
{
  "command": "python3",
  "args": ["/path/to/server.py"],
  "transport": "stdio"
}
```

## Tools

### `zellij_read`

Read the content of the focused pane in a Zellij session.

| Parameter | Type | Description |
|-----------|------|-------------|
| `host` | string | SSH host or `"local"` (default: `"local"`) |
| `session` | string | Session name. Auto-detects if only one active. |
| `tail` | integer | Only return last N lines |
| `full` | boolean | Include full scrollback (not just viewport) |

```json
{"name": "zellij_read", "arguments": {"tail": 20}}
```

### `zellij_write`

Type text into the focused pane. Like pressing keys on the keyboard.

| Parameter | Type | Description |
|-----------|------|-------------|
| `host` | string | SSH host or `"local"` (default: `"local"`) |
| `session` | string | Session name. Auto-detects if only one active. |
| `text` | string | **Required.** Text to type. |
| `enter` | boolean | Append Enter after text (default: false) |

```json
{"name": "zellij_write", "arguments": {"text": "cargo build", "enter": true}}
```

### `zellij_list_sessions`

List all Zellij sessions, showing active vs exited.

| Parameter | Type | Description |
|-----------|------|-------------|
| `host` | string | SSH host or `"local"` (default: `"local"`) |

```json
{"name": "zellij_list_sessions", "arguments": {}}
```

## SSH Support

Every tool accepts a `host` parameter. Set it to any SSH host from your `~/.ssh/config`:

```json
{"name": "zellij_read", "arguments": {"host": "my-server", "tail": 50}}
```

This lets an AI agent interact with terminals on remote machines — no extra setup beyond having SSH access.

## Auto-Detection

If you have exactly one active Zellij session, you never need to specify `session`. The server detects it automatically. If there are multiple sessions, it returns the list so the LLM can pick one.

## Use Cases

- **AI pair-programming** — Let your LLM read compiler output, run commands, check test results
- **Remote terminal interaction** — Agent operates terminals on remote servers via SSH
- **Build monitoring** — AI watches build output and reacts to errors
- **REPL interaction** — Feed code into Python/Node/etc REPLs and read results

## License

MIT — Manlio García, 2025
