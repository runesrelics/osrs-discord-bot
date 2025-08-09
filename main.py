import os
import discord
from discord.ext import commands
import asyncio
from config import COMMAND_PREFIX
from database.db import Database

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Initialize bot
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# List of cogs to load
COGS = [
    'cogs.events',
    'cogs.listings',
    'cogs.vouch',
    'cogs.react_roles'
]

async def load_cogs():
    """Load all cogs"""
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Loaded {cog}")
        except Exception as e:
            print(f"Error loading {cog}: {e}")

async def main():
    """Main function to run the bot"""
    # Initialize the database
    await Database.initialize()
    
    # Load all cogs
    await load_cogs()
    
    # Start the bot
    TOKEN = os.getenv("RELLY_DISCORD")
    if not TOKEN:
        raise ValueError("RELLY_DISCORD environment variable not set")
        
    try:
        await bot.start(TOKEN)
    except Exception as e:
        print(f"Error starting bot: {e}")

# Run the bot
if __name__ == "__main__":
    asyncio.run(main())