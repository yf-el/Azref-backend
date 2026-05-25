locals {
  name_prefix = "${var.project_name}-${var.env}-users-service"
  log_group   = "/${var.project_name}/${var.env}/users-service"
}

# --- Read upstream stack outputs ----------------------------------------

data "terraform_remote_state" "network" {
  backend = "s3"
  config = {
    bucket = "azref-tfstate-230148048244"
    key    = "network/terraform.tfstate"
    region = var.aws_region
  }
}

data "terraform_remote_state" "platform" {
  backend = "s3"
  config = {
    bucket = "azref-tfstate-230148048244"
    key    = "platform/terraform.tfstate"
    region = var.aws_region
  }
}

data "aws_caller_identity" "current" {}

# Amazon Linux 2023 AMI (x86_64) — kept up-to-date by AWS.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# --- CloudWatch log group -----------------------------------------------

resource "aws_cloudwatch_log_group" "app" {
  name              = local.log_group
  retention_in_days = var.log_retention_days

  tags = {
    Name = local.log_group
  }
}

# --- IAM role for the EC2 -----------------------------------------------

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = local.name_prefix
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json

  tags = {
    Name = local.name_prefix
  }
}

# SSM Session Manager + Run Command (no SSH key needed).
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Read SSM params under our service prefix, plus the shared Kafka creds.
# Shared path is scoped narrowly to KAFKA_* — users-service must not see
# other cross-service params it doesn't need.
data "aws_iam_policy_document" "ssm_read" {
  statement {
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      # GetParametersByPath needs permission on the parent path itself
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${data.terraform_remote_state.platform.outputs.ssm_path_prefix}",
      # GetParameter / GetParameters need permission on individual params under that path
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${data.terraform_remote_state.platform.outputs.ssm_path_prefix}/*",
    ]
  }

  statement {
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${data.terraform_remote_state.platform.outputs.shared_ssm_path_prefix}",
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${data.terraform_remote_state.platform.outputs.shared_ssm_path_prefix}/*",
    ]
  }

  # SecureString params are encrypted with the AWS-managed key 'aws/ssm'.
  # The kms:ViaService condition was misbehaving for GetParametersByPath, so we drop it
  # and rely on the action+resource scope alone (kms:Decrypt is still bounded by KMS key policy).
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ssm_read" {
  name   = "${local.name_prefix}-ssm-read"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.ssm_read.json
}

# Pull from our ECR repo.
data "aws_iam_policy_document" "ecr_pull" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchCheckLayerAvailability",
    ]
    resources = [data.terraform_remote_state.platform.outputs.ecr_repository_arn]
  }
}

resource "aws_iam_role_policy" "ecr_pull" {
  name   = "${local.name_prefix}-ecr-pull"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.ecr_pull.json
}

# Write container logs to CloudWatch (awslogs driver).
data "aws_iam_policy_document" "logs_write" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["${aws_cloudwatch_log_group.app.arn}:*"]
  }
}

resource "aws_iam_role_policy" "logs_write" {
  name   = "${local.name_prefix}-logs-write"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.logs_write.json
}

resource "aws_iam_instance_profile" "instance" {
  name = local.name_prefix
  role = aws_iam_role.instance.name
}

# --- EC2 instance --------------------------------------------------------

resource "aws_instance" "main" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = data.terraform_remote_state.network.outputs.public_subnet_ids[0]
  vpc_security_group_ids = [data.terraform_remote_state.network.outputs.compute_sg_id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    aws_region        = var.aws_region
    ecr_url           = data.terraform_remote_state.platform.outputs.ecr_repository_url
    ssm_prefix        = data.terraform_remote_state.platform.outputs.ssm_path_prefix
    shared_ssm_prefix = data.terraform_remote_state.platform.outputs.shared_ssm_path_prefix
    log_group         = local.log_group
    hostname          = var.hostname
  })

  # Trigger replacement if user_data changes.
  user_data_replace_on_change = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    delete_on_termination = true
    encrypted             = true
  }

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2          # 2 for Docker containers using the metadata API
  }

  tags = {
    Name = local.name_prefix
  }
}

# Stable public IP (otherwise it changes on stop/start).
resource "aws_eip" "main" {
  instance = aws_instance.main.id
  domain   = "vpc"

  tags = {
    Name = local.name_prefix
  }
}
