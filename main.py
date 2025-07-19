import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import io
from datetime import datetime

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
    "archive": 1395791949969231945,  # archive channel ID
    "vouch_post": 1383401756335149087  # vouch post channel ID
}

EMBED_COLOR = discord.Color.gold()
BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"

# In-memory vouch storage
# Structure: { user_id: {"total_stars": int, "count": int, "comments": [str]} }
vouch_data = {}

# --- TICKET ACTIONS ---

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
        await interaction.response.send_message("✅ You marked the trade as complete.", ephemeral=True)

        if len(self.completions) == 2:
            # Both users marked complete, start vouch process
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
        # Send separate star rating messages for each user
        user_list = list(self.users.values())
        self.vouch_view = VouchView(self, channel, self.message, user_list[0], user_list[1])
        star_view1 = StarRatingView(self.vouch_view, user_list[0])
        star_view2 = StarRatingView(self.vouch_view, user_list[1])
        await channel.send(f"{user_list[0].mention}, please select your star rating:", view=star_view1)
        await channel.send(f"{user_list[1].mention}, please select your star rating:", view=star_view2)

    async def archive_ticket(self, channel, listing_message):
        archive = channel.guild.get_channel(CHANNELS["archive"])
        if archive:
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
            await archive.send(content=f"📁 Archived ticket: {channel.name}", file=discord_file)

        try:
            await listing_message.delete()
        except Exception:
            pass

        await channel.delete()


# --- VOUCH VIEWS ---

class VouchView:
    def __init__(self, ticket_actions: TicketActions, channel: discord.TextChannel, listing_message, user1, user2):
        self.ticket_actions = ticket_actions
        self.channel = channel
        self.listing_message = listing_message
        self.users = {user1.id: user1, user2.id: user2}
        self.vouches = {}  # user_id -> {"stars": int, "comment": str}

    def submit_vouch(self, user_id, stars, comment):
        self.vouches[user_id] = {"stars": stars, "comment": comment}
        # Store global vouch data
        if user_id not in vouch_data:
            vouch_data[user_id] = {"total_stars": 0, "count": 0, "comments": []}
        vouch_data[user_id]["total_stars"] += stars
        vouch_data[user_id]["count"] += 1
        vouch_data[user_id]["comments"].append(comment)

    def all_vouches_submitted(self):
        return len(self.vouches) == 2

    async def finish_vouching(self):
        # Post vouches in vouch_post channel
        vouch_post_channel = self.channel.guild.get_channel(CHANNELS["vouch_post"])
        if not vouch_post_channel:
            await self.channel.send("❌ Vouch post channel not found. Cannot post vouch.")
            return

        user_list = list(self.users.values())

        embed = discord.Embed(title="🛡️ New Trade Vouch", color=EMBED_COLOR, timestamp=datetime.utcnow())
        embed.set_footer(text="Runes and Relics - Vouch System", icon_url=BRANDING_IMAGE)

        for uid, user in self.users.items():
            v = self.vouches.get(uid)
            stars = v["stars"] if v else 0
            comment = v["comment"] if v else "No comment"
            embed.add_field(
                name=f"{user.display_name} ({stars}⭐)",
                value=comment,
                inline=False,
            )

        await vouch_post_channel.send(embed=embed)
        await self.channel.send("✅ Both vouches received! Archiving ticket now.")
        await self.ticket_actions.archive_ticket(self.channel, self.listing_message)


class StarRatingView(View):
    def __init__(self, vouch_view: VouchView, user: discord.User):
        super().__init__(timeout=None)
        self.vouch_view = vouch_view
        self.user = user
        for i in range(1, 6):
            self.add_item(StarButton(i, self))

class StarButton(Button):
    def __init__(self, stars, star_view: StarRatingView):
        super().__init__(label=f"{stars} ⭐", style=discord.ButtonStyle.primary)
        self.stars = stars
        self.star_view = star_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.star_view.user.id:
            await interaction.response.send_message("This is not your star rating button.", ephemeral=True)
            return

        # Disable all buttons once clicked
        for child in self.star_view.children:
            child.disabled = True
        await interaction.message.edit(view=self.star_view)

        # Open comment modal
        user_to_vouch = next(u for uid, u in self.star_view.vouch_view.users.items() if uid != interaction.user.id)
        await interaction.response.send_modal(CommentModal(self.star_view.vouch_view, interaction.user, self.stars, user_to_vouch))


class CommentModal(Modal, title="Submit Your Vouch Comment"):
    def __init__(self, vouch_view: VouchView, user_submitting: discord.User, star_rating: int, user_to_vouch: discord.User):
        super().__init__()
        self.vouch_view = vouch_view
        self.user_submitting = user_submitting
        self.star_rating = star_rating
        self.user_to_vouch = user_to_vouch

        self.comment = TextInput(
            label="Comment",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=200,
            placeholder="Leave a comment (optional)"
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        comment_value = self.comment.value.strip() or "No comment"

        self.vouch_view.submit_vouch(
            user_id=self.user_submitting.id,
            stars=self.star_rating,
            comment=comment_value
        )

        await interaction.response.send_message("✅ Your vouch has been recorded!", ephemeral=True)

        if self.vouch_view.all_vouches_submitted():
            await self.vouch_view.finish_vouching()


# --- MODALS for Listings (no change) ---

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

        view = View()
        view.add_item(Button(label="🗡️ BUY", style=discord.ButtonStyle.success, custom_id=f"buy_{interaction.user.id}"))

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

        view = View()
        view.add_item(Button(label="💰 BUY", style=discord.ButtonStyle.success, custom_id=f"buy_{interaction.user.id}"))

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
            await interaction.response.send_message("❌ Invalid buyer or listing owner.", ephemeral=True)
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

        ticket_channel = await interaction.guild.create_text_channel(
            name=f"ticket-{buyer.name}",
            overwrites=overwrites,
            topic="Trade ticket between buyer and seller."
        )

        embed_copy = interaction.message.embeds[0]
        await ticket_channel.send(
            f"📥 New trade ticket between {buyer.mention} and {lister.mention}",
            embed=embed_copy,
            view=TicketActions(interaction.message, buyer, lister)
        )

        await interaction.response.send_message(f"📨 Ticket created: {ticket_channel.mention}", ephemeral=True)


# --- SLASH COMMANDS ---

@bot.tree.command(name="vouchleader", description="Show top 10 vouched users")
async def vouchleader(interaction: discord.Interaction):
    if not vouch_data:
        await interaction.response.send_message("No vouches recorded yet.", ephemeral=True)
        return

    # Sort users by average stars descending
    sorted_users = sorted(
        vouch_data.items(),
        key=lambda item: (item[1]["total_stars"] / item[1]["count"], item[1]["count"]),
        reverse=True
    )[:10]

    embed = discord.Embed(title="🌟 Vouch Leaderboard - Top 10", color=EMBED_COLOR)
    for user_id, data in sorted_users:
        user = interaction.guild.get_member(user_id)
        if user:
            avg_stars = data["total_stars"] / data["count"]
            embed.add_field(
                name=user.display_name,
                value=f"⭐ {avg_stars:.2f} from {data['count']} vouches",
                inline=False
            )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="vouchcount", description="Show your vouch stats")
async def vouchcount(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in vouch_data:
        await interaction.response.send_message("You have no vouches yet.", ephemeral=True)
        return

    data = vouch_data[user_id]
    avg_stars = data["total_stars"] / data["count"]
    embed = discord.Embed(
        title=f"🌟 Your Vouch Stats",
        description=f"⭐ Average Rating: {avg_stars:.2f}\n📝 Total Vouches: {data['count']}",
        color=EMBED_COLOR
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# --- SETUP COMMAND ---

@bot.command()
async def setup(ctx):
    if ctx.channel.id != CHANNELS["create_trade"]:
        return await ctx.send("Run this in the create-a-trade channel only.")

    view = View()
    view.add_item(Button(label="🗡️ List OSRS Account", style=discord.ButtonStyle.primary, custom_id="account_listing"))
    view.add_item(Button(label="💰 List OSRS GP", style=discord.ButtonStyle.primary, custom_id="gp_listing"))

    embed = discord.Embed(
        title="📜 Create a Trade Listing",
        description="Select one of the options below to list your account or OSRS GP.",
        color=EMBED_COLOR
    )
    embed.set_thumbnail(url=BRANDING_IMAGE)
    await ctx.send(embed=embed, view=view)


# --- ON READY ---

@bot.event
async def on_ready():
    print(f"Bot is live as {bot.user}.")
    try:
        await bot.tree.sync()
        print("Slash commands synced (2 commands).")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")


# --- RUN ---

TOKEN = os.getenv("RELLY_DISCORD")
bot.run(TOKEN)
