import discord
from discord.ui import View, Button, Modal, TextInput
from config import CHANNELS, EMBED_COLOR, BRANDING_IMAGE
from views.ticket_views import TicketActions

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
        buy_button.callback = self.buy_button_callback
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

    async def buy_button_callback(self, interaction: discord.Interaction):
        try:
            lister_id = int(interaction.data["custom_id"].split("_")[1])
        except (ValueError, KeyError, IndexError):
            await interaction.response.send_message("❌ Invalid listing.", ephemeral=True)
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

            await ticket_message.edit(view=TicketActions(ticket_message, interaction.message, buyer, lister))
            await interaction.followup.send(f"📨 Ticket created: {ticket_channel.mention}", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create ticket: `{e}`", ephemeral=True)

    async def edit_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return
            
        embed = self.listing_message.embeds[0]

        if "gp" in embed.title.lower():
            await interaction.response.send_modal(GPListingEditModal(self.listing_message, self.lister))
        elif "account" in embed.title.lower():
            await interaction.response.send_modal(AccountListingEditModal(self.listing_message, self.lister))
        else:
            await interaction.response.send_message("❌ Unknown listing type, cannot edit.", ephemeral=True)

    async def delete_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return

        view = DirectDeleteView(self.lister, self.listing_message)
        await interaction.response.send_message(
            "Are you sure you want to delete your listing?",
            view=view,
            ephemeral=True
        )

class DirectDeleteView(View):
    def __init__(self, lister: discord.User, listing_message: discord.Message):
        super().__init__(timeout=60)
        self.lister = lister
        self.listing_message = listing_message

    @discord.ui.button(label="🗑️ Delete Listing", style=discord.ButtonStyle.danger)
    async def delete_listing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("🚫 You are not the owner of this listing.", ephemeral=True, delete_after=3)
            return

        try:
            await self.listing_message.delete()
            await interaction.response.send_message("✅ Listing deleted.", ephemeral=True, delete_after=3)
        except discord.NotFound:
            await interaction.response.send_message("⚠️ Could not delete the listing message (already gone?).", ephemeral=True, delete_after=3)

class GPTypeSelectView(View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user

    @discord.ui.button(label="BUYING", style=discord.ButtonStyle.success)
    async def buying(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Only you can select this.", ephemeral=True)
            return
        await interaction.response.send_modal(GPListingModal("buying"))
        self.stop()

    @discord.ui.button(label="SELLING", style=discord.ButtonStyle.danger)
    async def selling(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Only you can select this.", ephemeral=True)
            return
        await interaction.response.send_modal(GPListingModal("selling"))
        self.stop()

class AccountListingModal(Modal, title="List an OSRS Account"):
    category = TextInput(label="Account Type (Main / PvP / Ironman)", required=True)
    description = TextInput(label="Describe the account", style=discord.TextStyle.paragraph)
    price = TextInput(label="Price / Value")

    async def on_submit(self, interaction: discord.Interaction):
        account_type = self.category.value.lower()
        trusted = any("trusted" in role.name.lower() for role in interaction.user.roles)

        target_channels = CHANNELS["trusted"] if trusted else CHANNELS["public"]

        target_channel_id = None
        if "main" in account_type:
            target_channel_id = target_channels["main"]
        elif "pvp" in account_type:
            target_channel_id = target_channels["pvp"]
        elif "iron" in account_type:
            target_channel_id = target_channels["ironman"]
        else:
            await interaction.response.send_message("❌ Invalid account type.", ephemeral=True)
            return

        listing_embed = discord.Embed(
            title=f"{account_type.title()} Account Listing",
            description=self.description.value,
            color=EMBED_COLOR
        )
        listing_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        listing_embed.set_thumbnail(url=BRANDING_IMAGE)
        listing_embed.add_field(name="Value", value=self.price.value)

        listing_channel = interaction.guild.get_channel(target_channel_id)
        create_trade_channel = interaction.guild.get_channel(CHANNELS["create_trade"])

        await interaction.response.send_message(
            "Please upload up to 5 images in this channel. When finished, type 'done'.",
            ephemeral=True
        )

        images = []
        def check(m):
            return m.channel == create_trade_channel and m.author == interaction.user

        while len(images) < 5:
            try:
                msg = await interaction.client.wait_for("message", timeout=120.0, check=check)
            except asyncio.TimeoutError:
                break

            if msg.content.lower() == "done":
                break

            if msg.attachments:
                images.extend(msg.attachments)
            else:
                await create_trade_channel.send(
                    f"{interaction.user.mention} Please upload images or type 'done' to finish.",
                    delete_after=10
                )

        files = []
        for img in images[:5]:
            try:
                files.append(await img.to_file())
            except:
                pass

        msg = await listing_channel.send(embed=listing_embed, view=None, files=files)
        view = ListingView(lister=interaction.user, listing_message=msg)
        await msg.edit(view=view)

        async for old_msg in create_trade_channel.history(limit=50):
            if old_msg.author == interaction.user:
                try:
                    await old_msg.delete()
                except:
                    pass

        await interaction.followup.send("✅ Your listing has been posted!", ephemeral=True)

class GPListingModal(Modal, title="List OSRS GP"):
    def __init__(self, choice):
        super().__init__()
        self.choice = choice
        self.amount = TextInput(label="Amount", placeholder="e.g. 500M", required=True)
        self.rate = TextInput(label="Rate", placeholder="e.g. 0.16usd", required=True)
        self.payment = TextInput(label="Accepted payment methods", placeholder="BTC, OS, PayPal...")

        self.add_item(self.amount)
        self.add_item(self.rate)
        self.add_item(self.payment)

    async def on_submit(self, interaction: discord.Interaction):
        trusted = any("trusted" in role.name.lower() for role in interaction.user.roles)
        target_channel_id = (CHANNELS["trusted"] if trusted else CHANNELS["public"])["gp"]

        color = discord.Color.green() if self.choice == "buying" else discord.Color.red()
        role_text = "**BUYER**" if self.choice == "buying" else "**SELLER**"

        listing_embed = discord.Embed(
            title="💰 OSRS GP Listing",
            description=(
                f"{role_text}\n\n"
                f"**Amount:** {self.amount.value}\n"
                f"**Payment Methods:** {self.payment.value}\n"
                f"**Rate:** {self.rate.value}"
            ),
            color=color
        )
        listing_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        listing_embed.set_thumbnail(url=BRANDING_IMAGE)

        listing_channel = interaction.guild.get_channel(target_channel_id)
        msg = await listing_channel.send(embed=listing_embed)

        view = ListingView(lister=interaction.user, listing_message=msg)
        await msg.edit(view=view)

        create_trade_channel = interaction.guild.get_channel(CHANNELS["create_trade"])
        async for old_msg in create_trade_channel.history(limit=50):
            if old_msg.author == interaction.user:
                try:
                    await old_msg.delete()
                except:
                    pass

        await interaction.response.send_message(
            "✅ Your GP listing has been posted!", ephemeral=True, delete_after=3
        )

class AccountListingEditModal(Modal, title="Edit Your Account Listing"):
    def __init__(self, message: discord.Message, lister: discord.User):
        super().__init__()
        self.message = message
        self.lister = lister

        self.description = TextInput(
            label="New Description",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.price = TextInput(
            label="New Price / Value",
            required=True
        )

        self.add_item(self.description)
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.message.embeds[0]

        new_fields = []
        for field in embed.fields:
            if field.name.lower() == "value":
                new_fields.append((field.name, self.price.value, field.inline))
            else:
                new_fields.append((field.name, field.value, field.inline))

        embed.clear_fields()

        for name, value, inline in new_fields:
            embed.add_field(name=name, value=value, inline=inline)

        embed.description = self.description.value

        await self.message.edit(embed=embed)
        await interaction.response.send_message("✅ Account listing updated!", ephemeral=True)

class GPListingEditModal(Modal, title="Edit Your GP Listing"):
    def __init__(self, message: discord.Message, lister: discord.User):
        super().__init__()
        self.message = message
        self.lister = lister

        self.amount = TextInput(label="Amount", placeholder="e.g. 500M", required=True)
        self.rate = TextInput(label="Rate", placeholder="e.g. 0.16usd", required=True)
        self.payment = TextInput(label="Accepted Payment Methods", required=True)

        self.add_item(self.amount)
        self.add_item(self.rate)
        self.add_item(self.payment)

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.message.embeds[0]

        role_text = "**BUYER**" if "BUYER" in embed.description else "**SELLER**"
        embed.description = (
            f"{role_text}\n\n"
            f"**Amount:** {self.amount.value}\n"
            f"**Payment Methods:** {self.payment.value}\n"
            f"**Rate:** {self.rate.value}"
        )

        await self.message.edit(embed=embed)
        await interaction.response.send_message("✅ GP listing updated!", ephemeral=True)