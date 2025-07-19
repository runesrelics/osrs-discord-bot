import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
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
    "archive": 1395791949969231945,  # your actual archive channel ID here
    "vouch_post": 1383401756335149087,  # channel to post vouches
}

# Emojis and color scheme
EMBED_COLOR = discord.Color.gold()
BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"

# In-memory vouch data storage (user_id: {stars: [...], comments: [...], count: int})
vouch_data = {}


# --- VOUCH MODAL ---

class VouchModal(Modal, title="Submit Your Vouch"):
    def __init__(self, vouch_view, user_submitting, user_to_vouch):
        super().__init__()
        self.vouch_view = vouch_view
        self.user_submitting = user_submitting
        self.user_to_vouch = user_to_vouch

        self.stars = Select(
            placeholder="Select star rating",
            options=[
                discord.SelectOption(label="1 ⭐", value="1"),
                discord.SelectOption(label="2 ⭐⭐", value="2"),
                discord.SelectOption(label="3 ⭐⭐⭐", value="3"),
                discord.SelectOption(label="4 ⭐⭐⭐⭐", value="4"),
                discord.SelectOption(label="5 ⭐⭐⭐⭐⭐", value="5"),
            ],
            min_values=1,
            max_values=1,
            custom_id="star_select"
        )
        self.add_item(self.stars)

        self.comment = TextInput(
            label="Comment",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=200,
            placeholder="Leave a comment (optional)"
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        star_value = int(self.stars.values[0])
        comment_value = self.comment.value.strip() or "No comment"

        # Save vouch in vouch_view's storage
        self.vouch_view.submit_vouch(
            user_id=self.user_submitting.id,
            stars=star_value,
            comment=comment_value
        )

        await interaction.response.send_message("✅ Your vouch has been recorded!", ephemeral=True)

        # Check if both submitted; if yes, finalize
        if self.vouch_view.all_vouches_submitted():
            await self.vouch_view.finish_vouching()


# --- VOUCH VIEW ---

class VouchView(View):
    def __init__(self, user1, user2, ticket_channel, listing_message):
        super().__init__(timeout=None)
        self.users = {user1.id: user1, user2.id: user2}
        self.ticket_channel = ticket_channel
        self.listing_message = listing_message

        # Store vouches keyed by user ID who submitted the vouch
        self.vouches = {}

    def submit_vouch(self, user_id, stars, comment):
        self.vouches[user_id] = {
            "stars": stars,
            "comment": comment
        }

    def all_vouches_submitted(self):
        # Both users must have submitted
        return all(uid in self.vouches for uid in self.users.keys())

    async def finish_vouching(self):
        # Post vouches summary in vouch channel
        vouch_channel = self.ticket_channel.guild.get_channel(CHANNELS["vouch_post"])
        if not vouch_channel:
            print("Vouch post channel not found!")
            return

        embed = discord.Embed(
            title=f"Vouches for trade in #{self.ticket_channel.name}",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )

        for submitter_id, vouch in self.vouches.items():
            submitter = self.users[submitter_id]
            # The user to whom the vouch is directed is the *other* user in the trade
            vouched_user = next(user for uid, user in self.users.items() if uid != submitter_id)

            embed.add_field(
                name=f"From {submitter.display_name} to {vouched_user.display_name}",
                value=f"Stars: {'⭐' * vouch['stars']}\nComment: {vouch['comment']}",
                inline=False
            )

            # Update global vouch data for the vouched user
            uid = vouched_user.id
            if uid not in vouch_data:
                vouch_data[uid] = {"stars": [], "comments": [], "count": 0}
            vouch_data[uid]["stars"].append(vouch['stars'])
            vouch_data[uid]["comments"].append(vouch['comment'])
            vouch_data[uid]["count"] += 1

        await vouch_channel.send(embed=embed)

        # Archive the ticket channel and delete listing message as before
        await TicketActions.archive_ticket_static(self.ticket_channel, self.listing_message)


# --- UPDATED TicketActions VIEW ---

class TicketActions(View):
    def __init__(self, listing_message):
        super().__init__(timeout=None)
        self.listing_message = listing_message
        self.completions = set()
        self.vouch_view = None

    @discord.ui.button(label="✅ Mark as Complete", style=discord.ButtonStyle.success)
    async def complete(self, interaction: discord.Interaction, button: Button):
        self.completions.add(interaction.user.id)

        # Only two users allowed in ticket (buyer + seller), get them
        users_in_channel = [m for m in interaction.channel.members if not m.bot]
        if len(users_in_channel) != 2:
            await interaction.response.send_message("Error: Ticket must have exactly 2 users.", ephemeral=True)
            return

        if len(self.completions) >= 2:
            # Disable complete and cancel buttons
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

            # Prompt the two users in channel to submit vouch via modal
            user1, user2 = users_in_channel
            await interaction.channel.send(
                f"{user1.mention} and {user2.mention}, both marked complete! Please submit your vouch using the form below."
            )

            # Create and send VouchView message in channel with buttons to open modal
            self.vouch_view = VouchView(user1, user2, interaction.channel, self.listing_message)

            # Send buttons for each user to open the modal:
            class VouchButton(Button):
                def __init__(self, vouch_view, user):
                    super().__init__(label=f"Submit Vouch ({user.display_name})", style=discord.ButtonStyle.primary)
                    self.vouch_view = vouch_view
                    self.user = user

                async def callback(self, i: discord.Interaction):
                    if i.user.id != self.user.id:
                        await i.response.send_message("This button is not for you.", ephemeral=True)
                        return
                    await i.response.send_modal(VouchModal(self.vouch_view, self.user, [u for u in self.vouch_view.users.values() if u != self.user][0]))

            vouch_buttons_view = View()
            vouch_buttons_view.add_item(VouchButton(self.vouch_view, user1))
            vouch_buttons_view.add_item(VouchButton(self.vouch_view, user2))

            await interaction.channel.send("Please submit your vouch by clicking your button below:", view=vouch_buttons_view)
            await interaction.response.send_message("Both completions received! Please submit your vouch.", ephemeral=True)
        else:
            await interaction.response.send_message("Waiting for the other party to confirm completion.", ephemeral=True)

    @discord.ui.button(label="❌ Cancel Trade", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.send("❌ Trade has been cancelled.")
        await self.archive_ticket(interaction.channel, self.listing_message)

    @staticmethod
    async def archive_ticket_static(channel, listing_message):
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

    async def archive_ticket(self, channel, listing_message):
        await self.archive_ticket_static(channel, listing_message)


# --- MODALS AND LISTINGS (Your existing modals unchanged) ---


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

        # Prompt user for images
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
    if not interaction.type == discord.InteractionType.component:
        return

    custom_id = interaction.data["custom_id"]

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
            view=TicketActions(interaction.message)
        )

        await interaction.response.send_message(f"📨 Ticket created: {ticket_channel.mention}", ephemeral=True)


# --- VOUCH LEADERBOARD AND COUNT SLASH COMMANDS ---

@bot.tree.command(name="vouchleader", description="Show the top 10 vouched users")
async def vouchleader(interaction: discord.Interaction):
    if not vouch_data:
        await interaction.response.send_message("No vouch data available yet.", ephemeral=True)
        return

    # Sort users by count desc
    top_users = sorted(vouch_data.items(), key=lambda x: x[1]["count"], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 Vouch Leaderboard - Top 10",
        color=EMBED_COLOR,
        timestamp=datetime.utcnow()
    )

    for i, (user_id, data) in enumerate(top_users, 1):
        user = interaction.guild.get_member(user_id)
        if not user:
            continue
        avg_stars = sum(data["stars"]) / len(data["stars"]) if data["stars"] else 0
        embed.add_field(
            name=f"{i}. {user.display_name}",
            value=f"Vouches: {data['count']} | Avg. Stars: {avg_stars:.2f} ⭐",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="vouchcount", description="Check your personal vouch count")
async def vouchcount(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid not in vouch_data:
        await interaction.response.send_message("You have no vouches yet.", ephemeral=True)
        return

    data = vouch_data[uid]
    avg_stars = sum(data["stars"]) / len(data["stars"]) if data["stars"] else 0
    await interaction.response.send_message(
        f"You have {data['count']} vouches with an average rating of {avg_stars:.2f} ⭐.",
        ephemeral=True
    )


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
        synced = await bot.tree.sync()
        print(f"Slash commands synced ({len(synced)} commands).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")


# --- RUN BOT ---

TOKEN = os.getenv("RELLY_DISCORD")
bot.run(TOKEN)
