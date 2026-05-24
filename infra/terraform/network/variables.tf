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

variable "vpc_cidr" {
  type        = string
  description = "CIDR block of the VPC."
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for public subnets, one per AZ in azs."
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for private subnets, one per AZ in azs."
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "azs" {
  type        = list(string)
  description = "Availability zones used by the public and private subnets."
  default     = ["eu-west-1a", "eu-west-1b"]
}
