#!/bin/bash
set -ex
exec > >(tee /var/log/userdata.log) 2>&1

# --- Packages ------------------------------------------------------------
dnf update -y
dnf install -y docker jq

systemctl enable --now docker
usermod -aG docker ec2-user

# --- Bake deploy script for SSM Run Command to invoke later --------------
mkdir -p /opt/azref
cat > /opt/azref/deploy.sh <<'DEPLOY_EOF'
#!/bin/bash
set -e

REGION="${aws_region}"
ECR_URL="${ecr_url}"
SSM_PREFIX="${ssm_prefix}"
LOG_GROUP="${log_group}"
IMAGE_TAG="$${1:-latest}"

REGISTRY=$${ECR_URL%/*}

aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin "$REGISTRY"

docker pull $ECR_URL:$IMAGE_TAG

# Fetch every SSM param under $SSM_PREFIX and turn it into a docker -e arg
declare -a ENV_ARGS=()
while IFS=$'\t' read -r fullname value; do
  key=$${fullname##*/}
  ENV_ARGS+=("-e" "$${key}=$${value}")
done < <(
  aws ssm get-parameters-by-path \
    --path "$SSM_PREFIX" \
    --with-decryption \
    --region "$REGION" \
    --query 'Parameters[].[Name,Value]' \
    --output text
)

docker stop users-service 2>/dev/null || true
docker rm users-service 2>/dev/null || true

docker run -d --name users-service --restart unless-stopped \
  -p 80:8000 \
  --log-driver awslogs \
  --log-opt awslogs-region=$REGION \
  --log-opt awslogs-group=$LOG_GROUP \
  --log-opt awslogs-stream=app \
  "$${ENV_ARGS[@]}" \
  $ECR_URL:$IMAGE_TAG

echo "Deployed $ECR_URL:$IMAGE_TAG"
DEPLOY_EOF
chmod +x /opt/azref/deploy.sh

# Don't deploy at first boot — image may not exist yet.
# GitHub Actions will trigger /opt/azref/deploy.sh via SSM Run Command.
echo "User-data complete. Run /opt/azref/deploy.sh <tag> via SSM to deploy."
