# azref-platform (mono-repo)

Refactor of [azref.ma](https://azref.ma) / HuquqAI into an event-driven microservices platform.

> **Status:** walking skeleton — one service (`auth-backend`), deployed to AWS EC2 via Terraform + GitHub Actions OIDC. Business services (events-gateway, worker, sf-connector) come next.

## Layout

```
services/         one folder per service, each independently buildable & deployable
libs/             shared Python packages (empty for now)
infra/terraform/  IaC: bootstrap (state backend) + modules + envs/dev
.github/workflows/  CI per service + deploy on push to main
docs/             architecture.md + ADRs
scripts/          helper scripts (tf-bootstrap, deploy)
```

## Walking skeleton — what works end-to-end

1. Push to `main` triggers GitHub Actions
2. Action authenticates to AWS via OIDC (no long-lived keys)
3. Build Docker image for `auth-backend`, push to ECR
4. SSM Run Command on the EC2 instance pulls the new image and restarts the container
5. `GET http://<ec2-public-ip>/health` returns `{"status": "ok"}`

## Getting started

See [docs/setup.md](docs/setup.md) for the full first-time setup (AWS account, Terraform bootstrap, GitHub repo wiring).

Local dev:

```bash
make dev          # docker compose up postgres + auth-backend
make test         # run pytest for auth-backend
curl localhost:8000/health
```

## Roadmap (post walking skeleton)

| Iteration | Adds |
|-----------|------|
| 1 (now) | auth-backend `/health` deployed via Terraform + CI/CD |
| 2 | Auth0 integration in auth-backend, RBAC + tenant_id claims, Alembic + RDS migration |
| 3 | `events-gateway` service + Redpanda (Kafka) producer |
| 4 | `enrichment-worker` service consuming Kafka, multi-LLM enrichment |
| 5 | `sf-connector` service pushing to Salesforce Custom Object |
| 6 | TLS (Caddy or ALB+ACM), proper observability |

See [docs/architecture.md](docs/architecture.md) for the target diagram.
