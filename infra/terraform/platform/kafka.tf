locals {
  shared_ssm_path_prefix = "/${var.project_name}/${var.env}/shared"
}

# --- SSM Parameter Store: Kafka (shared) --------------------------------
# Confluent Cloud creds. Stored once here and consumed by every service that
# needs to produce/consume events. Consuming services grant themselves read
# access on the whole shared/ prefix (see services/agent/main.tf for the
# pattern) — anything added under shared/ later is auto-injected as env var.

resource "aws_ssm_parameter" "kafka_bootstrap_servers" {
  name        = "${local.shared_ssm_path_prefix}/KAFKA_BOOTSTRAP_SERVERS"
  type        = "String"
  value       = var.kafka_bootstrap_servers
  description = "Confluent Cloud bootstrap servers (host:port) for SASL_SSL connections."

  tags = {
    Name = "${local.shared_ssm_path_prefix}/KAFKA_BOOTSTRAP_SERVERS"
  }
}

resource "aws_ssm_parameter" "kafka_api_key" {
  name        = "${local.shared_ssm_path_prefix}/KAFKA_API_KEY"
  type        = "SecureString"
  value       = var.kafka_api_key
  description = "Confluent Cloud API Key (SASL username)."

  tags = {
    Name = "${local.shared_ssm_path_prefix}/KAFKA_API_KEY"
  }
}

resource "aws_ssm_parameter" "kafka_api_secret" {
  name        = "${local.shared_ssm_path_prefix}/KAFKA_API_SECRET"
  type        = "SecureString"
  value       = var.kafka_api_secret
  description = "Confluent Cloud API Secret (SASL password)."

  tags = {
    Name = "${local.shared_ssm_path_prefix}/KAFKA_API_SECRET"
  }
}
