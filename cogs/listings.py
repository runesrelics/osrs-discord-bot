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
        
        # Account Type Questions
        self.account_type_question = TextInput(
            label="Account Type",
            placeholder="Legacy or Jagex?",
            max_length=10
        )
        
        self.ban_status = TextInput(
            label="Ban Status",
            placeholder="No Bans, Temp Ban, or Perm Ban?",
            max_length=20
        )
        
        self.email_status = TextInput(
            label="Email Status (Legacy only)",
            placeholder="Registered or Unregistered? (Leave empty for Jagex)",
            max_length=20,
            required=False
        )
        
        # Left Side Details (4 text inputs)
        self.detail1 = TextInput(
            label="Achievement/Item 1",
            placeholder="e.g., Full graceful",
            max_length=50
        )
        
        self.detail2 = TextInput(
            label="Achievement/Item 2", 
            placeholder="e.g., Fire cape",
            max_length=50
        )
        
        self.detail3 = TextInput(
            label="Achievement/Item 3",
            placeholder="e.g., Dragon defender",
            max_length=50
        )
        
        self.detail4 = TextInput(
            label="Achievement/Item 4",
            placeholder="e.g., MA2 cape",
            max_length=50
        )
        
        # Right Side Details (4 text inputs)
        self.detail5 = TextInput(
            label="Achievement/Item 5",
            placeholder="e.g., Quest cape",
            max_length=50
        )
        
        self.detail6 = TextInput(
            label="Achievement/Item 6",
            placeholder="e.g., 99 strength",
            max_length=50
        )
        
        self.detail7 = TextInput(
            label="Achievement/Item 7",
            placeholder="e.g., Barrows gloves",
            max_length=50
        )
        
        self.detail8 = TextInput(
            label="Achievement/Item 8",
            placeholder="e.g., Void set",
            max_length=50
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

        # Add all items to modal
        self.add_item(self.account_type_question)
        self.add_item(self.ban_status)
        self.add_item(self.email_status)
        self.add_item(self.detail1)
        self.add_item(self.detail2)
        self.add_item(self.detail3)
        self.add_item(self.detail4)
        self.add_item(self.detail5)
        self.add_item(self.detail6)
        self.add_item(self.detail7)
        self.add_item(self.detail8)
        self.add_item(self.price)
        self.add_item(self.payment)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        trusted = any("trusted" in role.name.lower() for role in interaction.user.roles)
        target_channels = self.CHANNELS["trusted"] if trusted else self.CHANNELS["public"]
        target_channel_id = target_channels[self.channel_type]
        listing_channel = interaction.guild.get_channel(target_channel_id)

        # Collect multiple images (up to 3)
        image_bytes_list = []
        
        await interaction.followup.send("📸 Please upload up to 3 images for your listing. Upload them one by one, or type 'done' when finished.", ephemeral=True)
        
        def check(m):
            return (m.author == interaction.user and 
                   m.channel == interaction.channel and 
                   (m.attachments or m.content.lower() == 'done'))

        try:
            while len(image_bytes_list) < 3:
                msg = await interaction.client.wait_for("message", timeout=60.0, check=check)
                
                if msg.content.lower() == 'done':
                    break
                
                if msg.attachments:
                    # Process all attachments in the message
                    for attachment in msg.attachments:
                        if len(image_bytes_list) >= 3:
                            break
                        image_bytes = await attachment.read()
                        image_bytes_list.append(image_bytes)
                    
                    # Clean up the message
                    try:
                        await msg.delete()
                    except:
                        pass
                    
                    if len(image_bytes_list) < 3:
                        await interaction.followup.send(f"📸 {len(msg.attachments)} image(s) uploaded! Total: {len(image_bytes_list)}/3. Upload more images or type 'done'.", ephemeral=True)
                    else:
                        await interaction.followup.send("📸 Maximum 3 images reached! Processing your listing...", ephemeral=True)
                        break
                else:
                    await interaction.followup.send("❌ Please upload an image or type 'done'.", ephemeral=True)
                    try:
                        await msg.delete()
                    except:
                        pass
                        
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ No images were provided in time. Please try listing again.", ephemeral=True)
            return

        # Generate account header based on user inputs
        account_type = self.account_type_question.value.lower().strip()
        ban_status = self.ban_status.value.lower().strip()
        email_status = self.email_status.value.lower().strip() if self.email_status.value else ""
        
        # Build header based on account type
        header_parts = []
        
        if account_type == "jagex":
            header_parts.append("JAGEX ACCOUNT")
        elif account_type == "legacy":
            header_parts.append("LEGACY")
            if email_status:
                if email_status == "registered":
                    header_parts.append("REGISTERED")
                elif email_status == "unregistered":
                    header_parts.append("UNREGISTERED")
        
        # Add ban status
        if ban_status == "no bans":
            header_parts.append("NO BANS")
        elif ban_status == "temp ban":
            header_parts.append("TEMP BAN")
        elif ban_status == "perm ban":
            header_parts.append("PERM BAN")
        
        account_header = " | ".join(header_parts)
        
        # Build details strings
        details_left = []
        details_right = []
        
        # Left side details (1-4)
        for detail in [self.detail1.value, self.detail2.value, self.detail3.value, self.detail4.value]:
            if detail.strip():
                details_left.append(detail.strip())
        
        # Right side details (5-8)
        for detail in [self.detail5.value, self.detail6.value, self.detail7.value, self.detail8.value]:
            if detail.strip():
                details_right.append(detail.strip())
        
        details_left_text = "\n".join(details_left)
        details_right_text = "\n".join(details_right)
        
        # Generate the account details template (no images)
        embed_generator = EmbedGenerator()
        account_template = await embed_generator.generate_listing_image(
            self.account_type,
            interaction.user,
            account_header,
            details_left_text,
            details_right_text,
            self.price.value,
            self.payment.value
        )

        # Generate the image template if images were provided
        image_template = None
        if image_bytes_list:
            try:
                image_template = await embed_generator.generate_image_template(image_bytes_list)
            except FileNotFoundError as e:
                print(f"Warning: Image template files not found. Skipping image generation. Error: {e}")
                # Continue without image template
                pass

        # Send both templates in one message
        listing_msg, account_msg = await embed_generator.send_listing(listing_channel, account_template, image_template)
        
        # Add the listing controls
        view = ListingView(lister=interaction.user, listing_message=listing_msg, account_message=account_msg)
        await listing_msg.edit(view=view)
        
        await interaction.followup.send("✅ Your listing has been posted!", ephemeral=True)

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

class ListingView(View):
    def __init__(self, lister: discord.User, listing_message: discord.Message, account_message: discord.Message):
        super().__init__(timeout=None)
        self.lister = lister
        self.listing_message = listing_message
        self.account_message = account_message

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
            # Delete both messages
            await self.listing_message.delete()
            await self.account_message.delete()
            await interaction.response.send_message("✅ Listing deleted.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Failed to delete listing.", ephemeral=True)

class GPTypeSelectView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user

    @discord.ui.button(label="BUYING", style=discord.ButtonStyle.success)
    async def buying(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Only you can select this.", ephemeral=True)
            return
        await interaction.response.send_message("GP listings coming soon!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="SELLING", style=discord.ButtonStyle.danger)
    async def selling(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Only you can select this.", ephemeral=True)
            return
        await interaction.response.send_message("GP listings coming soon!", ephemeral=True)
        self.stop()

async def setup(bot):
    print("Adding ListingCog...")  # Debug print
    cog = ListingCog(bot)
    await bot.add_cog(cog)
    print("ListingCog added successfully")  # Debug print