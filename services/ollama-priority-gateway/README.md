# Ollama priority gateway

This service is the single access point to the Ollama instance on
`prometheus-ts`.

- Ollama itself runs behind the gateway on `127.0.0.1:11433`.
- Other local programs use `127.0.0.1:11434` (third priority).
- FlipFlop development clients use `127.0.0.1:11435` (second priority).
- Production reaches `prometheus-ts:11436` over Tailscale/SSH (first priority).
- Up to four generation requests are forwarded at a time, matching
  `OLLAMA_NUM_PARALLEL=4`. Waiting production requests are selected before
  development, then other applications, whenever a slot becomes available.

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
the gateway with four generation slots, and leaves the standard `11434`
address available for other programs. On Omarchy, run the equivalent two
processes under systemd.

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
| `OLLAMA_GATEWAY_CONCURRENCY` | `4` | Maximum Ollama generation requests forwarded at once |
| `OLLAMA_NUM_PARALLEL` | `4` | Engine parallel generations; set by the Windows launcher |

`start-all-servers.ps1` checks the live gateway health values and restarts the
local Ollama/gateway processes when either side is not configured for four or the GPU-only guard is disabled.
That reconfiguration interrupts any inference currently in flight, so start
the development stack after the active scan queue has drained.

Health and read-only Ollama endpoints (`/api/tags`, `/api/version`, and
`/api/ps`) bypass the generation queue. Generation endpoints are streamed
without buffering.

The health values describe configured limits, not verified model parallelism.
Ollama 0.32.6 forces the `qwen35` architecture (`qwen3.5:4b`) to one runner
slot, even with `OLLAMA_NUM_PARALLEL=4`. Check the engine startup log for
`model architecture does not currently support parallel requests` and
`n_slots` before claiming four simultaneous generations. Real four-way
inference requires a supported model architecture as well as these settings.

FlipFlop development uses `qwen3:4b` for both primary LLM calls and canonical
product extraction (`DEV_CPK_OLLAMA_MODEL`). Production model selection remains
deployment-configured. The extraction route uses a 2,048-token context and
128-token prompt batch with reasoning disabled. No cloud fallback is used for
this override. Normal MPN/source-identity matching still runs before model
extraction.


## GPU-only inference

Generation preloads the requested model without a prompt, requesting GPU offload
with the same runner options, then checks `/api/ps`. CPU-only and partially
offloaded models return HTTP 503 before the user prompt is forwarded. Read-only
health/model endpoints remain available. Startup checks GPU placement rather than
calling CPU warm-up a success. This policy concerns model inference: tokenization,
HTTP handling and other host work still use the CPU.

A smaller model does not fix failed GPU discovery. Inspect the timestamped
`logs/ollama-*.err.log` files produced by the launcher. Restarting this shared
service interrupts development and production inference; obtain approval first.
The private upstream port is an internal engine endpoint; GPU-only enforcement
applies to clients using the three gateway listeners.
