import os
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")


def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id SERIAL PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            discord_id TEXT NOT NULL,
            discord_tag TEXT NOT NULL,
            hwid TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            is_banned BOOLEAN DEFAULT FALSE,
            executions INT DEFAULT 0,
            last_used TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def require_internal(f):
    """Protect bot-only endpoints with a shared secret."""
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = request.headers.get("X-Internal-Secret")
        if secret != INTERNAL_SECRET:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def generate_key(length=32):
    alphabet = string.ascii_letters + string.digits
    return "KA-" + "".join(secrets.choice(alphabet) for _ in range(length))


# ── Bot-facing endpoints ────────────────────────────────────────────────────

@app.route("/bot/create_key", methods=["POST"])
@require_internal
def create_key():
    data = request.json
    discord_id = str(data["discord_id"])
    discord_tag = data["discord_tag"]
    days = int(data.get("days", 30))

    conn = get_db()
    cur = conn.cursor()

    # Check if user already has an active key
    cur.execute(
        "SELECT key, expires_at FROM keys WHERE discord_id = %s AND is_banned = FALSE ORDER BY created_at DESC LIMIT 1",
        (discord_id,)
    )
    existing = cur.fetchone()
    if existing and existing["expires_at"] > datetime.utcnow():
        cur.close()
        conn.close()
        return jsonify({
            "success": False,
            "error": "User already has an active key",
            "key": existing["key"],
            "expires_at": existing["expires_at"].isoformat()
        })

    key = generate_key()
    expires_at = datetime.utcnow() + timedelta(days=days)

    cur.execute(
        """INSERT INTO keys (key, discord_id, discord_tag, expires_at)
           VALUES (%s, %s, %s, %s)""",
        (key, discord_id, discord_tag, expires_at)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "key": key, "expires_at": expires_at.isoformat(), "days": days})


@app.route("/bot/revoke_key", methods=["POST"])
@require_internal
def revoke_key():
    data = request.json
    discord_id = str(data["discord_id"])

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE keys SET is_banned = TRUE WHERE discord_id = %s AND is_banned = FALSE",
        (discord_id,)
    )
    affected = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()

    if affected == 0:
        return jsonify({"success": False, "error": "No active key found for that user"})
    return jsonify({"success": True})


@app.route("/bot/reset_hwid", methods=["POST"])
@require_internal
def reset_hwid():
    data = request.json
    discord_id = str(data["discord_id"])

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE keys SET hwid = NULL WHERE discord_id = %s AND is_banned = FALSE",
        (discord_id,)
    )
    affected = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()

    if affected == 0:
        return jsonify({"success": False, "error": "No active key found"})
    return jsonify({"success": True})


@app.route("/bot/lookup", methods=["GET"])
@require_internal
def lookup():
    discord_id = str(request.args.get("discord_id", ""))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT key, expires_at, hwid, executions, last_used, is_banned FROM keys WHERE discord_id = %s ORDER BY created_at DESC LIMIT 1",
        (discord_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": "No key found"})

    return jsonify({
        "success": True,
        "key": row["key"],
        "expires_at": row["expires_at"].isoformat(),
        "hwid_locked": row["hwid"] is not None,
        "executions": row["executions"],
        "last_used": row["last_used"].isoformat() if row["last_used"] else None,
        "is_banned": row["is_banned"]
    })


# ── Script-facing endpoint ──────────────────────────────────────────────────

@app.route("/auth", methods=["POST"])
def auth():
    """
    Called by the Lua script on startup.
    Body: { "key": "KA-...", "hwid": "<getmachineid()>" }
    Returns: { "success": true/false, "script": "<lua source>" or "error": "..." }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid request"}), 400

    key = data.get("key", "").strip()
    hwid = data.get("hwid", "").strip()

    if not key or not hwid:
        return jsonify({"success": False, "error": "Missing key or hwid"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM keys WHERE key = %s", (key,))
    row = cur.fetchone()

    if not row:
        cur.close(); conn.close()
        return jsonify({"success": False, "error": "Invalid key"})

    if row["is_banned"]:
        cur.close(); conn.close()
        return jsonify({"success": False, "error": "Key is banned"})

    if row["expires_at"] < datetime.utcnow():
        cur.close(); conn.close()
        return jsonify({"success": False, "error": "Key has expired"})

    # HWID lock: if no HWID stored yet, lock it to this machine
    if row["hwid"] is None:
        cur.execute("UPDATE keys SET hwid = %s WHERE key = %s", (hwid, key))
    elif row["hwid"] != hwid:
        cur.close(); conn.close()
        return jsonify({"success": False, "error": "HWID mismatch — contact support to reset"})

    # Update stats
    cur.execute(
        "UPDATE keys SET executions = executions + 1, last_used = NOW() WHERE key = %s",
        (key,)
    )
    conn.commit()
    cur.close()
    conn.close()

    # Serve the protected script
    try:
        with open("protected_script.lua", "r") as f:
            script = f.read()
    except FileNotFoundError:
        script = "-- Protected script not uploaded yet"

    return jsonify({"success": True, "script": script})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
