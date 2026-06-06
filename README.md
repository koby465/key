# Key Auth System — Setup Guide

## Files
| File | What it does |
|------|-------------|
| `server.py` | Flask API — handles auth, key creation, HWID locking |
| `bot.py` | Discord bot — slash commands for admins |
| `start.py` | Starts both Flask + bot together |
| `loader.lua` | Paste this into Potassium — authenticates the user |
| `protected_script.lua` | Your actual script (you create this) — only served after auth |

---

## Step 1 — Railway Setup

1. Push all files to a **GitHub repo**
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add a **PostgreSQL** plugin inside Railway (click + → Database → PostgreSQL)
4. Railway auto-sets `DATABASE_URL` for you

---

## Step 2 — Environment Variables

Set these in Railway under **Variables**:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Auto-set by Railway PostgreSQL plugin |
| `BOT_TOKEN` | Your Discord bot token from discord.dev |
| `INTERNAL_SECRET` | Any long random string (e.g. `openssl rand -hex 32`) |
| `API_URL` | Your Railway app URL (e.g. `https://myapp.railway.app`) |
| `ADMIN_ROLE_ID` | The Discord role ID that can use admin commands |
| `KEY_CHANNEL_ID` | (Optional) Channel ID to log key activity |

---

## Step 3 — Discord Bot Setup

1. Go to [discord.dev/applications](https://discord.com/developers/applications)
2. Create a new app → Bot → copy token → set as `BOT_TOKEN`
3. Under **Privileged Gateway Intents**, enable **Server Members Intent**
4. Invite bot with scopes: `bot` + `applications.commands`
5. Create an "Admin" role in your server, copy its ID → set as `ADMIN_ROLE_ID`

---

## Step 4 — Your Protected Script

Create `protected_script.lua` in the same folder as `server.py`.
This is what gets served to users after successful auth.

```lua
-- protected_script.lua
print("Script loaded successfully!")
-- your actual script code here
```

---

## Step 5 — Lua Loader

1. Open `loader.lua`
2. Replace `YOUR-APP.railway.app` with your actual Railway URL
3. Paste `loader.lua` into Potassium to run it

Users put their key in a file called `auth_key.txt` in Potassium's workspace folder.

---

## Discord Commands

| Command | Who | What |
|---------|-----|------|
| `/genkey @user 30` | Admin | Generate a 30-day key, DMs it to user |
| `/revokekey @user` | Admin | Ban a user's key |
| `/resethwid @user` | Admin | Reset HWID so user can re-lock on new PC |
| `/lookup @user` | Admin | See all key info for a user |
| `/mystats` | Anyone | Check their own key status |

---

## How HWID Locking Works

1. User runs loader first time → key + HWID sent to server
2. Server stores the HWID against the key (locked)
3. Next time user runs it, HWID must match — if it doesn't, auth fails
4. Admin can `/resethwid` if the user changes PC

---

## Security Notes

- Script source is **never in the loader** — it's fetched server-side after auth
- `INTERNAL_SECRET` protects bot→API communication — keep it private
- Keys are 32-char random alphanumeric with `KA-` prefix
- Expired/banned keys are rejected at the API level
