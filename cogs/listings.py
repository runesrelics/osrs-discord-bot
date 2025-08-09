import discord
from discord.ext import commands
from config import CHANNELS
from views.listing_views import ListingView

class Listings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_listings(self, ctx):
        if ctx.channel.id != CHANNELS["create_trade"]:
            await ctx.send("❌ Please run this command in the create_trade channel.")
            return

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="List OSRS Account", custom_id="list_account"))
        view.add_item(discord.ui.Button(label="List OSRS GP", custom_id="list_gp"))

        await ctx.send("Choose what you want to list:", view=view)

async def setup(bot):
    await bot.add_cog(Listings(bot))