# 🦙 Ollama Chatbot on AWS EC2

A self-hosted chatbot that runs **open-source LLMs** (Llama, Mistral, Gemma, etc.) entirely on your own AWS EC2 instance using [Ollama](https://ollama.com). No OpenAI API key, no external calls — your data stays on your server.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [EC2 Instance Recommendations](#ec2-instance-recommendations)
5. [Quick Deploy (One Command)](#quick-deploy-one-command)
6. [Step-by-Step Deployment](#step-by-step-deployment)
7. [Managing Ollama Models](#managing-ollama-models)
8. [API Reference](#api-reference)
9. [Environment Variables](#environment-variables)
10. [Local Development](#local-development)
11. [GPU Support](#gpu-support)
12. [Security & Networking](#security--networking)
13. [Troubleshooting](#troubleshooting)
14. [Useful Commands](#useful-commands)

---

## Architecture Overview

```
                        Internet
                            │
                            ▼
                  ┌─────────────────────┐
                  │   AWS EC2 Instance  │
                  │                     │
                  │  ┌───────────────┐  │
 User Browser ───►│  │  Chatbot App  │  │  :8000
                  │  │  (FastAPI)    │  │
                  │  └──────┬────────┘  │
                  │         │           │
                  │  ┌──────▼────────┐  │
                  │  │    Ollama     │  │  :11434 (internal)
                  │  │  (LLM engine) │  │
                  │  └───────────────┘  │
                  │                     │
                  │  Docker Compose     │
                  └─────────────────────┘
```

- **Chatbot (port 8000):** FastAPI app serving the web UI and a streaming `/api/chat` endpoint. Talks to Ollama over Docker's internal network.
- **Ollama (port 11434):** Runs the LLM locally. Model weights are persisted in a Docker volume so they survive restarts.
- Both services run in **Docker Compose** on a single EC2 instance.

---

## Project Structure

```
ollama-chatbot/
├── app.py               # FastAPI chatbot — UI + streaming chat API
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container image for the chatbot
├── docker-compose.yml   # Orchestrates Ollama + Chatbot
├── setup.sh             # One-shot EC2 bootstrap script
├── .env.example         # Environment variable template
└── .gitignore
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| AWS account | EC2 launch permissions |
| SSH key pair | To connect to EC2 |
| AWS CLI (optional) | Helpful but not required |
| Git | To clone/push your project |

No local Docker or Python required — everything runs on EC2.

---

## EC2 Instance Recommendations

Model size determines how much RAM and compute you need.

| Model | Parameters | Min Instance | Recommended | Notes |
|---|---|---|---|---|
| llama3.2 | 3B | t3.medium (4 GB) | t3.large | Fast, lightweight |
| llama3.1 / mistral | 7–8B | t3.large (8 GB) | t3.xlarge | Good balance |
| llama3.1 | 70B | r6i.4xlarge (128 GB) | GPU instance | Slow on CPU |
| Any model | — | g4dn.xlarge | g4dn.xlarge | GPU: 16 GB VRAM |

> **Recommended starting point:** `t3.large` (2 vCPU, 8 GB RAM) with **Ubuntu 22.04 LTS** or **Amazon Linux 2023**.  
> **Storage:** 30–50 GB gp3 EBS volume (model files are 2–8 GB each).

---

## Quick Deploy (One Command)

If you just want everything running immediately:

```bash
# 1. Launch EC2, SSH in, then:
curl -fsSL https://raw.githubusercontent.com/<your-org>/<your-repo>/main/setup.sh -o setup.sh
chmod +x setup.sh
sudo ./setup.sh --model llama3.2
```

That's it. Visit `http://<your-ec2-ip>:8000` when it finishes.

---

## Step-by-Step Deployment

### Step 1 — Launch an EC2 Instance

1. Go to **EC2 → Launch Instance** in the AWS Console.
2. Choose **Ubuntu 22.04 LTS** (or Amazon Linux 2023).
3. Select instance type (see recommendations above).
4. Configure storage: **30 GB minimum** (50 GB recommended).
5. Under **Security Group**, add these inbound rules:

   | Type | Port | Source |
   |---|---|---|
   | SSH | 22 | Your IP |
   | Custom TCP | 8000 | 0.0.0.0/0 (chatbot UI) |
   | Custom TCP | 11434 | Your IP only (Ollama API — keep restricted) |

6. Launch and download your `.pem` key.

---

### Step 2 — Copy Project Files to EC2

```bash
# From your local machine, in the project directory:
scp -i ~/.ssh/your-key.pem -r . ubuntu@<EC2-PUBLIC-IP>:/home/ubuntu/ollama-chatbot
```

Or clone directly on EC2 if you've pushed to Git:

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2-PUBLIC-IP>
git clone https://github.com/<your-org>/<your-repo>.git ollama-chatbot
cd ollama-chatbot
```

---

### Step 3 — Run the Setup Script

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2-PUBLIC-IP>
cd ollama-chatbot

chmod +x setup.sh

# Option A: Start stack only, pull model manually later
sudo ./setup.sh

# Option B: Start stack AND pull a model automatically
sudo ./setup.sh --model llama3.2

# Option C: Custom chatbot port
sudo ./setup.sh --model mistral --port 3000
```

The script will:
1. Install Docker and Docker Compose
2. Copy project files to `/opt/ollama-chatbot`
3. Build and start the Compose stack
4. Pull the specified Ollama model (if provided)
5. Print the access URL

**Expected output:**

```
[setup] Installing Docker on ubuntu …
[  ok ] Docker installed.
[setup] Starting Docker Compose stack …
[  ok ] Stack started.
[setup] Pulling model: llama3.2 (this may take a few minutes) …
[  ok ] Model 'llama3.2' ready.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[  ok ] Setup complete!

  Chatbot UI  →  http://54.123.45.67:8000
  Ollama API  →  http://54.123.45.67:11434

  Useful commands:
    docker compose -f /opt/ollama-chatbot/docker-compose.yml logs -f
    docker exec ollama ollama pull <model>
    docker exec ollama ollama list
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Step 4 — Open the Chatbot

Navigate to `http://<EC2-PUBLIC-IP>:8000` in your browser.

- The **status dot** (top right) turns green when Ollama is reachable.
- The **model dropdown** lists all pulled models — select one and start chatting.
- Responses stream in real-time, token by token.

---

## Managing Ollama Models

All model operations run via `docker exec` into the Ollama container:

```bash
# List available (already pulled) models
docker exec ollama ollama list

# Pull a new model
docker exec ollama ollama pull llama3.2
docker exec ollama ollama pull mistral
docker exec ollama ollama pull gemma2:2b
docker exec ollama ollama pull codellama
docker exec ollama ollama pull phi3

# Remove a model (frees disk space)
docker exec ollama ollama rm llama3.2

# Show model info
docker exec ollama ollama show llama3.1
```

> Model weights are stored in the `ollama_data` Docker volume and **survive container restarts**. They are only removed if you delete the volume or run `ollama rm`.

### Popular Models Reference

| Model | Pull Command | RAM Needed | Best For |
|---|---|---|---|
| llama3.2 (3B) | `ollama pull llama3.2` | 4 GB | Fast, general chat |
| llama3.1 (8B) | `ollama pull llama3.1` | 8 GB | Quality chat |
| mistral (7B) | `ollama pull mistral` | 6 GB | Instruction following |
| gemma2 (2B) | `ollama pull gemma2:2b` | 3 GB | Lightweight |
| codellama (7B) | `ollama pull codellama` | 6 GB | Code generation |
| phi3 (3.8B) | `ollama pull phi3` | 4 GB | Microsoft, efficient |

Full model library: [ollama.com/library](https://ollama.com/library)

---

## API Reference

### `GET /`
Returns the chat web UI (HTML page).

---

### `GET /health`
Returns Ollama connection status and list of available models.

**Response:**
```json
{
  "status": "ok",
  "ollama": "connected",
  "models": ["llama3.2:latest", "mistral:latest"]
}
```

---

### `POST /api/chat`
Streams a chat completion from Ollama.

**Request body:**
```json
{
  "model": "llama3.2",
  "messages": [
    { "role": "user", "content": "What is the capital of France?" }
  ]
}
```

**Response:** `text/event-stream` (SSE)

Each event:
```
data: {"token": "Paris"}
data: {"token": " is"}
data: {"token": " the capital"}
...
data: [DONE]
```

**Example with curl:**
```bash
curl -N -X POST http://<EC2-IP>:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

### `GET /api/models`
Returns raw model list from Ollama.

**Response:**
```json
{
  "models": [
    { "name": "llama3.2:latest", "size": 2019393189, ... }
  ]
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint (set automatically in Compose) |
| `OLLAMA_MODEL` | `llama3.2` | Default model shown in UI |

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

`.env`:
```env
OLLAMA_MODEL=mistral
```

Then restart:
```bash
docker compose down && docker compose up -d
```

---

## Local Development

Run the full stack locally (requires Docker Desktop):

```bash
# Clone the repo
git clone https://github.com/<your-org>/<your-repo>.git
cd ollama-chatbot

# Start Ollama + chatbot
docker compose up --build

# Pull a model (in a separate terminal)
docker exec ollama ollama pull llama3.2

# Open the UI
open http://localhost:8000
```

To run the Python app directly (without Docker), point it at a running Ollama instance:

```bash
# Start Ollama separately (install from https://ollama.com)
ollama serve

# In another terminal:
pip install -r requirements.txt
OLLAMA_BASE_URL=http://localhost:11434 uvicorn app:app --reload --port 8000
```

---

## GPU Support

If your EC2 instance has an NVIDIA GPU (e.g., `g4dn.xlarge` with Tesla T4):

### 1. Install NVIDIA drivers on EC2

```bash
# Ubuntu
sudo apt-get install -y nvidia-driver-535 nvidia-utils-535

# Verify
nvidia-smi
```

### 2. Install NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 3. Enable GPU in docker-compose.yml

Uncomment the `deploy` section in `docker-compose.yml`:

```yaml
ollama:
  image: ollama/ollama:latest
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

Then restart:
```bash
docker compose down && docker compose up -d
```

GPU inference is **5–20× faster** than CPU for 7B+ models.

---

## Security & Networking

### Expose only what's needed

| Port | Recommended Access | Reason |
|---|---|---|
| 8000 | Public (0.0.0.0/0) | Chatbot UI |
| 11434 | Your IP only | Ollama API — no auth built-in |
| 22 | Your IP only | SSH |

### Add authentication (optional)

For production, put the chatbot behind a reverse proxy with basic auth:

```nginx
# /etc/nginx/sites-available/chatbot
server {
    listen 80;
    server_name your-domain.com;

    auth_basic "Chatbot";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;   # required for SSE streaming
    }
}
```

Create password file:
```bash
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd youruser
```

### Keep Ollama internal

The Chatbot container talks to Ollama via Docker's internal network (`http://ollama:11434`). Ollama's port 11434 is exposed on the host for convenience but should be **locked down** in your Security Group unless you need direct API access.

---

## Troubleshooting

### Chatbot UI shows "Ollama unreachable"

```bash
# Check if Ollama container is running and healthy
docker compose ps

# Check Ollama logs
docker compose logs ollama

# Test Ollama from inside the chatbot container
docker exec chatbot curl http://ollama:11434/api/tags
```

---

### "No models pulled yet" in the dropdown

```bash
# Pull a model
docker exec ollama ollama pull llama3.2

# Refresh the browser page
```

---

### Out of memory / container killed

The OOM killer will stop the Ollama container if the model is too large for your instance. Solutions:

1. Use a smaller model (e.g., `gemma2:2b` or `llama3.2` 3B)
2. Upgrade to a larger instance type
3. Add swap space:

```bash
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

### Port 8000 not accessible

1. Check EC2 Security Group — inbound TCP 8000 must be open.
2. Confirm container is running: `docker compose ps`
3. Check if another process is using the port: `sudo ss -tlnp | grep 8000`

---

### Docker Compose not found

```bash
# Test
docker compose version

# If missing, install plugin manually
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
sudo curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

---

### Slow responses on CPU

This is normal for large models on CPU-only instances. Options:

- Use a smaller/quantized model (e.g., `phi3`, `gemma2:2b`)
- Switch to a GPU instance (`g4dn.xlarge`)
- Use `q4_0` quantized variants: `ollama pull llama3.1:8b-instruct-q4_0`

---

## Useful Commands

```bash
# View live logs from both services
docker compose logs -f

# View only chatbot logs
docker compose logs -f chatbot

# View only Ollama logs
docker compose logs -f ollama

# Restart everything
docker compose restart

# Stop everything
docker compose down

# Stop and remove volumes (WARNING: deletes downloaded models)
docker compose down -v

# Rebuild chatbot image after code changes
docker compose up -d --build chatbot

# Shell into Ollama container
docker exec -it ollama bash

# Shell into chatbot container
docker exec -it chatbot bash

# Check disk usage (model storage)
docker system df
docker exec ollama du -sh /root/.ollama/models

# Update Ollama to latest version
docker compose pull ollama
docker compose up -d ollama
```

---

## License

MIT
