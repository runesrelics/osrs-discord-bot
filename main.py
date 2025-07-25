import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import io
from datetime import datetime
import sqlite3
import json

DB_PATH = "/app/data/vouches.db"

def get_vouch_data(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT total_stars, count, comments FROM vouches WHERE user_id = ?', (user_id,))
        return cursor.fetchone()

def update_vouch(user_id, stars, comment):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        row = get_vouch_data(user_id)

        if row:
            total_stars, count, comments_json = row
            comments_list = json.loads(comments_json) if comments_json else []
            total_stars += stars
            count += 1
            comments_list.append(comment)
            comments_json = json.dumps(comments_list)
            cursor.execute('UPDATE vouches SET total_stars=?, count=?, comments=? WHERE user_id=?',
                           (total_stars, count, comments_json, user_id))
        else:
            comments_json = json.dumps([comment])
            cursor.execute('INSERT INTO vouches (user_id, total_stars, count, comments) VALUES (?, ?, ?, ?)',
                           (user_id, stars, 1, comments_json))
        conn.commit()


with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vouches (
        user_id TEXT PRIMARY KEY,
        total_stars INTEGER NOT NULL,
        count INTEGER NOT NULL,
        comments TEXT
    )
    ''')
    conn.commit()




intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Trusted/Public channel mappings
CHANNELS = {
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

EMBED_COLOR = discord.Color.gold()
BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"

# Helper to cleanup messages from the bot
async def cleanup_bot_messages(channel, limit=100):
    async for msg in channel.history(limit=limit):
        if msg.author == bot.user:
            try:
                await msg.delete()
            except discord.Forbidden:
                pass

class TicketActions(View):
    def __init__(self, ticket_message, listing_message, user1, user2):
        super().__init__(timeout=None)
        self.ticket_message = ticket_message
        self.listing_message = listing_message
        self.users = {user1.id: user1, user2.id: user2}
        self.completions = set()
        self.vouch_view = None
        self.lister = user2

    @discord.ui.button(label="✅ Mark as Complete", style=discord.ButtonStyle.success)
    async def complete(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in self.users:
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return

        if interaction.user.id in self.completions:
            await interaction.response.send_message("You have already marked as complete.", ephemeral=True)
            return

        self.completions.add(interaction.user.id)
        await interaction.response.send_message("✅ You marked the trade as complete. Waiting for other user to mark as complete", ephemeral=True)

        if len(self.completions) == 2:
            await interaction.channel.send("✅ Both parties have marked the trade as complete.")
            await self.start_vouching(interaction.channel)

    @discord.ui.button(label="❌ Cancel Trade", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in self.users:
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        await interaction.channel.send("❌ Trade has been cancelled.")
        await self.archive_ticket(interaction.channel, self.listing_message)

    async def start_vouching(self, channel):
        user_list = list(self.users.values())
        self.vouch_view = VouchView(self, channel, self.listing_message, user_list[0], user_list[1], self.lister)
        await cleanup_bot_messages(channel)
        view1 = StarRatingView(self.vouch_view, user_list[0])
        view2 = StarRatingView(self.vouch_view, user_list[1])
        
        await channel.send(f"{user_list[0].mention}, please rate your trade partner:", view=view1)
        await channel.send(f"{user_list[1].mention}, please rate your trade partner:", view=view2)


    async def archive_ticket(self, channel, listing_message=None):
        archive = channel.guild.get_channel(CHANNELS["archive"])
        transcript_lines = []
        async for msg in channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = msg.author.display_name
            content = msg.content or ""
            transcript_lines.append(f"[{timestamp}] {author}: {content}")
            for att in msg.attachments:
                transcript_lines.append(f"[{timestamp}] {author} sent an attachment: {att.url}")

        transcript_text = "\n".join(transcript_lines)
        transcript_file = io.StringIO(transcript_text)
        discord_file = discord.File(fp=transcript_file, filename=f"ticket-{channel.name}-archive.txt")

        if archive:
            await archive.send(content=f"📁 Archived ticket: {channel.name}", file=discord_file)

        for user in self.users.values():
            try:
                transcript_file.seek(0)
                await user.send(content=f"📄 Transcript from your completed trade in `{channel.name}`.", file=discord_file)
            except discord.Forbidden:
                await channel.send(f"⚠️ Could not DM transcript to {user.mention}.")

        try:
            await listing_message.delete()
        except:
            pass

        await channel.delete()

class GPTypeSelectView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user
        self.choice = None

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
        self.choice = "selling"
        await interaction.response.send_modal(GPListingModal("selling"))
        self.stop()



class ListingRemoveView(View):
    def __init__(self, lister, channel, listing_message, ticket_actions):
        super().__init__(timeout=60)
        self.lister = lister
        self.channel = channel
        self.listing_message = listing_message
        self.ticket_actions = ticket_actions
        self.decision = None

    @discord.ui.button(label="🗑️ Yes, remove listing", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("🚫 Only the listing owner can use this.", ephemeral=True, delete_after=3)
            return

        await interaction.response.send_message("🛑Listing will be removed and the ticket archived.", ephemeral=True)
        self.decision = True
        self.stop()

    @discord.ui.button(label="❌ No, keep listing", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("🚫 Only the listing owner can use this.", ephemeral=True, delete_after=3)
            return

        await interaction.response.send_message("✅ Listing will be kept. Archiving the ticket.", ephemeral=True)
        self.decision = False
        self.stop()

class DirectDeleteView(View):
    def __init__(self, lister, listing_message):
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




class VouchView:
    def __init__(self, ticket_actions, channel, listing_message, user1, user2, lister):
        self.ticket_actions = ticket_actions
        self.channel = channel
        self.listing_message = listing_message
        self.users = {str(user1.id): user1, str(user2.id): user2}
        self.vouches = {}
        self.lister = lister

    def submit_vouch(self, user_id, stars, comment):
        user_id_str = str(user_id)
        self.vouches[user_id_str] = {"stars": stars, "comment": comment}
        update_vouch(user_id_str, stars, comment)

    def all_vouches_submitted(self):
        return len(self.vouches) == 2

    async def finish_vouching(self):
        vouch_post_channel = self.channel.guild.get_channel(CHANNELS["vouch_post"])
        if not vouch_post_channel:
            await self.channel.send("❌ Cannot find vouch post channel.")
            return

        embed = discord.Embed(title="🛡️ New Trade Vouch", color=EMBED_COLOR, timestamp=datetime.utcnow())
        embed.set_footer(text="Runes and Relics - Vouch System", icon_url=BRANDING_IMAGE)

        for uid, user in self.users.items():
            v = self.vouches.get(uid, {})
            embed.add_field(name=f"{user.display_name} ({v.get('stars', 0)}⭐)", value=v.get("comment", "No comment"), inline=False)

        await vouch_post_channel.send(embed=embed)
        await self.channel.send("✅ Both vouches received.")

        if self.listing_message and self.lister:
            view = ListingRemoveView(
                lister=self.lister,
                channel=self.channel,
                listing_message=self.listing_message,
                ticket_actions=self.ticket_actions
            )
            await self.channel.send(
                f"{self.lister.mention}, would you like to remove your original listing?",
                view=view
            )
            await view.wait()

            # Always archive the ticket
            await self.ticket_actions.archive_ticket(self.channel, None)

            # Delete listing only if confirmed
            if view.decision is True:
                try:
                    await self.listing_message.delete()
                    await self.channel.send("✅ Listing deleted.")
                except discord.NotFound:
                    await self.channel.send("⚠️ Listing message was already deleted or not found.")
            else:
                await self.channel.send("🛑 Listing kept by user.")
        else:
            # No listing to remove, just archive the ticket
            await self.ticket_actions.archive_ticket(self.channel, None)




class StarRatingView(View):
    def __init__(self, vouch_view, user):
        super().__init__(timeout=None)
        self.vouch_view = vouch_view
        self.user = user
        for i in range(1, 6):
            self.add_item(StarButton(i, self))

class StarButton(Button):
    def __init__(self, stars, star_view):
        super().__init__(label=f"{stars} ⭐", style=discord.ButtonStyle.primary)
        self.stars = stars
        self.star_view = star_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.star_view.user.id:
            await interaction.response.send_message("This is not your star rating.", ephemeral=True)
            return

        for child in self.star_view.children:
            child.disabled = True
        await interaction.message.edit(view=self.star_view)

        user_to_vouch = next(u for uid, u in self.star_view.vouch_view.users.items() if uid != str(interaction.user.id))
        await interaction.response.send_modal(CommentModal(self.star_view.vouch_view, interaction.user, self.stars, user_to_vouch))

class CommentModal(Modal, title="Submit Your Vouch Comment"):
    def __init__(self, vouch_view, user_submitting, star_rating, user_to_vouch):
        super().__init__()
        self.vouch_view = vouch_view
        self.user_submitting = user_submitting
        self.star_rating = star_rating
        self.user_to_vouch = user_to_vouch

        self.comment = TextInput(label="Comment", style=discord.TextStyle.paragraph, required=False, max_length=200, placeholder="Leave a comment (optional)")
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        comment_value = self.comment.value.strip() or "No comment"
        self.vouch_view.submit_vouch(self.user_submitting.id, self.star_rating, comment_value)
        await interaction.response.send_message("✅ Your vouch has been recorded! Waiting for other party to vouch.", ephemeral=True)
        if self.vouch_view.all_vouches_submitted():
            await self.vouch_view.finish_vouching()

# --- MODALS for Listings ---

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
                msg = await bot.wait_for("message", timeout=120.0, check=check)
            except asyncio.TimeoutError:
                break

            if msg.content.lower() == "done":
                break

            if msg.attachments:
                images.extend(msg.attachments)
            else:
                await create_trade_channel.send(f"{interaction.user.mention} Please upload images or type 'done' to finish.", delete_after=10)

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
    def __init__(self, choice):  # choice is 'buying' or 'selling'
        super().__init__()
        self.choice = choice
        self.amount = TextInput(label="Amount", placeholder="e.g. 500M", required=True)
        self.rate = TextInput(label="What rate?", placeholder="e.g. 0.16usd", required=True)
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

        # Clean up user's messages in the create_trade channel
        create_trade_channel = interaction.guild.get_channel(CHANNELS["create_trade"])
        async for old_msg in create_trade_channel.history(limit=50):
            if old_msg.author == interaction.user:
                try:
                    await old_msg.delete()
                except:
                    pass

        # Try to delete the ephemeral message that triggered this modal
        try:
            await interaction.message.delete()
        except Exception as e:
            print(f"Could not delete ephemeral message: {e}")

        # Send confirmation and auto-delete it after 3 seconds
        await interaction.response.send_message(
            "✅ Your GP listing has been posted!", ephemeral=True, delete_after=3
        )




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

    async def buy_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

    async def edit_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return
            
        embed = self.listing_message.embeds[0]

    # Check embed title to decide which modal to show
        if "gp" in embed.title.lower():
        # GP listing modal
            await interaction.response.send_modal(GPListingEditModal(self.listing_message, self.lister))
        elif "account" in embed.title.lower():
        # Account listing modal
            await interaction.response.send_modal(AccountListingEditModal(self.listing_message, self.lister))
        else:
        # Fallback to a generic modal or an error message
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

        # Rebuild fields, replacing the "Value" field with the new price
        new_fields = []
        for field in embed.fields:
            if field.name.lower() == "value":
                new_fields.append((field.name, self.price.value, field.inline))
            else:
                new_fields.append((field.name, field.value, field.inline))

        embed.clear_fields()

        for name, value, inline in new_fields:
            embed.add_field(name=name, value=value, inline=inline)

        # Update the description with new value
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

        # Update the embed description to reflect new GP info
        role_text = "**BUYER**" if "BUYER" in embed.description else "**SELLER**"
        embed.description = (
            f"{role_text}\n\n"
            f"**Amount:** {self.amount.value}\n"
            f"**Payment Methods:** {self.payment.value}\n"
            f"**Rate:** {self.rate.value}"
        )

        await self.message.edit(embed=embed)
        await interaction.response.send_message("✅ GP listing updated!", ephemeral=True)



# --- INTERACTION HANDLER ---

@bot.event
async def on_interaction(interaction: discord.Interaction):
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

        if custom_id.startswith("buy_"):
            try:
                lister_id = int(custom_id.split("_")[1])
            except ValueError:
                # Cannot parse lister id, ignore interaction
                return


            buyer = interaction.user
            lister = interaction.guild.get_member(lister_id)

            if not lister or lister == buyer:
                # Respond ONCE with error, no defer here
                await interaction.response.send_message("❌ Invalid buyer or listing owner.", ephemeral=True)
                return

            # Defer interaction to get more time for processing
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
                    # Use followup.send because initial interaction is deferred
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


# --- SLASH COMMANDS ---

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_listings(ctx):
    if ctx.channel.id != CHANNELS["create_trade"]:
        await ctx.send("❌ Please run this command in the create_trade channel.")
        return

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="List OSRS Account", custom_id="list_account"))
    view.add_item(discord.ui.Button(label="List OSRS GP", custom_id="list_gp"))

    await ctx.send("Choose what you want to list:", view=view)


@bot.tree.command(name="vouchleader", description="Show top 10 vouched users")
async def vouchleader(interaction: discord.Interaction):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, total_stars, count FROM vouches WHERE count > 0')
        rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message("No vouches recorded yet.")
        return

    # Sort by average stars (total_stars/count) descending, then count descending
    rows.sort(key=lambda r: (r[1]/r[2], r[2]), reverse=True)
    top10 = rows[:10]

    embed = discord.Embed(title="🏆 Runes & Relics Vouch Leaderboard", color=EMBED_COLOR)
    embed.set_image(url="https://i.postimg.cc/0jHw8mRV/glowww.png")
    embed.set_footer(text="Based on average rating and number of vouches")

    for user_id, total_stars, count in top10:
        member = interaction.guild.get_member(int(user_id))
        if member:
            avg = total_stars / count
            embed.add_field(name=member.display_name, value=f"⭐ {avg:.2f} from {count} vouches", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouchcheck", description="Check how many vouches you have.")
async def vouchcheck(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT total_stars, count FROM vouches WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

    if not row:
        await interaction.response.send_message("You have no recorded vouches yet.", ephemeral=True)
        return

    total_stars, count = row
    avg = total_stars / count if count > 0 else 0
    await interaction.response.send_message(
        f"📊 You have {count} vouches with an average rating of {avg:.2f}⭐.",
        ephemeral=True
    )


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

TOKEN = os.getenv("RELLY_DISCORD")
bot.run(TOKEN)
