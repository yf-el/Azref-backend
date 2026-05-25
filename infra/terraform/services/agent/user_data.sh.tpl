#!/bin/bash
set -ex
exec > >(tee /var/log/userdata.log) 2>&1

# --- Packages ------------------------------------------------------------
dnf update -y
dnf install -y docker jq

systemctl enable --now docker
usermod -aG docker ec2-user

# --- Caddyfile (TLS termination + reverse proxy) ------------------------
mkdir -p /opt/azref
cat > /opt/azref/Caddyfile <<CADDYFILE_EOF
${hostname} {
    reverse_proxy agent:8000
}
CADDYFILE_EOF

# --- Shared Docker network for Caddy <-> agent --------------------------
docker network inspect azref-net >/dev/null 2>&1 || docker network create azref-net

# --- Caddy container (idempotent, started once at boot, restarts on reboot)
docker rm -f caddy 2>/dev/null || true
docker run -d --name caddy --restart unless-stopped \
  --network azref-net \
  -p 80:80 -p 443:443 \
  -v /opt/azref/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v caddy_data:/data \
  -v caddy_config:/config \
  caddy:2

# --- Bake deploy script for SSM Run Command to invoke later --------------
cat > /opt/azref/deploy.sh <<'DEPLOY_EOF'
#!/bin/bash
set -e

REGION="${aws_region}"
ECR_URL="${ecr_url}"
SSM_PREFIX="${ssm_prefix}"
SHARED_SSM_PREFIX="${shared_ssm_prefix}"
LOG_GROUP="${log_group}"
IMAGE_TAG="$${1:-latest}"

REGISTRY=$${ECR_URL%/*}

# Ensure shared network exists (idempotent)
docker network inspect azref-net >/dev/null 2>&1 || docker network create azref-net

aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin "$REGISTRY"

docker pull $ECR_URL:$IMAGE_TAG

# Fetch agent-private params + every shared/* param and turn each into
# a docker -e arg. Shared params (Kafka creds today, more later) are
# readable by every service whose IAM grants ssm:Get* on shared_ssm_prefix.
declare -a ENV_ARGS=()
while IFS=$'\t' read -r fullname value; do
  key=$${fullname##*/}
  ENV_ARGS+=("-e" "$${key}=$${value}")
done < <(
  {
    aws ssm get-parameters-by-path \
      --path "$SSM_PREFIX" \
      --with-decryption \
      --region "$REGION" \
      --query 'Parameters[].[Name,Value]' \
      --output text
    aws ssm get-parameters-by-path \
      --path "$SHARED_SSM_PREFIX" \
      --with-decryption \
      --region "$REGION" \
      --query 'Parameters[].[Name,Value]' \
      --output text
  }
)

docker stop agent 2>/dev/null || true
docker rm agent 2>/dev/null || true

# agent runs on the shared network — NO host port mapping (Caddy fronts it)
docker run -d --name agent --restart unless-stopped \
  --network azref-net \
  --log-driver awslogs \
  --log-opt awslogs-region=$REGION \
  --log-opt awslogs-group=$LOG_GROUP \
  --log-opt awslogs-stream=app \
  "$${ENV_ARGS[@]}" \
  $ECR_URL:$IMAGE_TAG

# Make sure Caddy is up (it may have been stopped, or this is the first deploy)
if ! docker ps --format '{{.Names}}' | grep -q '^caddy$'; then
  docker start caddy 2>/dev/null || true
fi

echo "Deployed $ECR_URL:$IMAGE_TAG"
DEPLOY_EOF
chmod +x /opt/azref/deploy.sh

echo "User-data complete. Caddy is running; deploy will be triggered by GitHub Actions via SSM."
