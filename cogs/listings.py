import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import asyncio
from .embed_generator import EmbedGenerator

# Store user selections temporarily
user_selections = {}

class AccountTypeSelectView(View):
    def __init__(self, account_type: str, channel_type: str, channels: dict):
        super().__init__(timeout=60)
        self.account_type = account_type
        self.channel_type = channel_type
        self.CHANNELS = channels

    @discord.ui.button(label="Legacy", style=discord.ButtonStyle.primary)
    async def legacy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in user_selections:
            user_selections[user_id] = {}
        user_selections[user_id]['account_type'] = 'legacy'
        await interaction.response.send_message("✅ Account Type: Legacy\n\n**Ban Status:**", view=BanStatusSelectView(self.account_type, self.channel_type, self.CHANNELS), ephemeral=True)

    @discord.ui.button(label="Jagex", style=discord.ButtonStyle.success)
    async def jagex_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in user_selections:
            user_selections[user_id] = {}
        user_selections[user_id]['account_type'] = 'jagex'
        await interaction.response.send_message("✅ Account Type: Jagex\n\n**Ban Status:**", view=BanStatusSelectView(self.account_type, self.channel_type, self.CHANNELS), ephemeral=True)

class BanStatusSelectView(View):
    def __init__(self, account_type: str, channel_type: str, channels: dict):
        super().__init__(timeout=60)
        self.account_type = account_type
        self.channel_type = channel_type
        self.CHANNELS = channels

    @discord.ui.button(label="No Bans", style=discord.ButtonStyle.success)
    async def no_bans_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        user_selections[user_id]['ban_status'] = 'no bans'
        
        # Check if this is a Legacy account to show email status
        if user_selections[user_id].get('account_type') == 'legacy':
            await interaction.response.send_message("✅ Ban Status: No Bans\n\n**Email Status:**", view=EmailStatusSelectView(self.account_type, self.channel_type, self.CHANNELS), ephemeral=True)
        else:
            # For Jagex accounts, proceed directly to modal
            await self.proceed_to_modal(interaction)

    @discord.ui.button(label="Temp Banned", style=discord.ButtonStyle.danger)
    async def temp_banned_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        user_selections[user_id]['ban_status'] = 'temp ban'
        
        # Check if this is a Legacy account to show email status
        if user_selections[user_id].get('account_type') == 'legacy':
            await interaction.response.send_message("✅ Ban Status: Temp Banned\n\n**Email Status:**", view=EmailStatusSelectView(self.account_type, self.channel_type, self.CHANNELS), ephemeral=True)
        else:
            # For Jagex accounts, proceed directly to modal
            await self.proceed_to_modal(interaction)

    async def proceed_to_modal(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        await interaction.response.send_modal(AccountListingModal(self.account_type, self.channel_type, self.CHANNELS, user_selections[user_id]))

class EmailStatusSelectView(View):
    def __init__(self, account_type: str, channel_type: str, channels: dict):
        super().__init__(timeout=60)
        self.account_type = account_type
        self.channel_type = channel_type
        self.CHANNELS = channels

    @discord.ui.button(label="Registered", style=discord.ButtonStyle.primary)
    async def registered_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        user_selections[user_id]['email_status'] = 'registered'
        await interaction.response.send_message("✅ Email Status: Registered\n\n**Opening listing modal...**", ephemeral=True)
        await interaction.followup.send_modal(AccountListingModal(self.account_type, self.channel_type, self.CHANNELS, user_selections[user_id]))

    @discord.ui.button(label="Unregistered", style=discord.ButtonStyle.secondary)
    async def unregistered_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        user_selections[user_id]['email_status'] = 'unregistered'
        await interaction.response.send_message("✅ Email Status: Unregistered\n\n**Opening listing modal...**", ephemeral=True)
        await interaction.followup.send_modal(AccountListingModal(self.account_type, self.channel_type, self.CHANNELS, user_selections[user_id]))

class AccountListingModal(Modal):
    def __init__(self, account_type: str, channel_type: str, channels: dict, user_selections: dict):
        super().__init__(title=f"List an OSRS {account_type} Account")
        self.account_type = account_type
        self.channel_type = channel_type
        self.CHANNELS = channels
        self.user_selections = user_selections
        
        # Left Side Details (1 text input with multiple lines)
        self.details_left = TextInput(
            label="Left Side Achievements/Items",
            placeholder="Enter 4 items, one per line:\ne.g., Full graceful\nFire cape\nDragon defender\nMA2 cape",
            style=discord.TextStyle.paragraph,
            max_length=200
        )
        
        # Right Side Details (1 text input with multiple lines)
        self.details_right = TextInput(
            label="Right Side Achievements/Items",
            placeholder="Enter 4 items, one per line:\ne.g., Quest cape\n99 strength\nBarrows gloves\nVoid set",
            style=discord.TextStyle.paragraph,
            max_length=200
        )
        
        self.price = TextInput(
            label="Price / Value",
            placeholder="Enter your asking price in USD",
            max_length=50
        )

        # Add all items to modal (3 total - much more manageable!)
        self.add_item(self.details_left)
        self.add_item(self.details_right)
        self.add_item(self.price)

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

        # Generate account header based on stored selections
        account_type = self.user_selections.get('account_type', '').lower().strip()
        ban_status = self.user_selections.get('ban_status', '').lower().strip()
        email_status = self.user_selections.get('email_status', '').lower().strip()
        
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
        
        account_header = " | ".join(header_parts)
        
        # Build details strings
        details_left = []
        details_right = []
        
        # Left side details (split by lines)
        if self.details_left.value:
            details_left = [line.strip() for line in self.details_left.value.split('\n') if line.strip()]
        
        # Right side details (split by lines)
        if self.details_right.value:
            details_right = [line.strip() for line in self.details_right.value.split('\n') if line.strip()]
        
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
            "USD"  # Default payment method
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
            await interaction.response.send_message("**Account Type:**", view=AccountTypeSelectView("Main", "main", self.CHANNELS), ephemeral=True)

        @discord.ui.button(label="PvP", style=discord.ButtonStyle.danger)
        async def pvp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("**Account Type:**", view=AccountTypeSelectView("PvP", "pvp", self.CHANNELS), ephemeral=True)

        @discord.ui.button(label="HCIM", style=discord.ButtonStyle.success)
        async def hcim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("**Account Type:**", view=AccountTypeSelectView("HCIM", "ironman", self.CHANNELS), ephemeral=True)

        @discord.ui.button(label="Iron", style=discord.ButtonStyle.secondary)
        async def iron_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("**Account Type:**", view=AccountTypeSelectView("Iron", "ironman", self.CHANNELS), ephemeral=True)

        @discord.ui.button(label="Special", style=discord.ButtonStyle.primary)
        async def special_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("**Account Type:**", view=AccountTypeSelectView("Special", "main", self.CHANNELS), ephemeral=True)

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