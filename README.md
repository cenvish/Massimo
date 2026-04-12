# Massimo Dutti SG Sale Monitor 🛍️

A 24/7 bot that monitors massimodutti.com/sg and sends a Discord alert the moment a sale is detected.

---

## Deploy to Railway (5 minutes)

### Step 1 — Push to GitHub

1. Create a free account at https://github.com if you don't have one
2. Create a **new repository** (click + → New repository)
   - Name it: `md-monitor`
   - Set to **Private**
   - Click **Create repository**
3. Upload these 3 files to the repo:
   - `monitor.py`
   - `requirements.txt`
   - `Dockerfile`

   *(Click "uploading an existing file" on the repo page)*

---

### Step 2 — Deploy on Railway

1. Go to https://railway.app and sign up (free)
2. Click **New Project** → **Deploy from GitHub repo**
3. Connect your GitHub account and select `md-monitor`
4. Railway will auto-detect the Dockerfile and start building

---

### Step 3 — Add your Discord Webhook

1. In your Railway project, click on the service
2. Go to **Variables** tab
3. Add these environment variables:

| Variable | Value |
|---|---|
| `DISCORD_WEBHOOK_URL` | `https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE` |
| `CHECK_INTERVAL_MINUTES` | `30` (or any number you want) |

4. Railway will automatically restart with the new variables

---

### Step 4 — Verify it's running

- Click **Deployments** tab in Railway → you should see logs like:
  ```
  Massimo Dutti SG Sale Monitor starting up
  Site: https://www.massimodutti.com/sg/
  Interval: 30 minutes
  Discord: configured ✓
  ```
- You'll also get a **"✅ Monitor is live!"** message in your Discord channel

---

## Cost

Railway's free **Hobby plan** gives you $5 of credit/month.  
This bot uses barely any resources — it should run **free indefinitely**.

---

## How it works

- Every `CHECK_INTERVAL_MINUTES` minutes, the bot fetches the Massimo Dutti SG homepage
- It scans the page for sale keywords: `sale`, `% off`, `discount`, `promotion`, `offer`, `clearance`, `up to`, `save`, `promo`, etc.
- If found → sends a Discord embed with the keywords and a snippet of what the site says
- Logs every check so you can monitor it in Railway's dashboard

---

## Changing the check interval

In Railway → Variables, change `CHECK_INTERVAL_MINUTES` to any number:
- `15` = every 15 minutes
- `60` = every hour
- `1440` = once a day
