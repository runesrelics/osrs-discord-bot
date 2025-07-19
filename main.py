import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import io
import sqlite3
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Channel config
CHANNELS = {
    "trusted": {
        "main": 1381504991491260528,
        "pvp": 1393405064374390935,
        "ironman": 1393405855700877394,
        "gp": 1393727788112154745,
    },
    "public": {
        "main": 1393407626490024038,
        "pvp": 1393407738188660858,
        "ironman": 1393407893411332217,
        "gp": 1393727911743193239,
    },
    "create_trade": 1395778950353129472,
    "archive": 1395791949969231945,
    "vouches": 1383401756335149087,
}

EMBED_COLOR = discord.Color.gold()
BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"

# --- DATABASE SETUP ---
conn = sqlite3.connect("vouches.db")
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS vouches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        to_user_id INTEGER,
        stars INTEGER,
        comment TEXT,
        timestamp TEXT
    )
''')
conn.commit()

# --- VOUCH MODAL ---

class VouchModal(Modal, title="Leave a Vouch"):
    stars = Select(
        placeholder="Rate this user",
        options=[discord.SelectOption(label=f"{i} Star{'s' if i > 1 else ''}", value=str(i)) for i in range(1, 6)]
    )
    comment = TextInput(label="Comment", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, from_user, to_user):
        super().__init__()
        self.from_user = from_user
        self.to_user = to_user
        self.add_item(self.stars)

    async def on_submit(self, interaction: discord.Interaction):
        rating = int(self.stars.values[0])
        text = self.comment.value
        now = datetime.utcnow().isoformat()

        # Store in DB
        with sqlite3.connect("vouches.db") as conn:
            c = conn.cursor()
            c.execute("INSERT INTO vouches (from_user_id, to_user_id, stars, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (self.from_user.id, self.to_user.id, rating, text, now))
            conn.commit()

        # Send to vouch channel
        channel = interaction.guild.get_channel(CHANNELS["vouches"])
        if channel:
            embed = discord.Embed(title=f"🌟 New Vouch for {self.to_user.display_name}", color=EMBED_COLOR)
            embed.add_field(name="Rating", value=f"{'⭐' * rating} ({rating}/5)", inline=True)
            embed.add_field(name="From", value=f"{self.from_user.mention}", inline=True)
            embed.add_field(name="Comment", value=text if text else "No comment provided", inline=False)
            embed.set_footer(text=now)
            await channel.send(embed=embed)

        await interaction.response.send_message("✅ Vouch submitted!", ephemeral=True)

# --- VOUCH SLASH COMMANDS ---

@bot.tree.command(name="vouches", description="Check someone's vouches.")
async def vouches(interaction: discord.Interaction, user: discord.Member):
    with sqlite3.connect("vouches.db") as conn:
        c = conn.cursor()
        c.execute("SELECT stars FROM vouches WHERE to_user_id = ?", (user.id,))
        results = c.fetchall()

    if not results:
        await interaction.response.send_message(f"{user.display_name} has no vouches yet.")
        return

    counts = {i: 0 for i in range(1, 6)}
    for row in results:
        counts[row[0]] += 1

    total = sum(counts.values())
    avg = sum(star * count for star, count in counts.items()) / total

    desc = "\n".join([f"{'⭐'*i}: {counts[i]}" for i in sorted(counts, reverse=True)])

    embed = discord.Embed(
        title=f"{user.display_name}'s Vouch Summary",
        description=desc,
        color=EMBED_COLOR
    )
    embed.set_footer(text=f"{total} total vouches | Avg rating: {avg:.2f}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouch_leaderboard", description="Show the top users by vouch count.")
async def vouch_leaderboard(interaction: discord.Interaction):
    with sqlite3.connect("vouches.db") as conn:
        c = conn.cursor()
        c.execute("SELECT to_user_id, COUNT(*) FROM vouches GROUP BY to_user_id ORDER BY COUNT(*) DESC LIMIT 10")
        rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("No vouches recorded yet.")
        return

    leaderboard = []
    for rank, (user_id, count) in enumerate(rows, 1):
        user = interaction.guild.get_member(user_id)
        name = user.display_name if user else f"User {user_id}"
        leaderboard.append(f"{rank}. **{name}** - {count} vouches")

    embed = discord.Embed(
        title="🏆 Vouch Leaderboard",
        description="\n".join(leaderboard),
        color=EMBED_COLOR
    )
    await interaction.response.send_message(embed=embed)

# --- TICKET ACTIONS CLASS (extended with vouch prompts + DM transcripts) ---

class TicketActions(View):
    def __init__(self, message):
        super().__init__()
        self.message = message
        self.completions = set()

    @discord.ui.button(label="✅ Mark as Complete", style=discord.ButtonStyle.success)
    async def complete(self, interaction: discord.Interaction, button: Button):
        self.completions.add(interaction.user.id)
        if len(self.completions) >= 2:
            await interaction.channel.send("✅ Trade marked as complete. Archiving ticket and prompting vouches.")
            # Prompt vouches to participants
            participants = [m for m in interaction.channel.members if not m.bot]
            if len(participants) >= 2:
                await self.prompt_vouch(participants)
            await self.archive_ticket(interaction.channel, self.message)
        else:
            await interaction.response.send_message("Waiting for the other party to confirm completion.", ephemeral=True)

    @discord.ui.button(label="❌ Cancel Trade", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.send("❌ Trade has been cancelled.")
        await self.archive_ticket(interaction.channel, self.message)

    async def prompt_vouch(self, members):
        if len(members) < 2:
            return
        user1, user2 = members[:2]
        try:
            await user1.send("📝 Please leave a vouch for your trade partner.", view=VouchModal(user1, user2))
        except:
            pass
        try:
            await user2.send("📝 Please leave a vouch for your trade partner.", view=VouchModal(user2, user1))
        except:
            pass

    async def archive_ticket(self, channel, listing_message):
        archive = channel.guild.get_channel(CHANNELS["archive"])
        transcript_lines = []

        async for msg in channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = msg.author.display_name
            content = msg.content or ""
            transcript_lines.append(f"[{timestamp}] {author}: {content}")
            for att in msg.attachments:
                transcript_lines.append(f"[{timestamp}] {author} sent attachment: {att.url}")

        transcript_text = "\n".join(transcript_lines)
        transcript_file_io = io.StringIO(transcript_text)
        discord_file = discord.File(fp=transcript_file_io, filename=f"ticket-{channel.name}-archive.txt")

        if archive:
            await archive.send(content=f"📁 Archived ticket: {channel.name}", file=discord_file)

        # DM transcript to participants (rewind file before sending each time)
        participants = [m for m in channel.members if not m.bot]
        for member in participants:
            try:
                transcript_file_io.seek(0)
                await member.send(
                    content=f"📄 Here is a copy of the archived transcript for ticket **{channel.name}**.",
                    file=discord.File(fp=io.StringIO(transcript_text), filename=f"ticket-{channel.name}-archive.txt")
                )
            except Exception as e:
                print(f"Failed to DM transcript to {member.display_name}: {e}")

        try:
            await listing_message.delete()
        except:
            pass

        await channel.delete()

# --- COMMANDS ---

@bot.event
async def on_ready():
    print(f"Bot is live as {bot.user}.")

@bot.command()
async def setup(ctx):
    if ctx.channel.id != CHANNELS["create_trade"]:
        return await ctx.send("Run this in the create-a-trade channel only.")

    view = View()
    view.add_item(Button(label="🗡️ List OSRS Account", style=discord.ButtonStyle.primary, custom_id="account_listing"))
    view.add_item(Button(label="💰 List OSRS GP", style=discord.ButtonStyle.primary, custom_id="gp_listing"))

    embed = discord.Embed(
        title="📜 Create a Trade Listing",
        description="Select one of the options below to list your account or OSRS GP.",
        color=EMBED_COLOR
    )
    embed.set_thumbnail(url=BRANDING_IMAGE)
    await ctx.send(embed=embed, view=view)

# --- START ---
TOKEN = os.getenv("RELLY_DISCORD")
bot.run(TOKEN)
