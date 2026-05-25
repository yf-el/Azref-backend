output "rds_endpoint" {
  value       = aws_db_instance.backend.endpoint
  description = "RDS host:port (private, only reachable from compute SG)."
}

output "rds_instance_id" {
  value = aws_db_instance.backend.id
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.users_service.repository_url
  description = "Full ECR URL for docker push / pull."
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.users_service.arn
}

output "ssm_path_prefix" {
  value       = local.ssm_path_prefix
  description = "Path under which all users-service params live in SSM."
}

output "ssm_database_url_arn" {
  value = aws_ssm_parameter.database_url.arn
}

output "ssm_clerk_issuer_arn" {
  value = aws_ssm_parameter.clerk_issuer.arn
}

# --- Agent service outputs ----------------------------------------------

output "agent_ecr_repository_url" {
  value       = aws_ecr_repository.agent.repository_url
  description = "Full ECR URL for the agent service (docker push / pull)."
}

output "agent_ecr_repository_arn" {
  value = aws_ecr_repository.agent.arn
}

output "agent_ssm_path_prefix" {
  value       = local.agent_ssm_path_prefix
  description = "Path under which all agent params live in SSM."
}

# --- Redis outputs ------------------------------------------------------

output "redis_endpoint" {
  value       = "${aws_elasticache_cluster.main.cache_nodes[0].address}:${aws_elasticache_cluster.main.cache_nodes[0].port}"
  description = "ElastiCache Redis host:port (private, only reachable from compute SG)."
}

output "ssm_users_service_redis_url_arn" {
  value = aws_ssm_parameter.users_service_redis_url.arn
}

output "ssm_agent_redis_url_arn" {
  value = aws_ssm_parameter.agent_redis_url.arn
}

# --- Kafka (shared) -----------------------------------------------------

output "shared_ssm_path_prefix" {
  value       = local.shared_ssm_path_prefix
  description = "Path under which cross-service shared params (Kafka, ...) live in SSM."
}

output "ssm_kafka_bootstrap_servers_arn" {
  value = aws_ssm_parameter.kafka_bootstrap_servers.arn
}

output "ssm_kafka_api_key_arn" {
  value = aws_ssm_parameter.kafka_api_key.arn
}

output "ssm_kafka_api_secret_arn" {
  value = aws_ssm_parameter.kafka_api_secret.arn
}
