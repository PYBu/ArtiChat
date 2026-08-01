# ArtiChat Troubleshooting

## Server Connection Error

Confirm the container is running:

```bash
docker compose -p artichat ps
```

Confirm the health endpoint responds:

```bash
curl http://localhost:3000/health
```

If the service is not healthy, inspect recent logs:

```bash
docker logs --tail 200 artichat
```

## Ollama Connection

When ArtiChat runs inside Docker, the browser talks to ArtiChat first. ArtiChat then forwards Ollama requests from the backend using `OLLAMA_BASE_URL`.

For Docker Desktop on Windows or macOS, use:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

For Linux host networking, you can use:

```bash
docker run -d --network=host -v artichat_data:/app/backend/data -e OLLAMA_BASE_URL=http://127.0.0.1:11434 --name artichat --restart always artichat:main
```

## Timeouts

Long model responses may need a higher backend timeout:

```text
AIOHTTP_CLIENT_TIMEOUT=600
```

Restart the service after changing environment values:

```bash
docker compose -p artichat up -d artichat
```

## Rebuild

After code or dependency changes:

```bash
docker compose -p artichat build artichat
docker compose -p artichat up -d artichat
```
