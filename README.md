# Massimo Dutti SG — Discord Bot Monitor 🛍️

Control your watchlist with slash commands directly in Discord:
- `/add [url] [name]` — Add a product
- `/remove [name]` — Remove a product  
- `/list` — See your watchlist
- `/check` — Instant check right now
- `/help` — All commands

---

## Part 1 — Create your Discord Bot (5 min)

### 1. Go to Discord Developer Portal
→ https://discord.com/developers/applications

### 2. Create a new application
- Click **New Application** (top right)
- Name it `MD Monitor` → Create

### 3. Create the Bot
- Click **Bot** in the left sidebar
- Click **Add Bot** → Yes, do it!
- Under **Token** → click **Reset Token** → **Copy** and save it somewhere safe
  - ⚠️ This is your `DISCORD_BOT_TOKEN` — treat it like a password

### 4. Enable required permissions
Still on the Bot page, scroll down to **Privileged Gateway Intents** and turn on:
- ✅ Message Content Intent (optional but useful)

### 5. Invite the bot to your server
- Click **OAuth2** → **URL Generator** in the left sidebar
- Under **Scopes** tick: `bot` and `applications.commands`
- Under **Bot Permissions** tick: `Send Messages`, `Embed Links`, `Read Message History`
- Copy the generated URL at the bottom → open it in your browser → select your server → Authorize

---

## Part 2 — Get your Channel ID

This is where the bot will post sale alerts.

1. In Discord, go to **Settings** → **Advanced** → turn on **Developer Mode**
2. Right-click the channel you want alerts in → **Copy Channel ID**
3. Save this number — it's your `DISCORD_CHANNEL_ID`

---

## Part 3 — Deploy to Railway

### 3a. Push to GitHub
1. Go to https://github.com → New repository → name it `md-monitor` → Private → Create
2. Upload these 3 files: `monitor.py`, `requirements.txt`, `Dockerfile`

### 3b. Deploy on Railway
1. Go to https://railway.app → sign up with GitHub
2. **New Project** → **Deploy from GitHub repo** → select `md-monitor`
3. Wait for the build (~1 min)

### 3c. Add a Volume (so your basket saves permanently)
1. In Railway, click your service → **+ Add** → **Volume**
2. Set Mount Path to `/data`
3. Click **Add**

### 3d. Add environment variables
Go to your service → **Variables** tab → add these:

| Variable | Value |
|---|---|
| `DISCORD_BOT_TOKEN` | your bot token from Step 1 |
| `DISCORD_CHANNEL_ID` | your channel ID from Part 2 |
| `CHECK_INTERVAL_MINUTES` | `30` (or any number) |

Railway will restart automatically.

---

## Part 4 — Verify it works

1. In your Discord channel you should see: **"✅ Massimo Dutti Monitor is Live!"**
2. Type `/add` in Discord — you should see the slash command appear
3. Try: `/add https://www.massimodutti.com/sg/[product-url] My Item`

---

## Using the bot

**Add an item:**
```
/add url:https://www.massimodutti.com/sg/slim-fit-suit-... name:Slim Fit Suit
```

**See your watchlist:**
```
/list
```

**Remove an item:**
```
/remove name:Slim Fit Suit
```

**Check everything right now:**
```
/check
```

---

## How to get a product URL
1. Go to massimodutti.com/sg
2. Browse and click the product you want
3. Copy the full URL from your browser's address bar
4. Paste it into `/add`

---

## Cost
Railway free tier = $5/month credit. This bot is very lightweight and should run free indefinitely.
