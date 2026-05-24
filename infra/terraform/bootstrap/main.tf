# One-shot bootstrap: creates the S3 bucket + DynamoDB table that hold Terraform state
# for the rest of the stack. Run this once with local state, then point envs/dev at it.
#
# Usage:
#   cd infra/terraform/bootstrap
#   terraform init
#   terraform apply -var="project_name=azref" -var="aws_region=eu-west-3"
#   # Copy the outputs into infra/terraform/envs/dev/backend.tf

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "project_name" {
  type        = string
  description = "Short project slug, used as prefix for all resources."
  default     = "azref"
}

variable "aws_region" {
  type    = string
  default = "eu-west-3"
}

# S3 bucket names are globally unique; append the account id to avoid collisions.
data "aws_caller_identity" "current" {}

locals {
  bucket_name = "${var.project_name}-tfstate-${data.aws_caller_identity.current.account_id}"
  lock_table  = "${var.project_name}-tfstate-lock"
}

resource "aws_s3_bucket" "tfstate" {
  bucket = local.bucket_name

  # Protect against accidental destroy during early experimentation.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tfstate_lock" {
  name         = local.lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

output "state_bucket" {
  value       = aws_s3_bucket.tfstate.id
  description = "Put this in envs/dev/backend.tf under 'bucket ='"
}

output "state_lock_table" {
  value       = aws_dynamodb_table.tfstate_lock.name
  description = "Put this in envs/dev/backend.tf under 'dynamodb_table ='"
}

output "aws_region" {
  value = var.aws_region
}
