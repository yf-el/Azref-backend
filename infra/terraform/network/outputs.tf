output "vpc_id" {
  value = aws_vpc.main.id
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "compute_sg_id" {
  value       = aws_security_group.compute.id
  description = "Attach this to the EC2 instance."
}

output "rds_sg_id" {
  value       = aws_security_group.rds.id
  description = "Attach this to the RDS instance."
}

output "redis_sg_id" {
  value       = aws_security_group.redis.id
  description = "Attach this to the ElastiCache Redis cluster."
}
