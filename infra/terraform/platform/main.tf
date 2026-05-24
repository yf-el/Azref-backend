locals {
  name_prefix     = "${var.project_name}-${var.env}"
  ssm_path_prefix = "/${var.project_name}/${var.env}/users-service"
}

# --- Read network stack outputs (from its remote state) ------------------

data "terraform_remote_state" "network" {
  backend = "s3"
  config = {
    bucket = "azref-tfstate-230148048244"
    key    = "network/terraform.tfstate"
    region = var.aws_region
  }
}

# --- RDS Postgres --------------------------------------------------------

resource "aws_db_subnet_group" "main" {
  name        = "${local.name_prefix}-db"
  subnet_ids  = data.terraform_remote_state.network.outputs.private_subnet_ids
  description = "Private subnets for platform RDS instances."

  tags = {
    Name = "${local.name_prefix}-db-subnet-group"
  }
}

resource "random_password" "db_master" {
  length           = 32
  special          = false # alphanumeric only — no URL-encoding hassles in DATABASE_URL
  override_special = ""
}

resource "aws_db_instance" "backend" {
  identifier        = "${local.name_prefix}-backend"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_master.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [data.terraform_remote_state.network.outputs.rds_sg_id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period   = var.db_backup_retention_days
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name_prefix}-backend-final"

  apply_immediately = true

  tags = {
    Name = "${local.name_prefix}-backend"
  }
}

# --- ECR repository ------------------------------------------------------

resource "aws_ecr_repository" "users_service" {
  name                 = "${local.name_prefix}/users-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${local.name_prefix}/users-service"
  }
}

resource "aws_ecr_lifecycle_policy" "users_service" {
  repository = aws_ecr_repository.users_service.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only the last ${var.ecr_image_retention_count} images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.ecr_image_retention_count
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# --- SSM Parameter Store -------------------------------------------------

resource "aws_ssm_parameter" "database_url" {
  name        = "${local.ssm_path_prefix}/DATABASE_URL"
  type        = "SecureString"
  value       = "postgresql+asyncpg://${var.db_username}:${random_password.db_master.result}@${aws_db_instance.backend.endpoint}/${var.db_name}"
  description = "PostgreSQL connection URL for users-service (includes password)."

  tags = {
    Name = "${local.ssm_path_prefix}/DATABASE_URL"
  }
}

resource "aws_ssm_parameter" "clerk_issuer" {
  name        = "${local.ssm_path_prefix}/CLERK_ISSUER"
  type        = "String"
  value       = var.clerk_issuer
  description = "Clerk issuer URL for JWT validation."

  tags = {
    Name = "${local.ssm_path_prefix}/CLERK_ISSUER"
  }
}
