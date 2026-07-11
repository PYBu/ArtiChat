# ArtiChat

ArtiChat is a self-hosted AI chat workspace for local and API-backed language models. It includes chat, knowledge retrieval, tool integrations, user management, and an admin console.

## Quick Start

### Docker Compose

```bash
docker compose -p artichat up -d --build artichat
```

ArtiChat will be available at:

```text
http://localhost:3000
```

The default application data volume is:

```text
artichat_data
```

### Local Development

```bash
npm install
npm run dev
```

Backend dependencies are managed from the Python project files in this repository. Use the existing Docker workflow when you want the frontend and backend packaged together.

## Common Configuration

Create or update your environment file from `.env.example`, then restart the service.

Useful settings include:

```text
ARTICHAT_PORT=3000
OLLAMA_BASE_URL=http://host.docker.internal:11434
OPENAI_API_KEY=your_key_here
WEBUI_SECRET_KEY=change_me
```

## Docker Operations

Build the local image:

```bash
docker compose -p artichat build artichat
```

Start or restart the service:

```bash
docker compose -p artichat up -d artichat
```

Check status:

```bash
docker compose -p artichat ps
```

Check health:

```bash
curl http://localhost:3000/health
```

Stop the service:

```bash
docker compose -p artichat down
```

## Verification

Run the branding guard:

```bash
npm run test:branding
```

Build the frontend bundle:

```bash
npm run build
```

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for local connection and Docker checks.
