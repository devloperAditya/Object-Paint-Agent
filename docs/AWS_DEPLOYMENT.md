# AWS Deployment

- **Deploy only on EC2 (one document, no jumping around):** **[DEPLOY_TO_EC2_STEP_BY_STEP.md](./DEPLOY_TO_EC2_STEP_BY_STEP.md)** — single step-by-step guide from AWS login to app in browser.
- **All options (EC2, App Runner, ECS) and reference:** **[AWS_DEPLOYMENT_STEPS.md](./AWS_DEPLOYMENT_STEPS.md)**.

The app is containerized (CPU-only). It listens on `PORT` (default **7860**) and exposes **GET /health** for load balancers and health checks.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 7860 | Server port |
| `MAX_IMAGE_PIXELS` | 1024 | Max dimension for uploaded images |
| `DATA_DIR` | ./data | Directory for exported outputs |
| `MODEL_CACHE_DIR` | ./models | Optional model weights directory |
| `LITE_MODE` | (unset) | Set to `true` to avoid loading heavy models |

## Option 1: AWS App Runner (containerized Gradio)

1. **Build and push image to ECR**
   - Create ECR repo: `aws ecr create-repository --repository-name object-paint-agent`
   - Build: `docker build -t object-paint-agent .`
   - Tag and push (see ECR publish section below).

2. **Create App Runner service**
   - Source: Amazon ECR (your image).
   - CPU: 1 vCPU, Memory: 2 GB (small).
   - Port: **7860**.
   - Environment: set `PORT=7860`, optionally `MAX_IMAGE_PIXELS=1024`, `DATA_DIR=/tmp/data` (ephemeral).
   - IAM: use default or a role with ECR pull and (if needed) Secrets Manager.

3. **Health check**
   - Protocol: HTTP.
   - Path: `/health`.
   - Interval: 30 s; healthy threshold 1; unhealthy 5.

4. **Storage**
   - App Runner is stateless. Exports go to container filesystem or `DATA_DIR`; for persistence, mount EFS or use S3 (requires code change to upload to S3).

## Option 2: ECS Fargate (ALB)

1. **ECR**
   - Build and push image (see below).

2. **ECS task definition**
   - Container: your image, CPU: 512–1024, Memory: 1–2 GB.
   - Port mapping: **7860**.
   - Environment: `PORT=7860`, `MAX_IMAGE_PIXELS`, `DATA_DIR` as needed.
   - Logging: use awslogs driver.

3. **ALB**
   - Target group: port 7860, protocol HTTP.
   - Health check: path `/health`, interval 30 s.

4. **IAM**
   - Task execution role: ECR pull, CloudWatch Logs.
   - Task role: add policies only if app needs S3/Secrets Manager.

5. **Security groups**
   - ALB: 80/443 from internet.
   - Fargate: allow 7860 from ALB only.

## Option 3: EC2 (Docker Compose)

1. **EC2**
   - Instance: t3.small or t3.medium (2 vCPU, 4 GB) for CPU-only; sufficient for GrabCut and optional small SAM.
   - AMI: Amazon Linux 2 or Ubuntu.

2. **Install Docker and Docker Compose**
   - Then clone repo and run:
   ```bash
   docker compose up -d
   ```

3. **Port and health**
   - Open security group for 7860 (or put behind ALB).
   - Health: `curl http://localhost:7860/health`.

4. **Persistence**
   - Use docker-compose volumes (as in repo) for `data/` and `models/` on the host, or bind-mount to EBS.

## Recommended instance sizing (CPU-only)

| Use case | Instance | Notes |
|----------|----------|--------|
| Lite (GrabCut only) | 1 vCPU, 1–2 GB RAM | t3.micro / t3.small |
| With small SAM | 2 vCPU, 4 GB RAM | t3.small / t3.medium |
| Optional GroundingDINO | 2–4 vCPU, 4–8 GB RAM | t3.medium |

Model constraints: GrabCut is fast and light. SAM and GroundingDINO increase memory and CPU; keep image size limited (e.g. 1024 px) for stability.

## ECR publish

```bash
AWS_REGION=us-east-1
ECR_URI=123456789012.dkr.ecr.us-east-1.amazonaws.com/object-paint-agent

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI
docker build -t object-paint-agent .
docker tag object-paint-agent:latest $ECR_URI:latest
docker push $ECR_URI:latest
```

Use `$ECR_URI:latest` as the image in App Runner, ECS, or EC2.
