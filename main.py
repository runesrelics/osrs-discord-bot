import os
import discord
from discord.ext import commands
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

class CustomBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.initial_extensions = [
            'cogs.vouch',
            'cogs.listings',
            'cogs.tickets',
            'cogs.test_layout'
        ]

    async def setup_hook(self):
        # Load all cogs
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"✅ Loaded extension {extension}")
            except Exception as e:
                print(f"❌ Failed to load extension {extension}: {e}")

        # Sync commands
        try:
            print("Syncing commands...")
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} commands")
        except Exception as e:
            print(f"❌ Error syncing commands: {e}")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        print("Registered commands:")
        for command in self.commands:
            print(f"- {command.name}")
        print("------")

bot = CustomBot()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        print(f"Command not found: {ctx.message.content}")
        print("Available commands:", [cmd.name for cmd in bot.commands])
    else:
        print(f"Error: {str(error)}")

TOKEN = os.getenv("RELLY_DISCORD")
bot.run(TOKEN)