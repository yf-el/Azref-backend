output "state_bucket" {
  value       = aws_s3_bucket.tfstate.id
  description = "Put this in each stack's backend.tf under 'bucket ='"
}

output "state_lock_table" {
  value       = aws_dynamodb_table.tfstate_lock.name
  description = "Put this in each stack's backend.tf under 'dynamodb_table ='"
}

output "aws_region" {
  value       = var.aws_region
  description = "Put this in each stack's backend.tf under 'region ='"
}
