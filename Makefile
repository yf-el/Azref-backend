.PHONY: help sync dev down test lint fmt tf-init tf-plan tf-apply tf-destroy tf-bootstrap

help:
	@echo "Targets:"
	@echo "  sync          uv sync (install all workspace members + dev tools)"
	@echo "  dev           docker compose up (postgres + redis + services)"
	@echo "  down          docker compose down"
	@echo "  test          run pytest across the workspace"
	@echo "  lint          ruff check"
	@echo "  fmt           ruff format"
	@echo "  tf-bootstrap  one-shot: create S3 state bucket + DynamoDB lock table"
	@echo "  tf-init       terraform init (envs/dev)"
	@echo "  tf-plan       terraform plan (envs/dev)"
	@echo "  tf-apply      terraform apply (envs/dev)"
	@echo "  tf-destroy    terraform destroy (envs/dev)"

sync:
	uv sync --all-packages --all-groups

dev:
	docker compose -f docker-compose.dev.yml up --build

down:
	docker compose -f docker-compose.dev.yml down

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

tf-bootstrap:
	bash scripts/tf-bootstrap.sh

tf-init:
	cd infra/terraform/envs/dev && terraform init

tf-plan:
	cd infra/terraform/envs/dev && terraform plan

tf-apply:
	cd infra/terraform/envs/dev && terraform apply

tf-destroy:
	cd infra/terraform/envs/dev && terraform destroy
