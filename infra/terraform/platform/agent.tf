locals {
  agent_ssm_path_prefix = "/${var.project_name}/${var.env}/agent"
}

# --- ECR repository ------------------------------------------------------

resource "aws_ecr_repository" "agent" {
  name                 = "${local.name_prefix}/agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${local.name_prefix}/agent"
  }
}

resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name

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
# Agent reads its config from these params at container start (deploy.sh
# fetches them via aws ssm get-parameters-by-path).

resource "aws_ssm_parameter" "agent_database_url" {
  name        = "${local.agent_ssm_path_prefix}/DATABASE_URL"
  type        = "SecureString"
  value       = var.agent_database_url
  description = "PostgreSQL DSN for the external read-only legal docs DB the agent queries."

  tags = {
    Name = "${local.agent_ssm_path_prefix}/DATABASE_URL"
  }
}

resource "aws_ssm_parameter" "agent_groq_api_key" {
  name        = "${local.agent_ssm_path_prefix}/GROQ_API_KEY"
  type        = "SecureString"
  value       = var.agent_groq_api_key
  description = "Groq API key (primary LLM provider in the cascade)."

  tags = {
    Name = "${local.agent_ssm_path_prefix}/GROQ_API_KEY"
  }
}

resource "aws_ssm_parameter" "agent_cerebras_api_key" {
  name        = "${local.agent_ssm_path_prefix}/CEREBRAS_API_KEY"
  type        = "SecureString"
  value       = var.agent_cerebras_api_key
  description = "Cerebras API key (second LLM provider in the cascade)."

  tags = {
    Name = "${local.agent_ssm_path_prefix}/CEREBRAS_API_KEY"
  }
}

resource "aws_ssm_parameter" "agent_mistral_api_key" {
  name        = "${local.agent_ssm_path_prefix}/MISTRAL_API_KEY"
  type        = "SecureString"
  value       = var.agent_mistral_api_key
  description = "Mistral API key (third LLM provider in the cascade)."

  tags = {
    Name = "${local.agent_ssm_path_prefix}/MISTRAL_API_KEY"
  }
}

resource "aws_ssm_parameter" "agent_clerk_issuer" {
  name        = "${local.agent_ssm_path_prefix}/CLERK_ISSUER"
  type        = "String"
  value       = var.clerk_issuer
  description = "Clerk issuer URL for JWT validation on /api/v1/chat."

  tags = {
    Name = "${local.agent_ssm_path_prefix}/CLERK_ISSUER"
  }
}

resource "aws_ssm_parameter" "agent_stage" {
  name        = "${local.agent_ssm_path_prefix}/STAGE"
  type        = "String"
  value       = var.env == "prod" ? "production" : var.env
  description = "Runtime stage (controls docs exposure and CORS allowlist)."

  tags = {
    Name = "${local.agent_ssm_path_prefix}/STAGE"
  }
}
