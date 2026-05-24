output "instance_id" {
  value       = aws_instance.main.id
  description = "EC2 instance ID — used by GHA SSM Run Command to target this instance."
}

output "public_ip" {
  value       = aws_eip.main.public_ip
  description = "Stable public IP. Test with: curl http://<this>/health"
}

output "public_dns" {
  value = aws_instance.main.public_dns
}

output "iam_role_arn" {
  value = aws_iam_role.instance.arn
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.app.name
}
