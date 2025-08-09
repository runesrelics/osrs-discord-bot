import discord
from discord.ext import commands
from discord import app_commands
from views.listing_views import AccountListingModal, GPTypeSelectView

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Logged in as {self.bot.user} (ID: {self.bot.user.id})")
        try:
            synced = await self.bot.tree.sync()
            print(f"Synced {len(synced)} commands.")
        except Exception as e:
            print(f"Error syncing commands: {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            return  # slash commands handled elsewhere

        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")

            if custom_id == "list_account":
                await interaction.response.send_modal(AccountListingModal())
                return

            elif custom_id == "list_gp":
                view = GPTypeSelectView(interaction.user)
                await interaction.response.send_message(
                    "Please select if you are **BUYING** or **SELLING** OSRS GP:",
                    view=view,
                    ephemeral=True
                )
                return

async def setup(bot):
    await bot.add_cog(Events(bot))