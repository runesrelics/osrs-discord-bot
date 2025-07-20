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
    def __init__(self, message, user1, user2):
        super().__init__(timeout=None)
        self.message = message
        self.users = {user1.id: user1, user2.id: user2}
        self.completions = set()
        self.vouch_view = None

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
        await self.archive_ticket(interaction.channel, self.message)

    async def start_vouching(self, channel):
        user_list = list(self.users.values())
        self.vouch_view = VouchView(self, channel, self.message, user_list[0], user_list[1])
        await cleanup_bot_messages(channel)
        await channel.send(f"{user_list[0].mention}, please rate your trade partner:", view=StarRatingView(self.vouch_view, user_list[0]))
        await channel.send(f"{user_list[1].mention}, please rate your trade partner:", view=StarRatingView(self.vouch_view, user_list[1]))

    async def archive_ticket(self, channel, listing_message):
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

class VouchView:
    def __init__(self, ticket_actions, channel, listing_message, user1, user2):
        self.ticket_actions = ticket_actions
        self.channel = channel
        self.listing_message = listing_message
        self.users = {str(user1.id): user1, str(user2.id): user2}
        self.vouches = {}

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
        await self.channel.send("✅ Both vouches received. Archiving ticket now.")
        await self.ticket_actions.archive_ticket(self.channel, self.listing_message)


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

        view = ListingView(lister=interaction.user)

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
            except:
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

        msg = await listing_channel.send(embed=listing_embed, view=view, files=files)

        async for old_msg in create_trade_channel.history(limit=50):
            if old_msg.author == interaction.user:
                try:
                    await old_msg.delete()
                except:
                    pass

        await interaction.followup.send("✅ Your listing has been posted!", ephemeral=True)

class GPListingModal(Modal, title="List OSRS GP"):
    amount = TextInput(label="Amount", placeholder="e.g. 500M", required=True)
    payment = TextInput(label="Accepted payment methods", placeholder="BTC, OS, PayPal...")

    async def on_submit(self, interaction: discord.Interaction):
        trusted = any("trusted" in role.name.lower() for role in interaction.user.roles)

        target_channel_id = (CHANNELS["trusted"] if trusted else CHANNELS["public"])["gp"]

        listing_embed = discord.Embed(
            title="💰 OSRS GP Listing",
            description=f"**Amount:** {self.amount.value}\n**Payment Methods:** {self.payment.value}",
            color=EMBED_COLOR
        )
        listing_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        listing_embed.set_thumbnail(url=BRANDING_IMAGE)

        view = ListingView(lister=interaction.user)

        listing_channel = interaction.guild.get_channel(target_channel_id)
        msg = await listing_channel.send(embed=listing_embed, view=view)

        create_trade_channel = interaction.guild.get_channel(CHANNELS["create_trade"])
        async for old_msg in create_trade_channel.history(limit=50):
            if old_msg.author == interaction.user:
                try:
                    await old_msg.delete()
                except:
                    pass

        await interaction.response.send_message("✅ Your GP listing has been posted!", ephemeral=True)

class ListingView(View):
    def __init__(self, lister: discord.User):
        super().__init__(timeout=None)
        self.lister = lister

        # ✅ BUY button with dynamic custom_id (includes lister ID)
        buy_button = Button(
            label="BUY",
            style=discord.ButtonStyle.success,
            custom_id=f"buy_{lister.id}"
        )
        buy_button.callback = self.buy_button_callback
        self.add_item(buy_button)

        # ✏️ EDIT button
        edit_button = Button(
            emoji="✏️",
            style=discord.ButtonStyle.secondary,
            custom_id="edit_listing"
        )
        edit_button.callback = self.edit_listing
        self.add_item(edit_button)

        # ❌ DELETE button
        delete_button = Button(
            emoji="❌",
            style=discord.ButtonStyle.secondary,
            custom_id="delete_listing"
        )
        delete_button.callback = self.delete_listing
        self.add_item(delete_button)

    # ✅ BUY button callback - only acknowledges interaction
    async def buy_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Ticket creation is handled in on_interaction via custom_id="buy_<lister_id>"

    # ✏️ EDIT button logic
    async def edit_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return
        await interaction.response.send_modal(EditListingModal(interaction.message, self.lister))

    # ❌ DELETE button logic
    async def delete_listing(self, interaction: discord.Interaction):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return
        await interaction.message.delete()
        await interaction.response.send_message("🗑️ Listing deleted.", ephemeral=True)

class EditListingModal(Modal, title="Edit Your Listing"):
    def __init__(self, message: discord.Message, lister: discord.User):
        super().__init__()
        self.message = message
        self.lister = lister

        self.description = TextInput(label="New Description", style=discord.TextStyle.paragraph, required=True)
        self.price = TextInput(label="New Price / Value", required=True)

        self.add_item(self.description)
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.message.embeds[0]
        embed.description = self.description.value

        # Update the "Value" field in the embed if it exists
        for i, field in enumerate(embed.fields):
            if field.name.lower() == "value":
                embed.set_field_at(i, name=field.name, value=self.price.value, inline=field.inline)
                break

        await self.message.edit(embed=embed)
        await interaction.response.send_message("✅ Listing updated!", ephemeral=True)



# --- INTERACTION HANDLER ---

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = interaction.data.get("custom_id", "")

    if custom_id == "account_listing":
        await interaction.response.send_modal(AccountListingModal())

    elif custom_id == "gp_listing":
        await interaction.response.send_modal(GPListingModal())

    elif custom_id.startswith("buy_"):
        try:
            lister_id = int(custom_id.split("_")[1])
        except ValueError:
            return

        buyer = interaction.user
        lister = interaction.guild.get_member(lister_id)

        if not lister or lister == buyer:
            await interaction.followup.send("❌ Invalid buyer or listing owner.", ephemeral=True)
            return

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            buyer: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            lister: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        for role_name in ["Moderator", "Admin"]:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        # Remove this line to avoid double defer:
        # await interaction.response.defer(ephemeral=True)

        ticket_channel = await interaction.guild.create_text_channel(
            name=f"ticket-{buyer.name}-and-{lister.name}",
            overwrites=overwrites,
            topic="Trade ticket between buyer and seller."
        )

        await interaction.followup.send(
            f"📨 Ticket created: {ticket_channel.mention}", ephemeral=True
        )

        embed_copy = interaction.message.embeds[0]
        await ticket_channel.send(
            f"📥 New trade ticket between {buyer.mention} and {lister.mention}",
            embed=embed_copy,
            view=TicketActions(interaction.message, buyer, lister)
        )




# --- SLASH COMMANDS ---

@bot.tree.command(name="vouchleader", description="Show top 10 vouched users")
async def vouchleader(interaction: discord.Interaction):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, total_stars, count FROM vouches')
        rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message("No vouches recorded yet.")
        return

    # Sort by average stars and count
    sorted_rows = sorted(rows, key=lambda x: (x[1] / x[2], x[2]), reverse=True)[:10]

    embed = discord.Embed(title="🏆 Runes & Relics Vouch Leaderboard", color=EMBED_COLOR)
    embed.set_image(url="https://i.postimg.cc/0jHw8mRV/glowww.png")
    embed.set_footer(text="Based on average rating and number of vouches")

    for user_id, total_stars, count in sorted_rows:
        user = interaction.guild.get_member(int(user_id))
        if user:
            avg_stars = total_stars / count if count > 0 else 0
            embed.add_field(
                name=user.display_name,
                value=f"⭐ {avg_stars:.2f} from {count} vouches",
                inline=False
            )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="vouchcheck", description="Check how many vouches you have.")
async def vouchcheck(interaction: discord.Interaction):
    user_id = str(interaction.user.id)  # Make sure user ID is a string
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT total_stars, count FROM vouches WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

    if not row:
        await interaction.response.send_message("📊 You have no recorded vouches yet.", ephemeral=True)
        return

    total_stars, count = row
    avg_stars = total_stars / count if count > 0 else 0
    await interaction.response.send_message(
        f"📊 You currently have **{count}** vouches with an average rating of **{avg_stars:.2f}⭐**.",
        ephemeral=True
    )



# --- READY EVENT ---

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    print("Slash commands synced.")


# --- RUN ---

TOKEN = os.getenv("RELLY_DISCORD")
bot.run(TOKEN)
