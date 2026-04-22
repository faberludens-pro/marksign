# How to Run MarkSign

## One-time setup (install these first)

### 1. Install Node.js

1. Go to [https://nodejs.org](https://nodejs.org)
2. Click the big green **"LTS"** button to download
3. Open the downloaded file and follow the installer — click "Next" / "Continue" through everything
4. To verify it worked, open **Terminal** (search "Terminal" in Spotlight with `Cmd + Space`) and type:
   ```
   node --version
   ```
   You should see a version number like `v22.x.x`

### 2. Install Docker Desktop

1. Go to [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. Download **Docker Desktop for Mac**
3. Open the downloaded file, drag Docker into your Applications folder
4. Open Docker Desktop from Applications — it will ask for your password, that's normal
5. Wait until the Docker icon in your menu bar shows **"Docker Desktop is running"**

---

## Every time you want to use MarkSign

Open **Terminal** and run these commands one at a time.

### Step 1 — Make sure Docker Desktop is open

Open it from your Applications folder if it isn't already running.

### Step 2 — Start the backend (file conversion engine)

```bash
cd ~/Library/Mobile\ Documents/com\~apple\~CloudDocs/Faber-Ludens-Pro/Projects/faberludenspro-marksign/2026-03-converter-engine/marksign-web-app/server
```

```bash
docker build -t marksign-server .
```

```bash
docker run -d -p 8000:8000 marksign-server
```

> The first time this will take a few minutes to download everything. After that it's fast.

### Step 3 — Start the frontend (the app interface)

```bash
cd ~/Library/Mobile\ Documents/com\~apple\~CloudDocs/Faber-Ludens-Pro/Projects/faberludenspro-marksign/2026-03-converter-engine/marksign-web-app
```

```bash
npm install
```

```bash
npm run dev
```

### Step 4 — Open the app

Go to your browser (Chrome or Safari) and visit: **http://localhost:5173**

---

## To stop MarkSign

- In the Terminal window where the frontend is running, press `Ctrl + C`
- To stop the backend, run:
  ```bash
  docker stop $(docker ps -q --filter ancestor=marksign-server)
  ```

---

## Quick reference

| Requirement        | Cost | What for                        |
| ------------------ | ---- | ------------------------------- |
| **Node.js**        | Free | Runs the app interface          |
| **Docker Desktop** | Free | Runs the file conversion engine |

No accounts, no API keys, no subscriptions needed. Everything runs locally on your Mac.
