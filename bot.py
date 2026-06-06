import os
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
API_URL = os.environ["API_URL"]              # e.g. https://your-app.railway.app
INTERNAL_SECRET = os.environ["INTERNAL_SECRET"]
ADMIN_ROLE_ID = int(os.environ["ADMIN_ROLE_ID"])  # Discord role ID for admins
KEY_CHANNEL_ID = int(os.environ.get("KEY_CHANNEL_ID", 0))  # optional log channel

HEADERS = {"X-Internal-Secret": INTERNAL_SECRET, "Content-Type": "application/json"}

# ── Bot setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


def is_admin():
    async def predicate(interaction: discord.Interaction):
        role = discord.utils.get(interaction.user.roles, id=ADMIN_ROLE_ID)
        if role is None:
            await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


async def log_to_channel(bot: commands.Bot, embed: discord.Embed):
    if KEY_CHANNEL_ID:
        ch = bot.get_channel(KEY_CHANNEL_ID)
        if ch:
            await ch.send(embed=embed)


# ── Slash commands ───────────────────────────────────────────────────────────

@tree.command(name="genkey", description="Generate a key for a user")
@is_admin()
@app_commands.describe(user="The user to generate a key for", days="How many days the key lasts (default 30)")
async def genkey(interaction: discord.Interaction, user: discord.Member, days: int = 30):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/bot/create_key",
            json={"discord_id": user.id, "discord_tag": str(user), "days": days},
            headers=HEADERS
        ) as resp:
            data = await resp.json()

    if not data["success"]:
        await interaction.followup.send(
            f"❌ {data['error']}\n**Existing key:** `{data.get('key', 'N/A')}`\n**Expires:** {data.get('expires_at', 'N/A')}",
            ephemeral=True
        )
        return

    key = data["key"]
    expires = data["expires_at"]

    # DM the user their key
    try:
        dm_embed = discord.Embed(
            title="🔑 Your Key",
            color=0x00ff88
        )
        dm_embed.add_field(name="Key", value=f"```{key}```", inline=False)
        dm_embed.add_field(name="Expires", value=expires[:10], inline=True)
        dm_embed.add_field(name="Duration", value=f"{days} days", inline=True)
        dm_embed.set_footer(text="Do NOT share your key. It is HWID locked to your PC.")
        await user.send(embed=dm_embed)
        dm_status = "✅ Key sent via DM"
    except discord.Forbidden:
        dm_status = "⚠️ Couldn't DM user — their DMs are closed"

    await interaction.followup.send(
        f"✅ Key generated for {user.mention}\n{dm_status}\n**Expires:** {expires[:10]}",
        ephemeral=True
    )

    # Log to channel
    log_embed = discord.Embed(title="Key Generated", color=0x00ff88)
    log_embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
    log_embed.add_field(name="Days", value=str(days), inline=True)
    log_embed.add_field(name="By", value=str(interaction.user), inline=True)
    log_embed.timestamp = datetime.utcnow()
    await log_to_channel(bot, log_embed)


@tree.command(name="revokekey", description="Revoke a user's key")
@is_admin()
@app_commands.describe(user="The user whose key to revoke")
async def revokekey(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/bot/revoke_key",
            json={"discord_id": user.id},
            headers=HEADERS
        ) as resp:
            data = await resp.json()

    if not data["success"]:
        await interaction.followup.send(f"❌ {data['error']}", ephemeral=True)
        return

    await interaction.followup.send(f"✅ Revoked key for {user.mention}", ephemeral=True)

    log_embed = discord.Embed(title="Key Revoked", color=0xff4444)
    log_embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
    log_embed.add_field(name="By", value=str(interaction.user), inline=True)
    log_embed.timestamp = datetime.utcnow()
    await log_to_channel(bot, log_embed)


@tree.command(name="resethwid", description="Reset HWID lock for a user")
@is_admin()
@app_commands.describe(user="The user whose HWID to reset")
async def resethwid(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/bot/reset_hwid",
            json={"discord_id": user.id},
            headers=HEADERS
        ) as resp:
            data = await resp.json()

    if not data["success"]:
        await interaction.followup.send(f"❌ {data['error']}", ephemeral=True)
        return

    await interaction.followup.send(f"✅ HWID reset for {user.mention}. They can re-lock on next run.", ephemeral=True)

    log_embed = discord.Embed(title="HWID Reset", color=0xffaa00)
    log_embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
    log_embed.add_field(name="By", value=str(interaction.user), inline=True)
    log_embed.timestamp = datetime.utcnow()
    await log_to_channel(bot, log_embed)


@tree.command(name="mystats", description="Check your key status")
async def mystats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_URL}/bot/lookup",
            params={"discord_id": interaction.user.id},
            headers=HEADERS
        ) as resp:
            data = await resp.json()

    if not data["success"]:
        await interaction.followup.send("❌ You don't have a key. Contact an admin.", ephemeral=True)
        return

    expires = data["expires_at"][:10]
    status = "🔴 Banned" if data["is_banned"] else "🟢 Active"
    hwid = "🔒 Locked" if data["hwid_locked"] else "🔓 Not locked yet"

    embed = discord.Embed(title="Your Key Stats", color=0x5865F2)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="HWID", value=hwid, inline=True)
    embed.add_field(name="Expires", value=expires, inline=True)
    embed.add_field(name="Executions", value=str(data["executions"]), inline=True)
    embed.add_field(name="Last Used", value=data["last_used"][:10] if data["last_used"] else "Never", inline=True)
    embed.set_footer(text="Do NOT share your key")

    await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(name="lookup", description="[Admin] Look up any user's key info")
@is_admin()
@app_commands.describe(user="The user to look up")
async def lookup(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_URL}/bot/lookup",
            params={"discord_id": user.id},
            headers=HEADERS
        ) as resp:
            data = await resp.json()

    if not data["success"]:
        await interaction.followup.send(f"❌ No key found for {user.mention}", ephemeral=True)
        return

    expires = data["expires_at"][:10]
    status = "🔴 Banned" if data["is_banned"] else "🟢 Active"

    embed = discord.Embed(title=f"Key Info — {user}", color=0x5865F2)
    embed.add_field(name="Key", value=f"`{data['key']}`", inline=False)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="HWID Locked", value="Yes" if data["hwid_locked"] else "No", inline=True)
    embed.add_field(name="Expires", value=expires, inline=True)
    embed.add_field(name="Executions", value=str(data["executions"]), inline=True)
    embed.add_field(name="Last Used", value=data["last_used"][:10] if data["last_used"] else "Never", inline=True)

    await interaction.followup.send(embed=embed, ephemeral=True)


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot ready — logged in as {bot.user}")


bot.run(BOT_TOKEN)
