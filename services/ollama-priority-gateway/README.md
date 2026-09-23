# Ollama priority gateway

This service is the single access point to the Ollama instance on
`prometheus-ts`.

- Ollama itself remains on `127.0.0.1:11434`.
- Development clients use `127.0.0.1:11435`.
- Production reaches `prometheus-ts:11436` over Tailscale/SSH.
- Only one generation request is forwarded at a time. Waiting production
  requests are always selected before waiting development requests.

The gateway does not pre-empt a request that is already running. This is
intentional: interrupting a streamed Ollama response would make callers fail
and would not reliably release GPU memory.

## Run locally

```powershell
python -m pip install -r services/ollama-priority-gateway/requirements.txt
python services/ollama-priority-gateway/server.py
```

The service binds the development listener to loopback and the production
listener to all interfaces. Restrict port `11436` to the Tailscale interface
with the host firewall when deploying on Linux.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_UPSTREAM_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `DEV_LISTEN_HOST` | `127.0.0.1` | Development bind address |
| `DEV_LISTEN_PORT` | `11435` | Development listener |
| `PROD_LISTEN_HOST` | `0.0.0.0` | Production bind address |
| `PROD_LISTEN_PORT` | `11436` | Production listener |
| `OLLAMA_GATEWAY_MAX_QUEUE` | `100` | Maximum waiting requests per listener |

Health and read-only Ollama endpoints (`/api/tags`, `/api/version`, and
`/api/ps`) bypass the generation queue. Generation endpoints are streamed
without buffering.
