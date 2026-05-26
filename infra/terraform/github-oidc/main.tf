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

  # 2. Push images to OUR ECR repos only
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
    resources = [
      data.terraform_remote_state.platform.outputs.ecr_repository_arn,
      data.terraform_remote_state.platform.outputs.agent_ecr_repository_arn,
    ]
  }

  # 3. SSM SendCommand on any EC2 tagged for our services (tag-based, decoupled from instance_id)
  statement {
    sid     = "SsmSendCommandDocument"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
    ]
  }

  statement {
    sid     = "SsmSendCommandInstance"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Name"
      values = [
        "azref-dev-users-service",
        "azref-dev-agent",
      ]
    }
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

  # ---------------------------------------------------------------------------
  # SAM / Lambda deploy path — used by services packaged as Lambda (e.g.
  # crm-sync-lambda). Each statement is scoped to the `azref-*` prefix so the
  # role can't touch resources outside the project. See `services/crm-sync-lambda/`.
  # ---------------------------------------------------------------------------

  # 5. CloudFormation — SAM is a CFN dialect, every deploy goes through CFN.
  statement {
    sid     = "CloudFormationDeploy"
    actions = ["cloudformation:*"]
    resources = [
      "arn:aws:cloudformation:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stack/azref-*/*",
      "arn:aws:cloudformation:${var.aws_region}:${data.aws_caller_identity.current.account_id}:changeSet/*",
    ]
  }

  # SAM CLI calls these globally (no resource arn possible) — read-only, safe.
  statement {
    sid = "CloudFormationListGlobal"
    actions = [
      "cloudformation:ListStacks",
      "cloudformation:DescribeStackResource",
      "cloudformation:ValidateTemplate",
    ]
    resources = ["*"]
  }

  # 6. Lambda — CRUD on functions prefixed `azref-`.
  statement {
    sid     = "LambdaDeploy"
    actions = ["lambda:*"]
    resources = [
      "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:azref-*",
    ]
  }

  # GetAccountSettings / ListFunctions have no per-resource ARN.
  statement {
    sid       = "LambdaListGlobal"
    actions   = ["lambda:GetAccountSettings", "lambda:ListFunctions"]
    resources = ["*"]
  }

  # 7. IAM — SAM creates the Lambda execution role + must PassRole it.
  # Scoped tight to `azref-*` role names so this role can't escalate to admin.
  statement {
    sid = "IamForLambdaExecutionRoles"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:PassRole",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:GetRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListRolePolicies",
      "iam:TagRole",
      "iam:UntagRole",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/azref-*",
    ]
  }

  # 8. S3 — SAM uploads the Lambda zip to its managed bucket before CFN
  # references it. `--resolve-s3` provisions the bucket on first deploy.
  statement {
    sid     = "SamArtifactsBucketIo"
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::aws-sam-cli-managed-default-*",
      "arn:aws:s3:::aws-sam-cli-managed-default-*/*",
    ]
  }

  # First-deploy bucket provisioning needs to act globally (CreateBucket
  # doesn't accept a resource constraint).
  statement {
    sid = "SamArtifactsBucketCreate"
    actions = [
      "s3:CreateBucket",
      "s3:PutBucketPolicy",
      "s3:PutBucketVersioning",
      "s3:PutBucketTagging",
      "s3:PutEncryptionConfiguration",
      "s3:ListAllMyBuckets",
    ]
    resources = ["*"]
  }

  # 9. CloudWatch Logs — SAM provisions the /aws/lambda/<fn> log group at
  # deploy time. Without this perm, deploy fails mid-way with a cryptic error.
  statement {
    sid = "LambdaLogGroups"
    actions = [
      "logs:CreateLogGroup",
      "logs:DescribeLogGroups",
      "logs:PutRetentionPolicy",
      "logs:TagResource",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/azref-*",
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/azref-*:*",
    ]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "${local.name_prefix}-deploy"
  role   = aws_iam_role.gha_deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
