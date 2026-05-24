.PHONY: help dev down test lint fmt tf-init tf-plan tf-apply tf-destroy tf-bootstrap

help:
	@echo "Targets:"
	@echo "  dev           docker compose up (postgres + auth-backend)"
	@echo "  down          docker compose down"
	@echo "  test          run pytest for auth-backend"
	@echo "  lint          ruff check"
	@echo "  fmt           ruff format"
	@echo "  tf-bootstrap  one-shot: create S3 state bucket + DynamoDB lock table"
	@echo "  tf-init       terraform init (envs/dev)"
	@echo "  tf-plan       terraform plan (envs/dev)"
	@echo "  tf-apply      terraform apply (envs/dev)"
	@echo "  tf-destroy    terraform destroy (envs/dev)"

dev:
	docker compose -f docker-compose.dev.yml up --build

down:
	docker compose -f docker-compose.dev.yml down

test:
	cd services/auth-backend && python -m pytest -q

lint:
	cd services/auth-backend && ruff check app tests

fmt:
	cd services/auth-backend && ruff format app tests

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
