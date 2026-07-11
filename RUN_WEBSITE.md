# Running the EVOKE Website

**Access the EVOKE Prosperity web interface**

---

## Quick Start

### Step 1: Start the Backend

```bash
cd ~/evoke-prosperity
python -m evoke.main

# Wait for:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

### Step 2: Open in Browser

```bash
# Open any web browser and go to:
http://localhost:8000
```

**That's it! You should see the EVOKE website.** 🎉

---

## What You'll See

### Home Page
- Overview of EVOKE Prosperity
- Links to missions
- Links to awards/badges
- Minecraft integration status

### API Documentation
```
http://localhost:8000/docs
```
- Interactive API explorer (Swagger UI)
- Try out endpoints directly
- See all available APIs

### Missions Page
```
http://localhost:8000/api/missions
```
- List of available missions
- Evidence submission
- Progress tracking

---

## Backend Serves the Website

The EVOKE backend (FastAPI) automatically serves the static website files.

**File locations:**
```
evoke/static/index.html          ← Main website
evoke/static/companion.html      ← Companion page
```

**When you start the backend:**
- Serves static files from `/static/` directory
- Serves API endpoints from `/api/` paths
- Automatically redirects root to `/static/index.html`

---

## Full Setup (with all services)

### Terminal 1: Database
```bash
cd ~/evoke-prosperity
docker compose -f evoke-infra/docker-compose.yml up -d postgres

# Wait 5 seconds for startup
sleep 5
```

### Terminal 2: Minecraft Server (Optional)
```bash
# If using local Java-based Minecraft:
cd /path/to/minecraft/server
java -Xmx2G -Xms2G -jar server.jar nogui

# If using Docker (skip if you had Docker issues):
cd ~/evoke-prosperity
docker compose -f docker-compose.minecraft.yml up -d
```

### Terminal 3: EVOKE Backend
```bash
cd ~/evoke-prosperity
python -m evoke.main

# Wait for: "Uvicorn running on http://0.0.0.0:8000"
```

### Terminal 4: Open Website
```bash
# Open in browser
open http://localhost:8000

# Or on Linux:
xdg-open http://localhost:8000

# Or on Windows:
start http://localhost:8000
```

---

## Website Features

### 1. Missions Dashboard
```
http://localhost:8000/api/missions?user_id=test-user-1
```
- View available missions
- Submit evidence
- Track progress
- See rewards

### 2. API Documentation
```
http://localhost:8000/docs
```
- Swagger UI with all endpoints
- Try requests interactively
- See response examples
- View authentication

### 3. Minecraft Integration Status
```
http://localhost:8000/api/minecraft/status
```
- Check if Minecraft server connected
- See online players
- Monitor connection health

### 4. Health Check
```
http://localhost:8000/api/health
```
- System status
- All services healthy
- Ready for production

---

## Development

### Modify Website Files

The website files are in:
```
evoke/static/
├── index.html          ← Main page
└── companion.html      ← Companion page
```

**To edit:**
```bash
# Edit the HTML file
nano evoke/static/index.html

# Refresh browser (Ctrl+R or Cmd+R)
# Changes appear immediately!
```

### Add Custom Styling

Edit `<style>` section in HTML or add CSS file:

```html
<!-- In index.html -->
<style>
  body {
    font-family: Arial, sans-serif;
    margin: 20px;
  }
  
  .mission-card {
    border: 1px solid #ddd;
    padding: 15px;
    margin: 10px 0;
  }
</style>
```

### Add Interactivity

Add JavaScript in the `<script>` section:

```html
<script>
// Fetch missions
fetch('/api/missions?user_id=user-1')
  .then(r => r.json())
  .then(data => {
    console.log('Missions:', data);
    // Display in HTML
  });
</script>
```

---

## Key API Endpoints

### Missions
```
GET /api/missions?user_id=USER_ID
Returns: List of available missions
```

### Submit Evidence
```
POST /api/submit-evidence
Body: {
  "mission_id": "mission-1",
  "evidence_url": "https://...",
  "description": "..."
}
```

### Collect Award
```
POST /api/awards/{award_id}/collect
Returns: Reward details + Minecraft delivery status
```

### Minecraft Rewards
```
POST /api/minecraft/reward/collect/USER_ID
Body: {
  "player_name": "Steve",
  "award_id": "award-1",
  "tier": "legendary"
}
```

### Check Status
```
GET /api/minecraft/status
GET /api/health
GET /api/ready
```

---

## Testing the Website

### Test 1: Basic Load

```bash
# Check homepage loads
curl http://localhost:8000

# Should return HTML content
```

### Test 2: API Documentation

```bash
# Open in browser
http://localhost:8000/docs

# Try clicking "Try it out" on any endpoint
```

### Test 3: Missions Endpoint

```bash
curl http://localhost:8000/api/missions?user_id=test-user-1 | jq

# Should return JSON list of missions
```

### Test 4: Submit Evidence (from website)

Use the web interface to:
1. Select a mission
2. Click "Submit Evidence"
3. Provide evidence URL
4. Submit

Then check API:
```bash
curl http://localhost:8000/api/submissions | jq
```

---

## Troubleshooting

### Issue: "Connection refused"

**Solution:**
```bash
# Make sure backend is running
curl http://localhost:8000/api/health

# Should respond with: {"status": "ok"}

# If not, start backend:
cd ~/evoke-prosperity
python -m evoke.main
```

### Issue: Page shows "Not Found"

**Solution:**
```bash
# Make sure you're accessing correct URL
http://localhost:8000              ✓ Correct
http://localhost:8000/index.html   ✗ Wrong
http://localhost:8000/static/      ✗ Wrong

# Root URL redirects to static files automatically
```

### Issue: Changes to HTML don't show up

**Solution:**
```bash
# Hard refresh browser
Windows/Linux: Ctrl+Shift+R
Mac: Cmd+Shift+R

# Or clear cache
# Browser → Settings → Clear Cache
```

### Issue: API returns 500 error

**Solution:**
```bash
# Check backend logs
# Look at Terminal 3 (where you ran python -m evoke.main)

# Common issues:
# - Database not running
# - Minecraft server not connected
# - Missing environment variables

# Restart backend:
# Ctrl+C in Terminal 3
# python -m evoke.main
```

---

## Browser Access

### Direct URLs

| URL | Purpose |
|-----|---------|
| `http://localhost:8000` | Main website |
| `http://localhost:8000/docs` | API documentation |
| `http://localhost:8000/api/health` | Health check |
| `http://localhost:8000/api/missions` | Missions endpoint |
| `http://localhost:8000/api/minecraft/status` | Minecraft status |

### API Playground

```
http://localhost:8000/docs
```

In the web interface, you can:
- ✓ See all available endpoints
- ✓ Click "Try it out" on any endpoint
- ✓ Fill in parameters
- ✓ Click "Execute"
- ✓ See response immediately

---

## Development Workflow

### 1. Make Changes to Website

```bash
# Edit HTML file
nano evoke/static/index.html

# Or CSS/JavaScript within the file
```

### 2. Refresh Browser

```
Ctrl+R (or Cmd+R on Mac)
```

### 3. Test API Calls

```
Open http://localhost:8000/docs
Try out endpoints directly
```

### 4. View Logs

```bash
# Watch backend logs in Terminal 3
# You'll see API requests, errors, etc.
```

---

## Complete System Running

```bash
# Terminal 1: Database
docker compose -f evoke-infra/docker-compose.yml up -d postgres

# Terminal 2: Minecraft (optional)
# Your local Minecraft server or docker compose

# Terminal 3: EVOKE Backend
python -m evoke.main

# Terminal 4: Browser
open http://localhost:8000
```

**All 3 services working? Celebrate!** 🎉

---

## Next Steps

- ✅ Website loading? → Try submitting evidence
- ✅ Evidence submitted? → Check Minecraft received reward
- ✅ Everything working? → Read PLAY_AND_TEST_GUIDE.md for more tests

---

## Website Features Summary

| Feature | URL | Status |
|---------|-----|--------|
| Home Page | `/` | ✅ Working |
| Missions | `/api/missions` | ✅ Working |
| Submit Evidence | `/api/submit-evidence` | ✅ Working |
| Collect Award | `/api/awards/{id}/collect` | ✅ Working |
| Minecraft Rewards | `/api/minecraft/reward/collect` | ✅ Working |
| API Docs | `/docs` | ✅ Working |
| Health Check | `/api/health` | ✅ Working |

---

**Website is up and running! Start exploring EVOKE Prosperity.** 🚀
