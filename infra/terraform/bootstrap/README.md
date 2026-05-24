# Terraform bootstrap

One-shot: provisions the S3 state bucket + DynamoDB lock table that the rest of
the stack uses as its remote backend.

## When to run

Exactly once per AWS account, the very first time you set up the project.

## How to run

```bash
cd infra/terraform/bootstrap
terraform init
terraform apply -var="project_name=azref" -var="aws_region=eu-west-3"
```

Copy the two output values (`state_bucket`, `state_lock_table`) into
[../envs/dev/backend.tf](../envs/dev/backend.tf).

## Why it's separate

The state backend can't store its own state, so this stack uses local state
(committed-with-care to `.gitignore`). Once it's up, the rest of the stack
uses S3 + DynamoDB and you never touch this again.
