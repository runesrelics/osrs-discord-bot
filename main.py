import os
import discord
from discord.ext import commands

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# List of cogs to load
INITIAL_EXTENSIONS = [
    'cogs.vouch',
    'cogs.listings',
    'cogs.tickets',
    'cogs.test_layout'
]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Load all cogs
    for extension in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(extension)
            print(f"Loaded extension {extension}")
        except Exception as e:
            print(f"Failed to load extension {extension}: {e}")
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

TOKEN = os.getenv("RELLY_DISCORD")
bot.run(TOKEN)