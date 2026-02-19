# Deploy Object Paint Agent to AWS EC2 — One Document, Step by Step

This guide takes you from zero to a working app on a single EC2 instance. Follow the steps in order. Everything you need is in this document.

---

## What you will have at the end

- An EC2 instance running Object Paint Agent in Docker.
- Access to the app in your browser at `http://<your-ec2-public-ip>:7860`.
- **Lite mode** (GrabCut only, no model downloads) by default. Optional **Grounding DINO** path is in Step 7.

---

## Step 1: Open AWS and go to EC2

1. Log in to the [AWS Console](https://console.aws.amazon.com/).
2. In the top search bar, type **EC2** and open **EC2** (Amazon Elastic Compute Cloud).
3. Make sure the **region** (top-right, e.g. **N. Virginia us-east-1**) is the one you want. All resources in this guide will be in that region.

---

## Step 2: Create a key pair (for SSH login)

1. In the left sidebar, under **Network & Security**, click **Key Pairs**.
2. Click **Create key pair**.
3. **Name:** `object-paint-agent-key` (or any name you like).
4. **Key pair type:** RSA.
5. **Private key format:**  
   - Choose **.pem** if you will use SSH from PowerShell or WSL.  
   - Choose **.ppk** if you will use PuTTY (you can convert .pem to .ppk in PuTTYgen).
6. Click **Create key pair**. A file will download. **Keep it safe and private**; you need it to connect to the instance.

---

## Step 3: Create a security group (firewall rules)

1. In the left sidebar, under **Network & Security**, click **Security Groups**.
2. Click **Create security group**.
3. **Name:** `object-paint-agent-sg`. **Description:** `Allow SSH and app port 7860`.
4. **VPC:** Leave **Default VPC** (or choose the VPC where you will launch the instance).
5. **Inbound rules:** Add these two rules (then leave outbound as default):

   | Type   | Protocol | Port range | Source        | Description      |
   |--------|----------|------------|---------------|------------------|
   | SSH    | TCP      | 22         | My IP         | For SSH login    |
   | Custom TCP | TCP  | 7860       | 0.0.0.0/0     | App (or use My IP to restrict) |

   - For **Source** of SSH: choose **My IP** so only your machine can SSH.
   - For **7860**: use **0.0.0.0/0** to allow anyone to open the app in a browser, or **My IP** to allow only you.

6. Click **Create security group**.

---

## Step 4: Launch the EC2 instance

1. In the left sidebar, click **Instances**.
2. Click **Launch instance**.
3. Set the following (change only what is listed):

   - **Name:** `object-paint-agent`.
   - **Application and OS Images (AMI):** **Ubuntu**, **Ubuntu Server 22.04 LTS**.
   - **Instance type:** **t3.small** (2 vCPU, 2 GB RAM). For GrabCut-only (lite) you can use **t3.micro**; for Grounding DINO use at least **t3.small**, better **t3.medium**.
   - **Key pair (login):** Select the key pair you created in Step 2 (e.g. `object-paint-agent-key`).
   - **Network settings:**  
     - **Security group:** Select **Select existing** and choose `object-paint-agent-sg` from Step 3.
   - **Storage:** 30 GB gp3 (or 20 GB minimum).

4. Click **Launch instance**. Wait until **Instance state** is **Running** (status check **2/2** can take 1–2 minutes).

5. Note the **Public IPv4 address** (e.g. `54.123.45.67`). You will use this to SSH and to open the app.

---

## Step 5: Connect to the instance (SSH)

Use one of the two methods below. Replace `YOUR_KEY_FILE` and `EC2_PUBLIC_IP` with your key path and the instance’s public IP.

**A — From Windows (PowerShell) using .pem**

```powershell
ssh -i "C:\path\to\object-paint-agent-key.pem" ubuntu@EC2_PUBLIC_IP
```

Example:

```powershell
ssh -i "C:\Users\YourName\Downloads\object-paint-agent-key.pem" ubuntu@54.123.45.67
```

If asked “Are you sure you want to continue connecting?”, type `yes` and press Enter.

**B — From Windows using PuTTY (if you use .ppk)**

1. Open PuTTY. **Host:** `ubuntu@EC2_PUBLIC_IP`.
2. Under **Connection → SSH → Auth**, in **Private key file for authentication**, choose your `.ppk` file.
3. Click **Open** and log in.

You should see a prompt like `ubuntu@ip-172-31-...:~$`. All following commands are run on this SSH session (on the EC2 instance) unless stated otherwise.

---

## Step 6: Install Docker and Docker Compose on the instance

Run these commands **one after the other** on the EC2 instance (copy-paste each block).

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
```

Then log out and log back in so the `docker` group applies (otherwise `docker` may say “permission denied”):

```bash
exit
```

Reconnect with the same SSH command as in Step 5, then verify:

```bash
docker --version
docker compose version
```

You should see version numbers for both.

---

## Step 7: Get the project code on the instance

**Option A — You have the project in a Git repo (GitHub, GitLab, etc.)**

Replace `YOUR_REPO_URL` with your repo URL (e.g. `https://github.com/youruser/object-paint-agent.git`).

```bash
cd ~
git clone YOUR_REPO_URL object-paint-agent
cd object-paint-agent
```

**Option B — You only have the project on your PC (no Git repo)**

1. On your **Windows PC**, zip the whole project folder (include `app/`, `scripts/`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, etc.).
2. From **PowerShell on your PC** (not on EC2), run (replace paths and IP):

```powershell
scp -i "C:\path\to\object-paint-agent-key.pem" C:\path\to\object-paint-agent.zip ubuntu@EC2_PUBLIC_IP:~/
```

3. On the **EC2 instance** (SSH session):

```bash
cd ~
sudo apt-get install -y unzip
unzip object-paint-agent.zip -d object-paint-agent
cd object-paint-agent
```

You should end with a directory `~/object-paint-agent` containing at least: `app/`, `scripts/`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`.

---

## Step 8: Run the app (choose one path)

You are in `~/object-paint-agent` on the EC2 instance. Choose **Path A** (lite) or **Path B** (with Grounding DINO).

---

### Path A: Lite mode (GrabCut only, no model downloads)

This works immediately; no extra downloads.

```bash
docker compose up -d --build
```

Wait 2–5 minutes for the first build. Then check that the container is running:

```bash
docker compose ps
```

You should see the `app` container with state **Up**. Check health:

```bash
curl -s http://localhost:7860/health
```

You should see something like `{"status":"ok",...}`.

**You are done for Path A.** Go to **Step 9**.

---

### Path B: With Grounding DINO object detection

Only do this if you want “Detect objects” with Grounding DINO. The instance should be at least **t3.small** (better **t3.medium**). Build will take 10–20 minutes.

**B.1 — Download the Grounding DINO checkpoint (on your PC or any machine)**

1. Get the file **groundingdino_swint_ogc.pth** from the [GroundingDINO releases](https://github.com/IDEA-Research/GroundingDINO/releases) or the link in their README.
2. Create on your PC a folder: `models/groundingdino/` and put the file inside it so you have:
   - `models/groundingdino/groundingdino_swint_ogc.pth`

**B.2 — Upload the weights to EC2**

From **PowerShell on your PC** (replace paths and IP):

```powershell
scp -i "C:\path\to\object-paint-agent-key.pem" -r "C:\path\to\models" ubuntu@EC2_PUBLIC_IP:~/object-paint-agent/
```

So on EC2 you have `~/object-paint-agent/models/groundingdino/groundingdino_swint_ogc.pth`.

**B.2.5 — Free disk space (avoid “no space left on device”)**

The build needs several GB free. On the EC2 instance run:

```bash
df -h .
docker system prune -af
df -h .
```

Ensure at least **15–20 GB free** for the build. If the root volume is too small, increase the EBS volume size in the AWS console (EC2 → Volumes → modify), then extend the partition on the instance (e.g. `sudo growpart /dev/nvme0n1 1` and `sudo resize2fs /dev/nvme0n1p1` on Ubuntu, or follow AWS docs for your AMI).

**B.3 — Build and run with Grounding DINO**

On the **EC2 instance** (you must be in `~/object-paint-agent` and have `models/groundingdino/groundingdino_swint_ogc.pth` there). The image uses **CPU-only PyTorch** to keep size and disk use down (~2–3 GB instead of 10+ GB for CUDA).

```bash
cd ~/object-paint-agent
docker compose -f docker-compose.groundingdino.yml up -d --build
```

The first build can take 10–20 minutes (PyTorch and GroundingDINO are installed). When it finishes, check:

```bash
docker compose -f docker-compose.groundingdino.yml ps
curl -s http://localhost:7860/health
```

You should see the container **Up** and `{"status":"ok",...}`. In the app UI, enable **“Use Grounding DINO”** and click **Detect objects**.

**You are done for Path B.** Go to **Step 9**.

---

## Step 9: Open the app in your browser

1. On your PC, open a browser.
2. Go to: **http://EC2_PUBLIC_IP:7860**  
   Example: `http://54.123.45.67:7860`
3. You should see the Object Paint Agent UI: upload an image, add points or a box, generate mask, apply recolor, export.

If the page does not load:

- Confirm the EC2 instance is **Running** and the security group allows **port 7860** from your IP (or 0.0.0.0/0) — see Step 3.
- On EC2, run: `curl -s http://localhost:7860/health`. If that works, the app is running and the problem is network/firewall.

---

## Step 10: (Optional) Run the app automatically after reboot

So the container starts again if the instance restarts:

**Path A (lite):**

```bash
cd ~/object-paint-agent
echo "@reboot cd /home/ubuntu/object-paint-agent && docker compose up -d" | crontab -
```

**Path B (Grounding DINO):**

```bash
cd ~/object-paint-agent
echo '@reboot cd /home/ubuntu/object-paint-agent && docker compose -f docker-compose.groundingdino.yml up -d' | crontab -
```

---

## Quick reference — commands on EC2

| What you want              | Command (run in `~/object-paint-agent`)     |
|---------------------------|---------------------------------------------|
| Start app (lite)          | `docker compose up -d`                      |
| Stop app (lite)           | `docker compose down`                       |
| View logs (lite)          | `docker compose logs -f`                    |
| Rebuild after code change | `docker compose up -d --build`              |
| Start app (Path B)        | `docker compose -f docker-compose.groundingdino.yml up -d` |
| Stop app (Path B)         | `docker compose -f docker-compose.groundingdino.yml down`  |
| Health check              | `curl -s http://localhost:7860/health`      |

---

## Summary checklist

- [ ] Key pair created and .pem/.ppk saved (Step 2).
- [ ] Security group created with SSH (22) and app (7860) (Step 3).
- [ ] EC2 instance launched (Ubuntu 22.04, t3.small or t3.medium for Grounding DINO) (Step 4).
- [ ] Connected via SSH (Step 5).
- [ ] Docker and Docker Compose installed; logged out and back in (Step 6).
- [ ] Project code on instance in `~/object-paint-agent` (Step 7).
- [ ] App running: Path A (`docker compose up -d`) or Path B (build + run with `Dockerfile.groundingdino` and weights) (Step 8).
- [ ] Browser opens `http://<EC2-public-IP>:7860` and shows the app (Step 9).

This single document is enough to deploy the entire solution on AWS EC2 from start to finish.
