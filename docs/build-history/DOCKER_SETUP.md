# Docker Setup & Verification

**Fix common Docker issues and verify your installation**

---

## Check Your Docker Installation

### Verify Docker is Installed

```bash
docker --version
# Should output: Docker version 20.10.x or higher

docker run hello-world
# Should output: "Hello from Docker!"
```

### Verify Docker Compose is Available

```bash
# Modern Docker (24.0+) includes compose built-in
docker compose version
# Should output: Docker Compose version X.X.X

# If you get "command not found", you have an older Docker
# You need to upgrade Docker Desktop or install Docker Compose separately
```

---

## Common Issues & Solutions

### Issue 1: `docker: command not found`

**Solution:** Install Docker Desktop
- macOS: https://docs.docker.com/desktop/install/mac-install/
- Windows: https://docs.docker.com/desktop/install/windows-install/
- Linux: https://docs.docker.com/engine/install/

### Issue 2: `docker compose: command not found` (but `docker` works)

**You have older Docker format.** You have two options:

#### Option A: Upgrade Docker (Recommended)
```bash
# macOS with Homebrew
brew install docker

# Or via Docker Desktop - just update to latest version
```

#### Option B: Use old `docker-compose` command (if you have it)
If you have the old `docker-compose` command installed:

```bash
# Check if you have old compose
docker-compose --version

# If yes, you can use it instead:
docker-compose -f docker-compose.minecraft.yml up -d
# (instead of: docker compose -f docker-compose.minecraft.yml up -d)
```

### Issue 3: Permission Denied Running Docker

```bash
# Error: "permission denied while trying to connect to Docker daemon"

# Solution: Add your user to docker group (Linux/Mac)
sudo usermod -aG docker $USER
newgrp docker

# Then try again:
docker run hello-world
```

---

## Verify Docker Compose Works

```bash
# Create test file
cat > test-compose.yml << 'EOF'
version: '3.8'
services:
  test:
    image: alpine:latest
    command: echo "Docker Compose works!"
EOF

# Test it
docker compose -f test-compose.yml up

# Clean up
rm test-compose.yml
docker compose -f test-compose.yml down
```

---

## All Commands in This Project

### Using Modern `docker compose` (Recommended)

```bash
# Start services
docker compose -f docker-compose.minecraft.yml up -d

# View logs
docker compose -f docker-compose.minecraft.yml logs -f

# Stop services
docker compose -f docker-compose.minecraft.yml down

# Restart a service
docker compose -f docker-compose.minecraft.yml restart minecraft-server-dev

# List running containers
docker compose -f docker-compose.minecraft.yml ps
```

### Using Old `docker-compose` (if you have it)

```bash
# Replace "docker compose" with "docker-compose"
docker-compose -f docker-compose.minecraft.yml up -d
docker-compose -f docker-compose.minecraft.yml logs -f
docker-compose -f docker-compose.minecraft.yml down
```

**Both work identically - use whichever your Docker installation supports.**

---

## Installation by OS

### macOS (with Homebrew)

```bash
# Install Docker Desktop
brew install docker

# Verify
docker --version
docker compose version
```

### macOS (without Homebrew)

Download and install Docker Desktop from: https://www.docker.com/products/docker-desktop

### Windows

Download and install Docker Desktop from: https://www.docker.com/products/docker-desktop

### Linux (Ubuntu/Debian)

```bash
# Install Docker
sudo apt-get update
sudo apt-get install docker.io

# Add yourself to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify
docker --version
docker compose version
```

---

## Verify All Docker Services Work

```bash
# 1. Check Docker daemon is running
docker ps
# Should list running containers (empty if none running)

# 2. Check compose works
docker compose version

# 3. Test with simple container
docker run --rm alpine:latest echo "Docker is working!"

# 4. Check you can pull images
docker pull alpine:latest
# Should complete successfully
```

---

## For the EVOKE Project

### Verify You Can Run Our Compose Files

```bash
cd ~/evoke-prosperity

# Check Minecraft compose file
docker compose -f docker-compose.minecraft.yml config
# Should output the YAML configuration without errors

# Check database compose file (if exists)
docker compose -f evoke-infra/docker-compose.yml config
# Should output the YAML configuration without errors
```

---

## Quick Commands Reference

| Task | Command |
|------|---------|
| **Start Minecraft** | `docker compose -f docker-compose.minecraft.yml up -d` |
| **Stop Minecraft** | `docker compose -f docker-compose.minecraft.yml down` |
| **View Logs** | `docker compose -f docker-compose.minecraft.yml logs -f` |
| **Check Status** | `docker compose -f docker-compose.minecraft.yml ps` |
| **Restart** | `docker compose -f docker-compose.minecraft.yml restart` |
| **Enter Console** | `docker exec -it minecraft-server-dev rcon-cli` |

---

## Troubleshooting Docker Issues

### Docker daemon won't start
```bash
# macOS/Windows
# Open Docker Desktop application

# Linux
sudo systemctl start docker
sudo systemctl status docker
```

### Out of disk space
```bash
# Check disk usage
docker system df

# Clean up unused images/containers
docker system prune -a

# Remove specific image
docker rmi image-name
```

### Container won't start
```bash
# Check logs
docker compose -f docker-compose.minecraft.yml logs minecraft-server-dev

# Restart container
docker compose -f docker-compose.minecraft.yml restart minecraft-server-dev

# If still failing, rebuild
docker compose -f docker-compose.minecraft.yml down
docker compose -f docker-compose.minecraft.yml up -d
```

---

## Next Steps

Once Docker is verified working:

1. **Run:** `bash scripts/minecraft-setup.sh`
2. **Verify:** `docker compose -f docker-compose.minecraft.yml ps`
3. **Check logs:** `docker logs minecraft-server-dev`
4. **Start EVOKE:** `python -m evoke.main`
5. **Test:** `curl http://localhost:8000/api/minecraft/status`

**Everything working? Jump to `QUICKSTART.md`!** 🚀
