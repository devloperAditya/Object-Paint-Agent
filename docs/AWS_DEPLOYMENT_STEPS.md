# Detailed Steps: Deploy Object Paint Agent to AWS

This guide walks you through deploying the Object Paint Agent (Gradio + FastAPI, CPU-only) to AWS. The app listens on **port 7860** and exposes **GET /health** for load balancers.

---

## Prerequisites

- **AWS account** with console or CLI access.
- **Docker** installed locally (to build and push the image).
- **AWS CLI** v2 installed and configured (`aws configure` with access key and region).
- **Git** (optional; for cloning the repo on EC2 if you use Option 3).

---

## Part 1: Build and Test the Docker Image Locally

Do this from your project root (e.g. `c:\Projects\HobbyProjects\Object Paint Agent`).

### 1.1 Build the image

```powershell
docker build -t object-paint-agent .
```

### 1.2 Run and test

```powershell
docker run -p 7860:7860 -e PORT=7860 -e MAX_IMAGE_PIXELS=1024 -e LITE_MODE=true object-paint-agent
```

- Open **http://localhost:7860** and use the UI.
- In another terminal: `curl http://localhost:7860/health` → should return `{"status":"ok",...}`.

### 1.3 Stop the container

```powershell
docker stop <container_id>
```

Once this works, use the same image for AWS (build once, tag for ECR, push).

---

## Part 2: Push Image to Amazon ECR

### 2.1 Set variables (PowerShell)

```powershell
$AWS_REGION = "us-east-1"   # or your preferred region
$AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$ECR_REPO_NAME = "object-paint-agent"
$ECR_URI = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
```

### 2.2 Create ECR repository

```powershell
aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION
```

(If it already exists, you can ignore "ResourceInUseException".)

### 2.3 Log in Docker to ECR

```powershell
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI
```

### 2.4 Tag and push

```powershell
docker tag object-paint-agent:latest "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
```

Use the image URI **`<account>.dkr.ecr.<region>.amazonaws.com/object-paint-agent:latest`** in App Runner, ECS, or EC2.

---

## Option A: Deploy with AWS App Runner (Recommended)

App Runner runs your container, handles scaling, and gives you a URL. No load balancer or ECS setup required.

### A.1 Create the App Runner service (Console)

1. In **AWS Console** → **App Runner** → **Create service**.
2. **Source**:
   - Repository type: **Amazon ECR**.
   - Connect to ECR (same account): select your **object-paint-agent** repository.
   - Image tag: **latest**.
   - ECR access: use **default** (or an IAM role that can pull from ECR).
3. **Configure service**:
   - Service name: e.g. `object-paint-agent`.
   - CPU: **1 vCPU**. Memory: **2 GB**.
   - Port: **7860**.
4. **Environment variables** (optional but recommended):

   | Key               | Value        |
   |-------------------|--------------|
   | `PORT`            | `7860`       |
   | `MAX_IMAGE_PIXELS` | `1024`     |
   | `DATA_DIR`        | `/tmp/data`  |
   | `LITE_MODE`       | `true`       |

5. **Health check**:
   - Protocol: **HTTP**.
   - Path: **/health**.
   - Interval: **30** seconds.
   - Timeout: **10** seconds.
   - Healthy threshold: **1**. Unhealthy: **5**.
6. Create the service. When it’s running, note the **Default domain** (e.g. `xxx.us-east-1.awsapprunner.com`).

### A.2 Create the App Runner service (CLI)

```powershell
# After pushing to ECR, get your ECR image URI
$IMAGE_URI = "${ECR_URI}:latest"

# Create App Runner service (requires an IAM role for ECR access; use default or create one)
aws apprunner create-service `
  --service-name object-paint-agent `
  --source-configuration "ImageRepository={ImageIdentifier=$IMAGE_URI,ImageRepositoryType=ECR},AutoDeploymentsEnabled=false" `
  --instance-configuration "Cpu=1024,Memory=2048" `
  --health-check-configuration "Protocol=HTTP,Path=/health,Interval=30,Timeout=10,HealthyThreshold=1,UnhealthyThreshold=5" `
  --network-configuration "EgressConfiguration={EgressType=DEFAULT}" `
  --region $AWS_REGION
```

Add environment variables via **`--instance-configuration`** or update the service after creation with:

```powershell
aws apprunner update-service --service-arn <service-arn> ...
```

### A.3 Access the app

- Open the **Default domain** URL in a browser (e.g. `https://xxx.us-east-1.awsapprunner.com`).
- Exports are stored in the container filesystem (`DATA_DIR`). For persistence, you’d need to add S3 (or similar) in the app and redeploy.

---

## Option B: Deploy with ECS Fargate + ALB

Use this if you need a custom domain, WAF, or more control over networking.

### B.1 Create ECR (already done in Part 2)

Use the same image URI from Part 2.

### B.2 Create ECS cluster

```powershell
aws ecs create-cluster --cluster-name object-paint-cluster --region $AWS_REGION
```

### B.3 Create task execution role (for ECR pull and logs)

1. IAM → **Roles** → **Create role** → **AWS service** → **Elastic Container Service** → **Elastic Container Service Task**.
2. Attach policies: **AmazonECSTaskExecutionRolePolicy** (ECR pull + CloudWatch Logs).
3. Name: e.g. `object-paint-task-execution-role`. Create role.

### B.4 Create task definition

Save as `task-definition.json` (replace `<account>.dkr.ecr.<region>.amazonaws.com` with your ECR URI and `<execution-role-arn>` with the role ARN):

```json
{
  "family": "object-paint-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "<execution-role-arn>",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "<account>.dkr.ecr.<region>.amazonaws.com/object-paint-agent:latest",
      "portMappings": [{ "containerPort": 7860, "protocol": "tcp" }],
      "environment": [
        { "name": "PORT", "value": "7860" },
        { "name": "MAX_IMAGE_PIXELS", "value": "1024" },
        { "name": "DATA_DIR", "value": "/tmp/data" },
        { "name": "LITE_MODE", "value": "true" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/object-paint-agent",
          "awslogs-region": "us-east-1"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:7860/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

Create log group and register task definition:

```powershell
aws logs create-log-group --log-group-name /ecs/object-paint-agent --region $AWS_REGION
aws ecs register-task-definition --cli-input-json file://task-definition.json --region $AWS_REGION
```

### B.5 Create Application Load Balancer (ALB)

1. EC2 → **Load Balancers** → **Create** → **Application Load Balancer**.
2. Name: e.g. `object-paint-alb`. Scheme: **Internet-facing**. VPC and subnets: your default or chosen VPC (public subnets).
3. Security group: allow **80** and **443** from `0.0.0.0/0` (or restrict later).
4. Target group: create new, name `object-paint-tg`, target type **IP**, protocol **HTTP**, port **7860**. VPC same as ALB.
5. Health check: path **/health**, interval **30**, healthy threshold **1**, unhealthy **5**.
6. Register targets: you’ll attach the target group to the ECS service (no manual registration).

### B.6 Create ECS service

- **Cluster**: `object-paint-cluster`.
- **Task definition**: `object-paint-agent` (latest revision).
- **Service type**: Replica, desired count **1**.
- **Networking**: same VPC; subnets (private if using NAT, or public with auto-assign IP); security group that allows **7860** from the ALB security group only.
- **Load balancing**: **Application Load Balancer**; select `object-paint-alb` and `object-paint-tg`; container **app:7860**.
- Create service.

### B.7 Access the app

- Use the ALB DNS name (e.g. `object-paint-alb-xxx.us-east-1.elb.amazonaws.com`) in the browser.
- Optional: add HTTPS and a custom domain with ACM certificate and an ALB listener on 443.

---

## Option C: Deploy on EC2 with Docker Compose

Good for a single instance, full control, and simple persistence with host volumes.

### C.1 Launch EC2 instance

1. EC2 → **Launch instance**.
2. Name: `object-paint-agent`. AMI: **Amazon Linux 2** or **Ubuntu 22.04**.
3. Instance type: **t3.small** (2 vCPU, 4 GB) for GrabCut + optional SAM; **t3.micro** for lite only.
4. Key pair: create or select one for SSH.
5. Security group: allow **SSH (22)** from your IP and **7860** from `0.0.0.0/0` (or restrict to ALB later).
6. Storage: 20–30 GB. Launch.

### C.2 Connect and install Docker

**Amazon Linux 2:**

```bash
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker && sudo systemctl enable docker
sudo usermod -aG docker ec2-user
# Log out and back in, then:
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

**Ubuntu:**

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl start docker && sudo systemctl enable docker
sudo usermod -aG docker ubuntu
# Log out and back in
```

### C.3 Deploy the app

Clone the repo (or copy files) and run Compose:

```bash
git clone <your-repo-url> object-paint-agent && cd object-paint-agent
# Or upload Dockerfile + docker-compose.yml + app/ + pyproject.toml + scripts/
docker compose up -d
```

Check:

```bash
curl http://localhost:7860/health
```

### C.4 Persistence and ports

- Data and models are in Docker volumes (`object_paint_data`, `object_paint_models`). To keep them on the host, use bind mounts in `docker-compose.yml` (e.g. `./data:/app/data`, `./models:/app/models`).
- Open **http://<EC2-public-IP>:7860** in a browser. For production, put an ALB in front and restrict 7860 to the ALB security group.

---

## Environment Variables Reference

| Variable           | Default   | Description                                      |
|--------------------|-----------|--------------------------------------------------|
| `PORT`             | 7860      | Server port                                      |
| `MAX_IMAGE_PIXELS` | 1024      | Max dimension for uploaded images                 |
| `DATA_DIR`         | ./data    | Directory for exported outputs                    |
| `MODEL_CACHE_DIR`  | ./models  | Optional model weights directory                  |
| `LITE_MODE`        | (unset)   | Set to `true` to avoid loading heavy models      |

---

## Instance Sizing (CPU-only)

| Use case              | Instance   | CPU / Memory   |
|-----------------------|------------|----------------|
| Lite (GrabCut only)   | t3.micro   | 1 vCPU, 1 GB   |
| Lite (recommended)    | t3.small   | 2 vCPU, 2 GB   |
| With small SAM        | t3.small / t3.medium | 2 vCPU 4 GB |
| Optional GroundingDINO| t3.medium  | 2–4 vCPU, 4–8 GB |

---

## Grounding DINO object detection on AWS

**With the default Docker image and deployment, Grounding DINO object detection does not work.** The default image is “lite”: it only includes GrabCut (and optional SAM if you add weights). It does **not** include PyTorch or the GroundingDINO package, so the “Use Grounding DINO” option in the UI will report that the detector is unavailable.

To have **Grounding DINO object detection** in your AWS deployment you must:

1. Use an image that includes **PyTorch**, the **GroundingDINO** package, and the **checkpoint** `groundingdino_swint_ogc.pth` in `models/groundingdino/`.
2. Use a larger instance (e.g. **t3.medium**: 2 vCPU, 4 GB RAM; or more if you hit OOM).
3. Set **`MODEL_CACHE_DIR`** to the path where the container sees the weights (e.g. `/app/models` if you bake them in, or a mounted path).

### Option 1: Use the Grounding DINO Dockerfile (recommended)

The repo includes **`Dockerfile.groundingdino`**, which installs the base app plus the `[detect]` extra (PyTorch) and the GroundingDINO package from source. You still need to provide the checkpoint.

**Build with weights baked in (larger image):**

1. Download the checkpoint once (see [GroundingDINO](https://github.com/IDEA-Research/GroundingDINO)):
   - Get **groundingdino_swint_ogc.pth** and put it in `models/groundingdino/` in the project root.
2. Build and run:
   ```bash
   docker build -f Dockerfile.groundingdino -t object-paint-agent:with-gd .
   docker run -p 7860:7860 -e PORT=7860 -e MODEL_CACHE_DIR=/app/models object-paint-agent:with-gd
   ```
3. Push the same image to ECR and use it in App Runner / ECS / EC2. In the UI, enable **“Use Grounding DINO”** and click **Detect objects**.

**Build without weights (smaller image); mount weights at runtime:**

1. Build: `docker build -f Dockerfile.groundingdino -t object-paint-agent:with-gd .`
2. On EC2 (or ECS with a volume): create `./models/groundingdino/`, put `groundingdino_swint_ogc.pth` there, and run with a bind mount:
   ```bash
   docker run -p 7860:7860 -e PORT=7860 -e MODEL_CACHE_DIR=/app/models -v $(pwd)/models:/app/models object-paint-agent:with-gd
   ```
3. On ECS/Fargate you can copy weights from S3 in an entrypoint script, or use EFS and set `MODEL_CACHE_DIR` to the mount path.

### Option 2: Add Grounding DINO to the default Dockerfile yourself

In your own fork or Dockerfile:

1. Install optional deps and GroundingDINO after the base install:
   - `pip install torch torchvision`
   - Clone [GroundingDINO](https://github.com/IDEA-Research/GroundingDINO), then `pip install -e /path/to/GroundingDINO --no-build-isolation`
2. Ensure the app’s config is present: `app/ml/groundingdino_config/GroundingDINO_SwinT_OGC.py` (already in the repo).
3. Place **groundingdino_swint_ogc.pth** in `models/groundingdino/` (or set `MODEL_CACHE_DIR` and mount that path).

### Checklist for Grounding DINO on AWS

- [ ] Image includes PyTorch and GroundingDINO (e.g. build from `Dockerfile.groundingdino`).
- [ ] Checkpoint at `models/groundingdino/groundingdino_swint_ogc.pth` (in image or mounted; `MODEL_CACHE_DIR` set if needed).
- [ ] Instance size at least t3.medium (2 vCPU, 4 GB RAM).
- [ ] In the UI: enable **“Use Grounding DINO”** and click **Detect objects**.

---

## Troubleshooting

- **Health check failing**: Ensure path is exactly **/health** and port is **7860**. Allow 10–60 s for the app to start.
- **502/503**: Increase task/instance memory or startup time (health check start period).
- **Out of memory**: Set `MAX_IMAGE_PIXELS=768` or `512` and/or use `LITE_MODE=true`.
- **Exports not persisting (App Runner / Fargate)**: Container filesystem is ephemeral. Add S3 upload in the app and set `DATA_DIR` or use an S3 path if you implement it.
- **GroundingDINO build fails in Docker**: If `Dockerfile.groundingdino` fails during `pip install -e /tmp/GroundingDINO`, add `build-essential` to the `apt-get install` line and retry. For CPU-only, the GroundingDINO setup skips CUDA extensions.

---

## Summary Checklist

- [ ] Build and test Docker image locally.
- [ ] Create ECR repo and push image.
- [ ] Choose deployment: **App Runner** (easiest), **ECS Fargate + ALB**, or **EC2 + Docker Compose**.
- [ ] Set env vars: `PORT=7860`, `MAX_IMAGE_PIXELS=1024`, `LITE_MODE=true` (and optionally `DATA_DIR`).
- [ ] Configure health check: **GET /health**, port **7860**.
- [ ] Open the service URL and test the UI and **/health**.

For a minimal path: **Part 1 → Part 2 → Option A (App Runner)** gets a working public URL with the least setup.
