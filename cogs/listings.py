import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import asyncio
from .embed_generator import EmbedGenerator

class ListingCog(commands.Cog):
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

    @commands.hybrid_command(name="setup_listings")
    @commands.has_permissions(administrator=True)
    async def setup_listings(self, ctx):
        """Sets up the listing buttons in the create_trade channel"""
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

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            return

        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")

            if custom_id == "list_account":
                view = AccountTypeSelectView(self.CHANNELS)
                await interaction.response.send_message(
                    "Select the type of account you want to list:",
                    view=view,
                    ephemeral=True
                )
                return

            elif custom_id == "list_gp":
                view = GPTypeSelectView(interaction.user)
                await interaction.response.send_message(
                    "Please select if you are **BUYING** or **SELLING** OSRS GP:",
                    view=view,
                    ephemeral=True
                )
                return

            if custom_id.startswith("buy_"):
                await self.handle_buy_interaction(interaction)

    class AccountTypeSelectView(discord.ui.View):
        def __init__(self, channels):
            super().__init__(timeout=60)
            self.CHANNELS = channels

        @discord.ui.button(label="Main", style=discord.ButtonStyle.primary)
        async def main_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AccountListingModal("Main", "main", self.CHANNELS))

        @discord.ui.button(label="PvP", style=discord.ButtonStyle.danger)
        async def pvp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AccountListingModal("PvP", "pvp", self.CHANNELS))

        @discord.ui.button(label="HCIM", style=discord.ButtonStyle.success)
        async def hcim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AccountListingModal("HCIM", "ironman", self.CHANNELS))

        @discord.ui.button(label="Iron", style=discord.ButtonStyle.secondary)
        async def iron_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AccountListingModal("Iron", "ironman", self.CHANNELS))

        @discord.ui.button(label="Special", style=discord.ButtonStyle.primary)
        async def special_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AccountListingModal("Special", "main", self.CHANNELS))

    async def handle_buy_interaction(self, interaction: discord.Interaction):
        try:
            lister_id = int(interaction.data["custom_id"].split("_")[1])
        except ValueError:
            return

        buyer = interaction.user
        lister = interaction.guild.get_member(lister_id)

        if not lister or lister == buyer:
            await interaction.response.send_message("❌ Invalid buyer or listing owner.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            buyer: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            lister: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        for role_name in ["Moderator", "Admin"]:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=f"ticket-{buyer.name}-and-{lister.name}",
                overwrites=overwrites,
                topic="Trade ticket between buyer and seller."
            )

            if not interaction.message or not interaction.message.embeds:
                await interaction.followup.send("❌ Original listing message not found.", ephemeral=True)
                return

            embed_copy = interaction.message.embeds[0]

            ticket_message = await ticket_channel.send(
                f"📥 New trade ticket between {buyer.mention} and {lister.mention}",
                embed=embed_copy
            )

            from .tickets import TicketActions
            await ticket_message.edit(view=TicketActions(ticket_message, interaction.message, buyer, lister))

            await interaction.followup.send(f"📨 Ticket created: {ticket_channel.mention}", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create ticket: `{e}`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ListingCog(bot))