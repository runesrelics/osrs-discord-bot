import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import asyncio
from .embed_generator import EmbedGenerator

class AccountListingModal(Modal):
    def __init__(self, account_type: str, channel_type: str, channels: dict):
        super().__init__(title=f"List an OSRS {account_type} Account")
        self.account_type = account_type
        self.channel_type = channel_type
        self.CHANNELS = channels
        
        self.description = TextInput(
            label="Account Description",
            style=discord.TextStyle.paragraph,
            placeholder="Describe your account's stats, quests, achievements, etc.",
            max_length=500
        )
        
        self.price = TextInput(
            label="Price / Value",
            placeholder="Enter your asking price",
            max_length=50
        )
        
        self.payment = TextInput(
            label="Payment Methods",
            placeholder="List accepted payment methods",
            max_length=100
        )

        self.add_item(self.description)
        self.add_item(self.price)
        self.add_item(self.payment)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        trusted = any("trusted" in role.name.lower() for role in interaction.user.roles)
        target_channels = self.CHANNELS["trusted"] if trusted else self.CHANNELS["public"]
        target_channel_id = target_channels[self.channel_type]
        listing_channel = interaction.guild.get_channel(target_channel_id)

        await interaction.followup.send(
            "Please upload ONE showcase image for your listing (30 seconds).",
            ephemeral=True
        )

        def check(m):
            return (m.author == interaction.user and 
                   m.channel == interaction.channel and 
                   m.attachments)

        try:
            msg = await interaction.client.wait_for("message", timeout=30.0, check=check)
            if msg.attachments:
                showcase_image = await msg.attachments[0].read()
                
                # Generate the custom listing image
                embed_generator = EmbedGenerator()
                listing_image = await embed_generator.generate_listing_image(
                    self.account_type,
                    interaction.user,
                    self.description.value,
                    self.price.value,
                    self.payment.value,
                    showcase_image
                )

                # Send the listing as a plain image with buttons
                file = discord.File(listing_image, filename="listing.png")
                listing_msg = await listing_channel.send(file=file)
                
                # Add the listing controls
                view = ListingView(lister=interaction.user, listing_message=listing_msg)
                await listing_msg.edit(view=view)
                
                await interaction.followup.send("✅ Your listing has been posted!", ephemeral=True)
                
                # Clean up the showcase image message
                try:
                    await msg.delete()
                except:
                    pass
                    
            else:
                await interaction.followup.send("❌ No image was provided. Please try listing again.", ephemeral=True)
                
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ No image was provided in time. Please try listing again.", ephemeral=True)
            return

class ListingView(View):
    def __init__(self, lister: discord.User, listing_message: discord.Message):
        super().__init__(timeout=None)
        self.lister = lister
        self.listing_message = listing_message

        buy_button = Button(
            label="TRADE",
            style=discord.ButtonStyle.success,
            custom_id=f"buy_{lister.id}"
        )
        self.add_item(buy_button)

        edit_button = Button(
            emoji="✏️",
            style=discord.ButtonStyle.secondary,
            custom_id="edit_listing"
        )
        edit_button.callback = self.edit_listing
        self.add_item(edit_button)

        delete_button = Button(
            emoji="❌",
            style=discord.ButtonStyle.secondary,
            custom_id="delete_listing"
        )
        delete_button.callback = self.delete_listing
        self.add_item(delete_button)

    async def edit_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return
            
        embed = self.listing_message.embeds[0]
        await interaction.response.send_message("❌ Editing listings is temporarily disabled.", ephemeral=True)

    async def delete_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return

        try:
            await self.listing_message.delete()
            await interaction.response.send_message("✅ Listing deleted.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Failed to delete listing.", ephemeral=True)

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

    @commands.command(name="setup_listings")
    @commands.has_permissions(administrator=True)
    async def setup_listings(self, ctx):
        """Sets up the listing buttons in the create_trade channel"""
        if ctx.channel.id != self.CHANNELS["create_trade"]:
            await ctx.send("❌ Please run this command in the create_trade channel.")
            return

        view = discord.ui.View(timeout=None)  # Make the view persistent
        view.add_item(discord.ui.Button(label="List OSRS Account", custom_id="list_account", style=discord.ButtonStyle.primary))
        view.add_item(discord.ui.Button(label="List OSRS GP", custom_id="list_gp", style=discord.ButtonStyle.success))

        await ctx.send("Choose what you want to list:", view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            return

        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")

            if custom_id == "list_account":
                view = self.AccountTypeSelectView(self.CHANNELS)
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