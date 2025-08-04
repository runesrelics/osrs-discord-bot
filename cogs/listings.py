import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import asyncio
import sqlite3
import json
import io
from datetime import datetime, timedelta
from .embed_generator import EmbedGenerator

# Store user selections temporarily
user_selections = {}

# Database setup
DB_PATH = "/app/data/listings.db"

def init_listings_db():
    """Initialize the listings database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            account_message_id INTEGER NOT NULL,
            image_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_bumped TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            account_image_data BLOB,
            showcase_images_data BLOB,
            listing_data TEXT,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    conn.commit()
    conn.close()

def store_listing(user_id, channel_id, account_message_id, image_message_id, 
                  account_image_bytes, showcase_images_bytes, listing_data):
    """Store a new listing in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Convert BytesIO objects to bytes if needed
    if hasattr(account_image_bytes, 'getvalue'):
        account_image_bytes = account_image_bytes.getvalue()
    
    if showcase_images_bytes and hasattr(showcase_images_bytes, 'getvalue'):
        showcase_images_bytes = showcase_images_bytes.getvalue()
    
    cursor.execute('''
        INSERT INTO listings 
        (user_id, channel_id, account_message_id, image_message_id, 
         account_image_data, showcase_images_data, listing_data, created_at, last_bumped, last_interaction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, channel_id, account_message_id, image_message_id,
          account_image_bytes, showcase_images_bytes, json.dumps(listing_data),
          datetime.now(), datetime.now(), datetime.now()))
    
    listing_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return listing_id

def get_listing(listing_id):
    """Get a listing by ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM listings WHERE id = ? AND is_active = TRUE
    ''', (listing_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'id': result[0],
            'user_id': result[1],
            'channel_id': result[2],
            'account_message_id': result[3],
            'image_message_id': result[4],
            'created_at': datetime.fromisoformat(result[5]),
            'last_bumped': datetime.fromisoformat(result[6]),
            'last_interaction': datetime.fromisoformat(result[7]),
            'account_image_data': result[8],
            'showcase_images_data': result[9],
            'listing_data': json.loads(result[10])
        }
    return None

def can_bump_listing(listing_id):
    """Check if a listing can be bumped (48-hour cooldown)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT last_bumped FROM listings WHERE id = ? AND is_active = TRUE
    ''', (listing_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        last_bumped = datetime.fromisoformat(result[0])
        return datetime.now() - last_bumped >= timedelta(hours=48)
    return False

def update_listing_interaction(listing_id):
    """Update the last interaction time for a listing"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE listings 
        SET last_bumped = ?, last_interaction = ?
        WHERE id = ?
    ''', (datetime.now(), datetime.now(), listing_id))
    
    conn.commit()
    conn.close()

def get_old_listings():
    """Get listings older than 10 days with no recent interactions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=10)
    
    cursor.execute('''
        SELECT id, user_id, channel_id, account_message_id, image_message_id
        FROM listings 
        WHERE is_active = TRUE 
        AND created_at < ? 
        AND last_interaction < ?
    ''', (cutoff_date, cutoff_date))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{'id': r[0], 'user_id': r[1], 'channel_id': r[2], 
             'account_message_id': r[3], 'image_message_id': r[4]} for r in results]

def delete_listing_from_db(listing_id):
    """Mark a listing as inactive in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE listings SET is_active = FALSE WHERE id = ?
    ''', (listing_id,))
    
    conn.commit()
    conn.close()

# Initialize database on module load
init_listings_db()

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
        await interaction.response.send_modal(AccountListingModal(self.account_type, self.channel_type, self.CHANNELS, user_selections[user_id]))

    @discord.ui.button(label="Unregistered", style=discord.ButtonStyle.secondary)
    async def unregistered_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        user_selections[user_id]['email_status'] = 'unregistered'
        await interaction.response.send_modal(AccountListingModal(self.account_type, self.channel_type, self.CHANNELS, user_selections[user_id]))

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
        try:
            await interaction.response.defer(ephemeral=True)
            
            trusted = any("trusted" in role.name.lower() for role in interaction.user.roles)
            target_channels = self.CHANNELS["trusted"] if trusted else self.CHANNELS["public"]
            target_channel_id = target_channels[self.channel_type]
            listing_channel = interaction.guild.get_channel(target_channel_id)
            
            if not listing_channel:
                await interaction.followup.send(f"❌ Error: Could not find the listing channel (ID: {target_channel_id}). Please contact an administrator.", ephemeral=True)
                return

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
                        
                        # Auto-process the listing after any image upload
                        await interaction.followup.send(f"📸 {len(msg.attachments)} image(s) uploaded! Total: {len(image_bytes_list)}/3. Processing your listing...", ephemeral=True)
                        break
                    else:
                        await interaction.followup.send("❌ Please upload an image.", ephemeral=True)
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
            try:
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
                
                # Store listing data for future editing/bumping
                listing_data = {
                    'account_type': self.account_type,
                    'channel_type': self.channel_type,
                    'user_selections': self.user_selections,
                    'details_left': self.details_left.value,
                    'details_right': self.details_right.value,
                    'price': self.price.value,
                    'payment_method': 'USD'
                }
                
                # Store in database
                listing_id = store_listing(
                    user_id=interaction.user.id,
                    channel_id=listing_channel.id,
                    account_message_id=account_msg.id,
                    image_message_id=listing_msg.id if image_template else None,
                    account_image_bytes=account_template,
                    showcase_images_bytes=image_template if image_template else None,
                    listing_data=listing_data
                )
                
                # Add the listing controls
                view = ListingView(
                    lister=interaction.user, 
                    listing_message=listing_msg, 
                    account_message=account_msg,
                    listing_id=listing_id
                )
                await listing_msg.edit(view=view)
                
                await interaction.followup.send("✅ Your listing has been posted!", ephemeral=True)
                
            except Exception as e:
                print(f"Error generating listing: {str(e)}")
                await interaction.followup.send(f"❌ Error generating listing: {str(e)}. Please try again or contact an administrator.", ephemeral=True)
                return
                
        except Exception as e:
            print(f"Error in on_submit: {str(e)}")
            await interaction.followup.send(f"❌ Something went wrong: {str(e)}. Please try again.", ephemeral=True)
            return

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
                # Create the account type selection view with all the buttons
                class AccountTypeSelectionView(discord.ui.View):
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

                view = AccountTypeSelectionView(self.CHANNELS)
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

    async def cleanup_old_listings(self):
        """Clean up listings older than 10 days with no interactions"""
        try:
            old_listings = get_old_listings()
            
            for listing in old_listings:
                try:
                    # Get the channel
                    channel = self.bot.get_channel(listing['channel_id'])
                    if not channel:
                        continue
                    
                    # Try to delete the Discord messages
                    try:
                        account_msg = await channel.fetch_message(listing['account_message_id'])
                        await account_msg.delete()
                    except:
                        pass
                    
                    if listing['image_message_id']:
                        try:
                            image_msg = await channel.fetch_message(listing['image_message_id'])
                            await image_msg.delete()
                        except:
                            pass
                    
                    # Delete from database
                    delete_listing_from_db(listing['id'])
                    
                    # Send DM to user
                    user = self.bot.get_user(listing['user_id'])
                    if user:
                        try:
                            await user.send(
                                f"Your listing in Runes & Relics has been deleted as it is older than 10 days without interactions. "
                                f"Please make a new listing if you're still selling."
                            )
                        except:
                            pass  # User might have DMs disabled
                    
                except Exception as e:
                    print(f"Error cleaning up listing {listing['id']}: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error in cleanup_old_listings: {str(e)}")

    @commands.command(name="cleanup_listings")
    @commands.has_permissions(administrator=True)
    async def cleanup_listings_command(self, ctx):
        """Manually trigger listing cleanup"""
        await ctx.send("🧹 Starting listing cleanup...")
        await self.cleanup_old_listings()
        await ctx.send("✅ Listing cleanup completed!")



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
    def __init__(self, lister: discord.User, listing_message: discord.Message, account_message: discord.Message, listing_id: int = None):
        super().__init__(timeout=None)
        self.lister = lister
        self.listing_message = listing_message
        self.account_message = account_message
        self.listing_id = listing_id

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

        bump_button = Button(
            emoji="⬆️",
            style=discord.ButtonStyle.primary,
            custom_id="bump_listing"
        )
        bump_button.callback = self.bump_listing
        self.add_item(bump_button)

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
            
        # Get the channels from the cog
        channels = {}
        cog = interaction.client.get_cog("Listings")
        if cog:
            channels = cog.CHANNELS
        
        await interaction.response.send_message(
            "⚠️ **Are you sure you want to edit this listing?**\n"
            "Your old listing will be deleted and replaced with a new one.",
            view=EditConfirmationView(self, channels),
            ephemeral=True
        )

    async def bump_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return
        
        if not self.listing_id:
            await interaction.response.send_message("❌ This listing cannot be bumped.", ephemeral=True)
            return
        
        # Check if listing can be bumped
        if not can_bump_listing(self.listing_id):
            await interaction.response.send_message("⏰ You can only bump your listing once every 48 hours.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the stored listing data
            listing = get_listing(self.listing_id)
            if not listing:
                await interaction.followup.send("❌ Listing not found.", ephemeral=True)
                return
            
            # Delete old messages
            try:
                await self.listing_message.delete()
                await self.account_message.delete()
            except:
                pass
            
            # Get the channel
            channel = interaction.guild.get_channel(listing['channel_id'])
            if not channel:
                await interaction.followup.send("❌ Channel not found.", ephemeral=True)
                return
            
            # Recreate the listing using stored data
            account_file = discord.File(io.BytesIO(listing['account_image_data']), filename="account_template.png")
            account_msg = await channel.send(file=account_file)
            
            image_msg = None
            if listing['showcase_images_data']:
                image_file = discord.File(io.BytesIO(listing['showcase_images_data']), filename="image_template.png")
                image_msg = await channel.send(file=image_file)
            
            # Update the listing in database
            update_listing_interaction(self.listing_id)
            
            # Create new view
            new_view = ListingView(
                lister=interaction.user,
                listing_message=image_msg if image_msg else account_msg,
                account_message=account_msg,
                listing_id=self.listing_id
            )
            
            # Add view to the image message (or account message if no images)
            target_msg = image_msg if image_msg else account_msg
            await target_msg.edit(view=new_view)
            
            await interaction.followup.send("✅ Your listing has been bumped!", ephemeral=True)
            
        except Exception as e:
            print(f"Error bumping listing: {str(e)}")
            await interaction.followup.send(f"❌ Error bumping listing: {str(e)}", ephemeral=True)

    async def delete_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return

        try:
            # Delete from database if we have a listing_id
            if self.listing_id:
                delete_listing_from_db(self.listing_id)
            
            # Delete both messages
            await self.listing_message.delete()
            await self.account_message.delete()
            await interaction.response.send_message("✅ Listing deleted.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Failed to delete listing.", ephemeral=True)

class EditConfirmationView(View):
    def __init__(self, listing_view, channels):
        super().__init__(timeout=60)
        self.listing_view = listing_view
        self.channels = channels

    @discord.ui.button(label="Yes, Edit Listing", style=discord.ButtonStyle.danger)
    async def confirm_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.listing_view.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return
        
        try:
            # Get the stored listing data to pre-fill the modal BEFORE deleting
            if self.listing_view.listing_id:
                try:
                    listing = get_listing(self.listing_view.listing_id)
                    print(f"Debug: Retrieved listing {self.listing_view.listing_id}: {listing is not None}")
                    
                    if listing and listing.get('listing_data'):
                        listing_data = listing['listing_data']
                        print(f"Debug: Listing data keys: {list(listing_data.keys())}")
                        
                        # Delete old messages
                        await self.listing_view.listing_message.delete()
                        await self.listing_view.account_message.delete()
                        
                        # Delete from database
                        delete_listing_from_db(self.listing_view.listing_id)
                        
                        # Pre-fill user_selections for the modal
                        user_id = interaction.user.id
                        if user_id not in user_selections:
                            user_selections[user_id] = {}
                        user_selections[user_id].update(listing_data.get('user_selections', {}))
                        
                        # Open the modal with pre-filled data
                        modal = AccountListingModal(
                            account_type=listing_data.get('account_type', 'Main'),
                            channel_type=listing_data.get('channel_type', 'main'),
                            channels=self.channels,
                            user_selections=listing_data.get('user_selections', {})
                        )
                        
                        # Pre-fill the text inputs
                        modal.details_left.default = listing_data.get('details_left', '')
                        modal.details_right.default = listing_data.get('details_right', '')
                        modal.price.default = listing_data.get('price', '')
                        
                        # Send the modal directly without deferring
                        await interaction.response.send_modal(modal)
                        return
                    else:
                        print(f"Debug: No listing data found for ID {self.listing_view.listing_id}")
                        await interaction.response.send_message("❌ Could not retrieve listing data for editing. The listing may have been deleted or corrupted.", ephemeral=True)
                        return
                        
                except Exception as e:
                    print(f"Debug: Error retrieving listing {self.listing_view.listing_id}: {str(e)}")
                    await interaction.response.send_message(f"❌ Error retrieving listing data: {str(e)}", ephemeral=True)
                    return
            
            # Fallback if no stored data
            await interaction.response.send_message("❌ Could not retrieve listing data for editing.", ephemeral=True)
            
        except Exception as e:
            print(f"Error editing listing: {str(e)}")
            await interaction.followup.send(f"❌ Error editing listing: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.listing_view.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return
        
        await interaction.response.send_message("❌ Edit cancelled.", ephemeral=True)

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