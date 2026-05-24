output "gha_deploy_role_arn" {
  value       = aws_iam_role.gha_deploy.arn
  description = "Paste this in the GitHub Actions workflow under 'role-to-assume'."
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}
