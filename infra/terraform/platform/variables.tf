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
