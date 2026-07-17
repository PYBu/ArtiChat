# 2026-07-06 AWS / 1Panel Deployment

## Target

- Server: `18.234.239.56`
- SSH user used: `ubuntu`
- Runtime user reported by server: `minierpcadmin`
- Existing services preserved: 1Panel OpenResty, artimage, PostgreSQL, searxng, searxng-valkey.

## Deployment Layout

- Container: `artichat-prod`
- Image: `artichat:main`
- Host port: `13000`
- Container port: `8080`
- Deploy directory: `/data/artichat-prod`
- Runtime data directory: `/data/artichat-prod/data`
- Compose file: `/data/artichat-prod/docker-compose.yaml`
- Secret configuration: `/data/artichat-prod/.env`

## Data Migration

- Local source volume: `artichat_data`
- Local backup file: `deploy-backups/artichat_data_20260706-185102.tar.gz`
- Server backup copy: `/data/artichat-prod/artichat_data_20260706-185102.tar.gz`
- Restored into: `/data/artichat-prod/data`
- The local `WEBUI_SECRET_KEY` was migrated into the server `.env` without printing the secret value.

## Verification

- `http://18.234.239.56:13000/health`: 200, `{"status":true}`.
- `http://18.234.239.56:13000/api/config`: 200, reports `ArtiChat`.
- `artichat-prod`: running healthy.
- Bind mount verified: `/data/artichat-prod/data -> /app/backend/data`.
- Existing containers remained running after deployment.

## Space

- `/data`: 20G total, 17G available after restore.
- `/`: 19G total, about 2.6G available after importing the Docker image.
- Docker build cache was pruned before deployment. Existing service images were not removed.

## Cleanup

- Local temporary image tar `deploy-backups/artichat-main-image.tar` was removed after upload/import.
- Server temporary image tar `/data/artichat-prod/artichat-main-image.tar` was removed after `docker load`.
- Server duplicate temporary `webui_secret_key.local` was removed after writing `.env`.
- Server stopped old recreated container was pruned, reclaiming about 56MB.

## Notes

- Root disk space is tighter because Docker image layers still live under `/var/lib/docker`.
- ArtiChat runtime data is on `/data`, so future app data growth should not consume the root disk.
- Moving Docker's global data root to `/data` would require Docker downtime and would affect existing 1Panel-managed containers, so it was not done.
