locals {
  name_prefix = "${var.project_name}-gha"
}

data "aws_caller_identity" "current" {}

# Read upstream stacks for ARNs we want to scope IAM permissions to
data "terraform_remote_state" "platform" {
  backend = "s3"
  config = {
    bucket = "azref-tfstate-230148048244"
    key    = "platform/terraform.tfstate"
    region = var.aws_region
  }
}

data "terraform_remote_state" "users_service" {
  backend = "s3"
  config = {
    bucket = "azref-tfstate-230148048244"
    key    = "services/users-service/terraform.tfstate"
    region = var.aws_region
  }
}

# --- OIDC provider (one per AWS account) --------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # GitHub's OIDC certs change periodically — AWS validates the cert chain
  # internally, but the field is still required. These are the well-known thumbprints.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

# --- IAM role assumable from the GitHub repo ----------------------------

data "aws_iam_policy_document" "assume_from_github" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    # The OIDC token's audience must match — locked to AWS STS.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Restrict which repo + branch can assume this role.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/${var.github_branch}"]
    }
  }
}

resource "aws_iam_role" "gha_deploy" {
  name               = "${local.name_prefix}-deploy"
  assume_role_policy = data.aws_iam_policy_document.assume_from_github.json

  tags = {
    Name = "${local.name_prefix}-deploy"
  }
}

# --- Permissions for the role -------------------------------------------

data "aws_iam_policy_document" "deploy" {
  # 1. Get a temporary ECR token (always resource:*)
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # 2. Push images to OUR ECR repo only
  statement {
    sid = "EcrPushPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [data.terraform_remote_state.platform.outputs.ecr_repository_arn]
  }

  # 3. SSM SendCommand to trigger redeploy on the users-service EC2
  statement {
    sid     = "SsmSendCommand"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/${data.terraform_remote_state.users_service.outputs.instance_id}",
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
    ]
  }

  # 4. Read back the result of the SendCommand
  statement {
    sid = "SsmReadResult"
    actions = [
      "ssm:GetCommandInvocation",
      "ssm:ListCommandInvocations",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "${local.name_prefix}-deploy"
  role   = aws_iam_role.gha_deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
