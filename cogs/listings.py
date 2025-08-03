import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import asyncio
from .embed_generator import EmbedGenerator

class ListingCog(commands.Cog, name="Listings"):
    """Commands for managing listings"""
    
    def __init__(self, bot):
        self.bot = bot
        self.EMBED_COLOR = discord.Color.gold()
        self.BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"
        self.CHANNELS = {
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
            "vouch_post": 1383401756335149087
        }

    @commands.command(name="setup_listings")
    @commands.has_permissions(administrator=True)
    async def setup_listings(self, ctx):
        """Sets up the listing buttons in the create_trade channel"""
        print(f"setup_listings command called by {ctx.author}")  # Debug print
        
        if ctx.channel.id != self.CHANNELS["create_trade"]:
            await ctx.send("❌ Please run this command in the create_trade channel.")
            return

        # Create persistent view for the buttons
        class PersistentView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)

            @discord.ui.button(label="List OSRS Account", style=discord.ButtonStyle.primary, custom_id="list_account")
            async def account_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                pass

            @discord.ui.button(label="List OSRS GP", style=discord.ButtonStyle.success, custom_id="list_gp")
            async def gp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                pass

        view = PersistentView()
        await ctx.send("Choose what you want to list:", view=view)
        await ctx.send("✅ Listing buttons have been set up!")

    # Rest of your ListingCog code...
    # (keeping the rest of the code the same)

def setup(bot):
    print("Adding ListingCog...")  # Debug print
    cog = ListingCog(bot)
    bot.add_command(cog.setup_listings)  # Explicitly add the command
    bot.add_cog(cog)
    print("ListingCog added successfully")  # Debug print