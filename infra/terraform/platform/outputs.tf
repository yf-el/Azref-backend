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
