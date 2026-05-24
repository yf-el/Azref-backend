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
  description = "EC2 instance type. t3.micro is free tier eligible for the first 750h/month on a single instance — this is the second instance so it falls outside free tier."
  default     = "t3.micro"
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch Logs retention."
  default     = 7
}

variable "hostname" {
  type        = string
  description = "Public hostname for the agent service, used by Caddy to obtain a Let's Encrypt cert. Must have a DNS A record pointing to the EIP BEFORE applying."
}
