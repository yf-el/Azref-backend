# azref-platform

Backend mono-repo for **[huquqai.ma](https://huquqai.ma) / [azref.ma](https://azref.ma)** — an AI assistant for Moroccan law that answers legal questions in French and Arabic with citations from the official corpus (Bulletin officiel, Cour de cassation, Adala, etc.).

> The **frontend** (Next.js) lives in a separate repository. This repo is API-only.

## Table of contents

- [What's in here](#whats-in-here)
- [Architecture](#architecture)
- [Layout](#layout)
- [Services](#services)
- [Shared libs](#shared-libs)
- [Event topics](#event-topics)
- [Running locally](#running-locally)
- [Infrastructure](#infrastructure)
- [Deployment](#deployment)
- [Production endpoints](#production-endpoints)

## What's in here

Three independently deployable backend services, plus four shared Python libraries, plus the Terraform that provisions everything on AWS.

- **`users-service`** — owns the user account / profile / onboarding lifecycle (Clerk-authenticated). Emits user events.
- **`agent`** — answers legal questions. ReAct loop over a multi-LLM cascade with retrieval over an external legal corpus DB. Emits Q&A events.
- **`crm-sync-lambda`** — Kafka consumer (via Confluent's managed AWS Lambda Sink Connector) that upserts onboarded users into Salesforce.

The services don't call each other synchronously. They communicate **only via Kafka events** (Confluent Cloud) on the `azref.user.events` and `azref.agent.events` topics. The shared `kafka_events` lib defines the Pydantic schemas every producer and consumer agrees on.

## Architecture

```
                                ┌─────────────────────────────────────────┐
                                │     huquqai-web (separate repo)         │
   end-user / dev ──browses──▶  │     Next.js frontend                    │  ◀── Clerk SDK
                                └────┬───────────────────────┬────────────┘
                                     │ Bearer JWT (Clerk)    │
                                     ▼                       ▼
                          ┌──────────────────┐    ┌──────────────────┐
                          │  users-service   │    │      agent       │
                          │   (FastAPI)      │    │    (FastAPI)     │
                          │  Clerk JWT auth  │    │  Clerk JWT auth  │
                          │  RDS Postgres    │    │  Redis cache     │
                          │  + Alembic       │    │  LLM cascade:    │
                          │                  │    │  Groq → Cerebras │
                          │                  │    │       → Mistral  │
                          └────┬─────────────┘    └──┬───────────┬───┘
                               │                    │           │
                               │                    │           │ full-text search
                               │                    │           │ (tsvector + ILIKE)
                               │                    │           ▼
                               │                    │   ┌─────────────────────┐
                               │                    │   │ Legal corpus DB     │
                               │                    │   │ (external Postgres, │
                               │                    │   │  read-only)         │
                               │                    │   └─────────────────────┘
                               │ produces           │ produces
                               ▼                    ▼
                   ┌──────────────────────────────────────────────┐
                   │      Confluent Cloud (Kafka, SASL_SSL)       │
                   │   topics: azref.user.events                  │
                   │           azref.agent.events                 │
                   └────┬─────────────────────────────────────────┘
                        │ Confluent AWS Lambda Sink Connector
                        │ (filtered to user.onboarded.v1)
                        ▼
                   ┌─────────────────────┐         ┌──────────────────┐
                   │  crm-sync-lambda    │ ──upsert▶│   Salesforce     │
                   │  (AWS Lambda)       │  Contact│  (JWT bearer)    │
                   └─────────────────────┘         └──────────────────┘
```

Key design choices:
- **Event-driven, never service-to-service**. Adding a new consumer (analytics, billing, etc.) means subscribing to a topic — no changes to producers.
- **Kafka producers are lazy and fail-safe**. If Confluent is unreachable, HTTP requests still succeed — the publish is a fire-and-forget `publish_nowait`.
- **Two Postgres databases.** The platform RDS holds the user accounts (`users-service`). The legal corpus (laws, articles, document chunks) lives in a **separate read-only Postgres** that the agent queries via full-text search (`tsvector` + `ILIKE`) — it's owned by a different ingestion pipeline. No vector embeddings are used yet; switching to pgvector / hybrid search is on the roadmap.
- **No shared HTTP gateway.** Each service is exposed on its own subdomain, with TLS terminated by Caddy on the EC2 instance.

### Cost-driven choices (open-source side project, ~$0 target)

This is an open-source side project, self-funded. The platform is engineered to stay inside AWS Free Tier and the free quotas of managed services — every choice below is "what's the cheapest option that's still production-shaped?". The architecture reflects that:

| Decision | Cheaper option chosen | What it replaces | Why it's fine for now |
|---|---|---|---|
| Secrets | **SSM Parameter Store** (Standard tier, free) | AWS Secrets Manager (~$0.40/secret/month) | We don't need automatic rotation yet; SecureString + KMS default key is enough. |
| TLS / reverse proxy | **Caddy on EC2** (auto Let's Encrypt) | ALB (~$16/month minimum + LCU) | Single instance per service, no path-based routing needed. |
| Compute | **t3.micro EC2** (one per service) | ECS Fargate / EKS | Two services × t3.micro fit comfortably in free tier; deploy = SSM Run Command pulls new image. |
| Database | **db.t3.micro RDS**, single-AZ | Multi-AZ RDS / Aurora Serverless | No HA SLA to honour yet; daily backup retention is enough. |
| Cache | **cache.t3.micro Redis**, 1 node, no auth | ElastiCache cluster mode / Redis Cloud | Intra-VPC only, security group restricts access. |
| Network | **No NAT Gateway** (services run in public subnets behind SGs) | NAT GW (~$32/month + traffic) | EC2 instances need outbound to the internet (LLMs, Confluent); NAT alone would cost more than the rest of the stack. |
| Kafka | **Confluent Cloud free tier** | MSK / self-hosted Kafka on EC2 | Throughput and storage caps are way above our current volume; managed = no ops. |
| LLM | **Groq → Cerebras → Mistral cascade** (free tiers) | OpenAI / Anthropic paid APIs | Free quotas + cascade gives us a generous effective rate limit; quality is good enough for v1. |
| CRM sync | **AWS Lambda** | Always-on EC2 worker | Onboarding events are sparse; Lambda free tier (1M req/month) is untouchable at this scale. |
| ECR | **Lifecycle policy: keep last N images** | unlimited retention | Keeps ECR storage in free tier (500 MB/month). |

The cost ceiling I'm optimising for is the AWS bill — **target < $5/month** out of my own pocket. If the project ever needs to scale beyond that, the obvious upgrades are: multi-AZ RDS, ALB for path-based routing, Secrets Manager for rotation, a paid LLM provider, and an MSK or higher Confluent tier.

## Layout

```
services/             one folder per service, each independently buildable & deployable
  agent/              FastAPI — legal RAG agent
  users-service/      FastAPI — user accounts + onboarding
  crm-sync-lambda/    AWS Lambda (SAM) — Salesforce sink

libs/                 shared Python packages, mounted under /libs in every container
  auth_clerk/         Clerk JWT verification (JWKS) + FastAPI dependency
  kafka_events/       aiokafka producer wrapper + Pydantic event schemas
  cache_semantic/     Redis cache decorators (currently exact-match only)
  crm/                CRM port (interface) + Salesforce adapter

infra/terraform/      Multi-stack Terraform (S3 remote state)
  bootstrap/          one-shot: S3 state bucket + DynamoDB lock table
  github-oidc/        GitHub Actions OIDC role (no long-lived AWS creds in CI)
  network/            VPC, subnets, security groups
  platform/           shared infra: RDS Postgres, ElastiCache Redis, ECRs, SSM params
  services/agent/             agent EC2 + IAM
  services/users-service/     users-service EC2 + IAM

.github/workflows/    one CI workflow per service, triggered on path changes
scripts/              helper scripts
```

## Services

| Service | Stack | Local port | Prod host |
|---|---|---|---|
| [`users-service`](services/users-service) | FastAPI · SQLAlchemy async · Alembic · Postgres | `8000` | [`users-service.azref.ma`](https://users-service.azref.ma) |
| [`agent`](services/agent) | FastAPI · asyncpg · Redis · multi-LLM (Groq/Cerebras/Mistral) | `8001` | [`agent.azref.ma`](https://agent.azref.ma) |
| [`crm-sync-lambda`](services/crm-sync-lambda) | AWS Lambda (Python 3.13 · arm64) · SAM · `simple-salesforce` | — | — (invoked by Confluent) |

### `users-service`
Single source of truth for user identity within the platform.
- `GET /me` / `PATCH /me` — read or update the current user; auto-creates the row on first call from a Clerk JWT.
- Emits `user.signed_up.v1` on first contact, `user.onboarded.v1` when profession + usage_type are both set, `user.profile_updated.v1` on subsequent edits.
- First-touch marketing attribution is sent by the front as a `X-Signup-Attribution` header (URL-encoded JSON) and attached to `user.signed_up.v1`.

### `agent`
ReAct loop (`reason → act → observe`, max 5 steps) over an OpenAI-compatible tool-calling LLM. Per request:
1. LLM cascade tries **Groq → Cerebras → Mistral** in order; on rate-limit or transient failure it falls through to the next provider.
2. Tools available to the model: `search_all` (runs `tsvector` full-text search on `document_chunks` + `ILIKE` lookups on `lois` and `articles` in parallel), `get_article` (fetch a specific article by law + number).
3. The final answer is returned with structured `sources[]` (laws, articles, document chunks with PDF URLs when available).
4. Whole answers are cached in Redis for 24h on the **exact** question string (`cache_exact` decorator). The semantic-cache decorator exists in `libs/cache_semantic` but is not wired in yet.
5. Emits `agent.question_answered.v1` (fire-and-forget) for every answered question.

### `crm-sync-lambda`
Stateless Lambda consumer. Confluent Cloud's managed **AWS Lambda Sink Connector** pushes records from `azref.user.events` into this function. The handler:
1. Parses each record into the `UserEvent` discriminated union (`kafka_events.schemas`).
2. Filters for `user.onboarded.v1` (other event types are skipped in v1).
3. Maps to a Salesforce Contact and upserts via External ID (idempotent — safe under at-least-once delivery).
4. Auth to SF uses the **JWT Bearer flow** (RSA key in Lambda env, paired with a cert uploaded to a Salesforce External Client App).

## Shared libs

Mounted at `/libs` inside every container (and zipped into the Lambda package). Editable from any service.

| Lib | Purpose |
|---|---|
| [`libs/auth_clerk`](libs/auth_clerk) | Clerk JWT verification via JWKS, FastAPI `get_current_clerk_user` dependency, `ClerkClaims` model. |
| [`libs/kafka_events`](libs/kafka_events) | `aiokafka` producer wrapper (lazy connect, SASL_SSL Confluent defaults, fire-and-forget `publish_nowait`) + Pydantic event schemas with `event_type` discriminators. |
| [`libs/cache_semantic`](libs/cache_semantic) | Redis client + `cache_exact` decorator (used by the agent). A `cache_semantic` decorator is scaffolded for future embedding-based deduplication but not enabled. |
| [`libs/crm`](libs/crm) | Hexagonal `CrmClient` port + `SalesforceCrmClient` adapter built on `simple-salesforce`. Used by `crm-sync-lambda`. |

## Event topics

Schemas live in [`libs/kafka_events/schemas/`](libs/kafka_events/schemas) and are versioned in the type name (`*V1`). Adding a new event = add a class, add it to the discriminated union, ship.

| Topic | Producer | Event types | Consumers |
|---|---|---|---|
| `azref.user.events` | `users-service` | `user.signed_up.v1`, `user.onboarded.v1`, `user.profile_updated.v1` | `crm-sync-lambda` (only `user.onboarded.v1`) |
| `azref.agent.events` | `agent` | `agent.question_answered.v1` | — (analytics planned) |

Partition key = `user_id` (Clerk subject) on every event, so all events for one user land on the same partition and stay ordered.

## Running locally

Requires **Docker + Docker Compose**. Each service has a `.env.example` — copy to `.env` before starting:

```bash
cp services/users-service/.env.example services/users-service/.env
cp services/agent/.env.example         services/agent/.env

make dev          # postgres + redis + users-service + agent
make down         # stop everything
```

Kafka is **not** part of the local stack — the producer is lazy and silently no-ops if Confluent isn't reachable, so the services run fine without it. Point the env at a Confluent cluster only when you need to test the event path end-to-end.

The agent's `DATABASE_URL` should point at a Postgres instance containing the legal corpus schema (this is owned by a separate ingestion pipeline and not provisioned here). Without it, the agent boots but the search tools return empty results.

Once up:

| | URL |
|---|---|
| users-service health / Swagger | http://localhost:8000/health · http://localhost:8000/docs |
| agent health / Swagger | http://localhost:8001/health · http://localhost:8001/docs |
| Postgres (local) | `localhost:5433` — user/pass/db: `azref` |
| Redis | `localhost:6379` |

Hot-reload is enabled: `services/<name>/app` and `libs/` are bind-mounted, so edits trigger uvicorn reload automatically.

Per-service tests:

```bash
cd services/users-service     && python -m pytest -q
cd services/agent             && python -m pytest -q
cd services/crm-sync-lambda   && python -m pytest -q
```

## Infrastructure

All AWS, region `eu-west-1`. Terraform is split into independent stacks with S3 remote state; downstream stacks read upstream outputs via `terraform_remote_state`.

```
bootstrap        →  S3 state bucket + DynamoDB lock table  (run once, locally)
github-oidc      →  IAM role assumed by GitHub Actions via OIDC
network          →  VPC, public/private subnets, security groups
platform         →  RDS Postgres, ElastiCache Redis, ECR repos, shared SSM params (Kafka creds)
services/<name>  →  EC2 instance (Caddy + Docker), IAM role, per-service SSM params
```

Resource sizing is intentionally minimal (t3.micro EC2, db.t3.micro RDS, cache.t3.micro Redis, single-AZ) — free-tier friendly while we're pre-revenue.

Secrets and per-environment config live in **SSM Parameter Store** under `/<project>/<env>/<service>/`. Each service's `deploy.sh` fetches its namespace via `aws ssm get-parameters-by-path` at container start.

## Deployment

CI/CD per service via GitHub Actions, no long-lived AWS credentials (OIDC).

**EC2 services** (`agent`, `users-service`):
1. Push to `main` touching the relevant paths triggers the workflow in [`.github/workflows/`](.github/workflows/).
2. Action authenticates to AWS via OIDC, builds the Docker image, pushes to ECR.
3. SSM Run Command (targeting the EC2 by tag) pulls the new image and restarts the container.
4. Caddy on the instance terminates TLS (auto-provisioned via Let's Encrypt) and reverse-proxies to the container.

**Lambda service** (`crm-sync-lambda`):
1. Push triggers the workflow, which runs `pytest` then `sam build && sam deploy`.
2. SAM updates the CloudFormation stack and publishes a new Lambda version.
3. The Confluent Cloud AWS Lambda Sink Connector points at the function ARN and resumes consuming from its committed offset.

Terraform changes are applied **manually** from a workstation (not in CI yet):

```bash
make tf-bootstrap                              # one-shot, only on first setup
cd infra/terraform/<stack> && terraform init   # network, platform, services/agent, ...
                              terraform plan
                              terraform apply
```

## Production endpoints

| Service | URL | Docs |
|---|---|---|
| users-service | https://users-service.azref.ma | https://users-service.azref.ma/docs |
| agent | https://agent.azref.ma | https://agent.azref.ma/docs |
| crm-sync-lambda | — | invoked by Confluent Sink Connector, no HTTP surface |
