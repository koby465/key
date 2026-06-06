"""
start.py — runs Flask API + Discord bot in the same process.
Railway runs this via: python start.py
"""
import threading
import os

# Init DB before anything
from server import app, init_db
init_db()

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def run_bot():
    # Import here so bot.py env vars are already loaded
    import bot  # noqa: F401

if __name__ == "__main__":
    t1 = threading.Thread(target=run_flask, daemon=True)
    t1.start()
    run_bot()   # bot.run() blocks, so runs on main thread
