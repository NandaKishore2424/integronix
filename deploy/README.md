# Deployment

The API runs on one EC2 instance (t3.small, Mumbai) that is started only for demos.
CI builds and smoke-tests the image and publishes it to GHCR; the host only pulls.

```
git push main ─▶ GitHub Actions: tests ─▶ build ─▶ boot + smoke test ─▶ push ghcr.io/…/integronix-backend:{main,sha-<commit>}
EC2 boot ─▶ desec-update (DNS → new public IP) ─▶ integronix.service (compose pull + up) ─▶ nginx :443 ─▶ 127.0.0.1:8000
```

| File in repo | Path on the host |
|---|---|
| `compose.yml` | `/opt/integronix/compose.yml` |
| — (secrets, never in git) | `/opt/integronix/app.env` (root, 0600) |
| `systemd/integronix.service` | `/etc/systemd/system/integronix.service` |
| `bin/integronix-deploy` | `/usr/local/bin/integronix-deploy` |
| `nginx/integronix.conf` | `/etc/nginx/sites-available/integronix` (linked in sites-enabled) |
| `nginx/conf.d-ratelimit.conf` | `/etc/nginx/conf.d/ratelimit.conf` |
| `nginx/conf.d-security.conf` | `/etc/nginx/conf.d/security.conf` |
| `bin/certbot-deploy-hook-reload-nginx` | `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx` |
| `bin/desec-update` | `/usr/local/sbin/desec-update` (token in `/etc/desec/token`, root, 0600) |
| `systemd/desec-update.{service,timer}` | `/etc/systemd/system/` |

## Everyday use

```bash
sudo integronix-deploy                 # roll onto the newest :main
sudo integronix-deploy sha-<commit>    # roll back to a specific build
docker compose -f /opt/integronix/compose.yml logs -f api
```

`app.env` holds `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`,
`GROQ_API_KEY`, `GROQ_MODEL` and `CORS_ALLOW_ORIGINS`. The database connection
string is deliberately absent: the API reaches Postgres only through the
Supabase REST API.
