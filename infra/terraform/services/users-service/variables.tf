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

variable "instance_type" {
  type        = string
  description = "EC2 instance type. t3.micro is free tier eligible in eu-west-1 for accounts created after mid-2024."
  default     = "t3.micro"
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch Logs retention. Free tier covers ~5GB ingest/mo, no time cap."
  default     = 7
}
