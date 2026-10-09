# Ollama priority gateway

This service is the single access point to the Ollama instance on
`prometheus-ts`.

- Ollama itself runs behind the gateway on `127.0.0.1:11433`.
- Other local programs use `127.0.0.1:11434` (third priority).
- FlipFlop development clients use `127.0.0.1:11435` (second priority).
- Production reaches `prometheus-ts:11436` over Tailscale/SSH (first priority).
- Only one generation request is forwarded at a time. Waiting production
  requests are always selected before development, then other applications.

The gateway does not pre-empt a request that is already running. This is
intentional: interrupting a streamed Ollama response would make callers fail
and would not reliably release GPU memory.

## Run locally

```powershell
python -m pip install -r services/ollama-priority-gateway/requirements.txt
python services/ollama-priority-gateway/server.py
```

On the current Windows development machine, use
`start-prometheus-services.ps1` at login. It moves Ollama to `11433`, starts
the gateway, and leaves the standard `11434` address available for other
programs. On Omarchy, run the equivalent two processes under systemd.

All listeners bind to loopback. Production reaches `11436` through the SSH
tunnel, so the gateway is never exposed directly to the LAN or tailnet.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_UPSTREAM_URL` | `http://127.0.0.1:11433` | Ollama endpoint |
| `OTHER_LISTEN_HOST` | `127.0.0.1` | Other-program bind address |
| `OTHER_LISTEN_PORT` | `11434` | Other-program listener |
| `DEV_LISTEN_HOST` | `127.0.0.1` | Development bind address |
| `DEV_LISTEN_PORT` | `11435` | Development listener |
| `PROD_LISTEN_HOST` | `127.0.0.1` | Production bind address |
| `PROD_LISTEN_PORT` | `11436` | Production listener |
| `OLLAMA_GATEWAY_MAX_QUEUE` | `100` | Maximum waiting requests per listener |

Health and read-only Ollama endpoints (`/api/tags`, `/api/version`, and
`/api/ps`) bypass the generation queue. Generation endpoints are streamed
without buffering.
