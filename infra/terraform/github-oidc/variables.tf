variable "project_name" {
  type        = string
  description = "Short project slug used to prefix resource names."
}

variable "aws_region" {
  type        = string
  description = "AWS region — needed to scope SSM SendCommand resource ARNs."
}

variable "github_repo" {
  type        = string
  description = "GitHub repository in 'owner/repo' format (e.g. 'hitach12/mono-repo-microservices')."
}

variable "github_branch" {
  type        = string
  description = "Branch allowed to assume the deploy role. Use '*' to allow all branches (less secure)."
  default     = "main"
}
