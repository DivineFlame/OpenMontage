# Deploying OpenMontage On Dokploy

OpenMontage is an agent-operated video production toolkit, not a full public web
application. Deploy it in Dokploy as a Docker Compose worker/service, then run
production commands through the container shell or Dokploy terminal.

## Compose

Use the repository's `docker-compose.yml` in Dokploy.

The Compose stack includes only `openmontage`.

OpenMontage is exposed on host port `3003` for a lightweight Jobs API. New jobs
auto-render a prompt-based Remotion MP4 when `OPENMONTAGE_AUTO_RENDER=true`.

```text
http://your-server-ip:3003/health
http://your-server-ip:3003/jobs
```

The OpenMontage container includes:

- Python 3.11 and the OpenMontage core dependencies
- FFmpeg and FFprobe
- Node.js/npm
- Chromium for Remotion rendering
- Remotion dependencies from `remotion-composer/package-lock.json`
- Piper TTS for zero-key local narration

Persistent outputs are stored in Docker volumes for:

- `/app/projects`
- `/app/output`
- `/app/pipeline`
- `/app/library`
- `/workspace`

API job records are stored under:

```text
/workspace/openmontage-api/jobs
```

Rendered job outputs are stored under:

```text
/app/output/openmontage-api
```

## Ollama On The Dokploy Host

If Ollama runs directly on the same VPS as Dokploy, bind Ollama to all interfaces
or at least to the Docker bridge-reachable host, then use Docker's host gateway:

```env
OPENMONTAGE_LLM_PROVIDER=ollama
OPENMONTAGE_LLM_MODEL=qwen3-coder:30b
OPENMONTAGE_LLM_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3-coder:30b
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

The compose file includes:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

That maps `host.docker.internal` to the Linux Docker host gateway.

## Ollama As A Separate Dokploy Service

If you deploy Ollama as another Compose service on the same network, point
OpenMontage at that service name instead:

```env
OPENMONTAGE_LLM_PROVIDER=ollama
OPENMONTAGE_LLM_MODEL=qwen3-coder:30b
OPENMONTAGE_LLM_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen3-coder:30b
OLLAMA_BASE_URL=http://ollama:11434
```

## Useful Dokploy Environment Variables

```env
OPENMONTAGE_LLM_PROVIDER=ollama
OPENMONTAGE_LLM_MODEL=qwen3-coder:30b
OPENMONTAGE_LLM_BASE_URL=http://host.docker.internal:11434
OPENMONTAGE_LLM_TEMPERATURE=0.7
OPENMONTAGE_LLM_MAX_TOKENS=4096

OLLAMA_MODEL=qwen3-coder:30b
OLLAMA_BASE_URL=http://host.docker.internal:11434

OPENMONTAGE_CACHE_DIR=/workspace/cache
OPENMONTAGE_API_STATE_DIR=/workspace/openmontage-api
OPENMONTAGE_AUTO_RENDER=true
OPENMONTAGE_RENDER_OUTPUT_DIR=/app/output/openmontage-api
OPENMONTAGE_PORT=3003

# Optional provider keys
FAL_KEY=
GOOGLE_API_KEY=
ELEVENLABS_API_KEY=
OPENAI_API_KEY=
XAI_API_KEY=
PEXELS_API_KEY=
PIXABAY_API_KEY=
UNSPLASH_ACCESS_KEY=
SUNO_API_KEY=
HEYGEN_API_KEY=
RUNWAY_API_KEY=
HF_TOKEN=
```

## Smoke Checks

After Dokploy builds the service, open the container terminal and run:

```bash
python -c "from lib.config_model import OpenMontageConfig; print(OpenMontageConfig.load().llm.model_dump())"
curl http://localhost:3003/health
curl -X POST http://localhost:3003/jobs \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Make a 30-second animated explainer about local AI.","pipeline":"animated-explainer","render_runtime":"remotion"}'
curl http://localhost:3003/jobs/<job_id>
curl http://localhost:3003/jobs/<job_id>/outputs
curl -o final.mp4 http://localhost:3003/jobs/<job_id>/outputs/final.mp4
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"
cd remotion-composer && npx remotion --version
ffmpeg -version
```

## LibreChat Schema Files

OpenMontage does not serve `/openapi.json` from the runtime container. For
LibreChat Actions, use the static schema in this repository instead:

```text
docs/librechat/openmontage.openapi.json
```

The matching LibreChat config sample is:

```text
docs/librechat/librechat.yaml
```

Before pasting the schema into LibreChat, update the `servers[0].url` value if
your LibreChat container reaches OpenMontage through a different address than:

```text
http://host.docker.internal:3003
```

In LibreChat, create a job, then ask the agent to check the job status until it
is `completed`. The rendered video URL is:

```text
http://host.docker.internal:3003/jobs/<job_id>/outputs/final.mp4
```
