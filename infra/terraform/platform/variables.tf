variable "project_name" {
  type        = string
  description = "Short project slug used to prefix resource names."
}

variable "env" {
  type        = string
  description = "Environment name (dev, staging, prod)."
}

variable "aws_region" {
  type        = string
  description = "AWS region for all resources."
}

variable "clerk_issuer" {
  type        = string
  description = "Clerk issuer URL. Find via Clerk dashboard or by decoding a JWT (iss claim)."
}

variable "db_name" {
  type        = string
  description = "Initial database name."
  default     = "azref"
}

variable "db_username" {
  type        = string
  description = "DB master username."
  default     = "azref"
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class. db.t3.micro is free tier eligible."
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  type        = number
  description = "Allocated storage in GB. 20 is the free tier max."
  default     = 20
}

variable "db_backup_retention_days" {
  type        = number
  description = "Days of automated backups kept. 0 disables. Free tier covers ~20GB of backup storage."
  default     = 1
}

variable "ecr_image_retention_count" {
  type        = number
  description = "How many images to keep in the ECR repository before expiring older ones."
  default     = 10
}

# --- Agent service secrets ----------------------------------------------
# These are pushed to SSM Parameter Store and read by the agent container at
# start. Provide values via a gitignored secrets.auto.tfvars or env vars
# (TF_VAR_agent_database_url, etc.). Never commit real values.

variable "agent_database_url" {
  type        = string
  description = "PostgreSQL DSN for the external legal docs DB the agent queries (read-only)."
  sensitive   = true
}

variable "agent_groq_api_key" {
  type        = string
  description = "Groq API key."
  sensitive   = true
  default     = ""
}

variable "agent_cerebras_api_key" {
  type        = string
  description = "Cerebras API key."
  sensitive   = true
  default     = ""
}

variable "agent_mistral_api_key" {
  type        = string
  description = "Mistral API key."
  sensitive   = true
  default     = ""
}

# --- Kafka (shared across services) -------------------------------------
# Confluent Cloud Basic cluster. Same credentials consumed by every service
# that produces or consumes events (agent, users-service, future workers).
# Stored once under /<project>/<env>/shared/KAFKA_* and exposed to each
# service via an IAM statement on the shared/ prefix (see services/*/main.tf).

variable "kafka_bootstrap_servers" {
  type        = string
  description = "Confluent Cloud bootstrap servers URL (host:port). Found in Cluster Settings."
}

variable "kafka_api_key" {
  type        = string
  description = "Confluent Cloud API Key for SASL_SSL auth."
  sensitive   = true
}

variable "kafka_api_secret" {
  type        = string
  description = "Confluent Cloud API Secret for SASL_SSL auth."
  sensitive   = true
}
