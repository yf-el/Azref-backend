# --- ElastiCache Redis (shared cache for all services) ------------------
# Single t3.micro node, single AZ, no TLS — intra-VPC only, free tier eligible.

resource "aws_elasticache_subnet_group" "main" {
  name        = "${local.name_prefix}-redis"
  subnet_ids  = data.terraform_remote_state.network.outputs.private_subnet_ids
  description = "Private subnets for platform ElastiCache clusters."

  tags = {
    Name = "${local.name_prefix}-redis-subnet-group"
  }
}

resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${local.name_prefix}-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [data.terraform_remote_state.network.outputs.redis_sg_id]

  apply_immediately = true

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}

locals {
  redis_url = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:${aws_elasticache_cluster.main.cache_nodes[0].port}/0"
}

# --- SSM Parameter Store -------------------------------------------------
# Same REDIS_URL exposed under both service prefixes so each service's
# deploy.sh can fetch it via get-parameters-by-path on its own namespace.

resource "aws_ssm_parameter" "users_service_redis_url" {
  name        = "${local.ssm_path_prefix}/REDIS_URL"
  type        = "String"
  value       = local.redis_url
  description = "Shared ElastiCache Redis URL (intra-VPC, no auth)."

  tags = {
    Name = "${local.ssm_path_prefix}/REDIS_URL"
  }
}

resource "aws_ssm_parameter" "agent_redis_url" {
  name        = "${local.agent_ssm_path_prefix}/REDIS_URL"
  type        = "String"
  value       = local.redis_url
  description = "Shared ElastiCache Redis URL (intra-VPC, no auth)."

  tags = {
    Name = "${local.agent_ssm_path_prefix}/REDIS_URL"
  }
}
