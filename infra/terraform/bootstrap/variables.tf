variable "project_name" {
  type        = string
  description = "Short project slug, used as prefix for all resources."
}

variable "aws_region" {
  type        = string
  description = "AWS region where the state backend lives."
}
