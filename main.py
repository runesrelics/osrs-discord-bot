import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
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
    "vouch_post": 1383401756335149087  # channel to post vouched info
}

# Emojis and color scheme
EMBED_COLOR = discord.Color.gold()
BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"

# Store vouches per user ID: {user_id: {"stars": [int,...], "comments": [str,...], "count": int}}
vouch_data = {}

# --- VIEWS ---


class VouchModal(Modal):
    def __init__(self, user_to_vouch, ticket_channel, interaction_user):
        super().__init__(title=f"Leave a Vouch for {user_to_vouch.display_name}")
        self.user_to_vouch = user_to_vouch
        self.ticket_channel = ticket_channel
        self.interaction_user = interaction_user

        self.star_input = TextInput(
            label="Stars (1-5)",
            placeholder="Enter a star rating between 1 and 5",
            required=True,
            max_length=1,
            min_length=1
        )
        self.comment_input = TextInput(
            label="Comment",
            style=discord.TextStyle.paragraph,
            placeholder="Leave an optional comment (max 200 characters)",
            required=False,
            max_length=200
        )

        self.add_item(self.star_input)
        self.add_item(self.comment_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate stars input
        try:
            stars = int(self.star_input.value)
            if stars < 1 or stars > 5:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid stars rating. Please enter a number between 1 and 5.", ephemeral=True)
            return

        # Save vouch data
        user_id = self.user_to_vouch.id
        if user_id not in vouch_data:
            vouch_data[user_id] = {"stars": [], "comments": [], "count": 0}

        vouch_data[user_id]["stars"].append(stars)
        vouch_data[user_id]["comments"].append(self.comment_input.value.strip() or "No comment")
        vouch_data[user_id]["count"] += 1

        # Notify ticket channel that this user submitted vouch
        await self.ticket_channel.send(f"✅ {interaction.user.mention} submitted their vouch for {self.user_to_vouch.mention}.")

        # Mark this user's vouch as done in ticket view
        ticket_view: TicketActions = self.ticket_channel.current_view
        if ticket_view is None:
            # If for some reason current_view is None, store vouch completion manually on the view instance
            ticket_view = getattr(self.ticket_channel, "ticket_actions_view", None)

        if ticket_view:
            ticket_view.vouch_completions.add(interaction.user.id)
            # If both completed, archive ticket and post vouch info
            if len(ticket_view.vouch_completions) >= 2:
                await ticket_view.finish_vouching()

        await interaction.response.send_message("✅ Vouch submitted! Thank you.", ephemeral=True)


class TicketActions(View):
    def __init__(self, listing_message):
        super().__init__(timeout=None)
        self.listing_message = listing_message
        self.completions = set()
        self.vouch_completions = set()
        self.vouch_phase = False
        # Save self to channel so modals can access it later
        self._channel_view_set = False

    async def on_timeout(self):
        # Optional: handle timeout, maybe archive ticket
        pass

    @discord.ui.button(label="✅ Mark as Complete", style=discord.ButtonStyle.success)
    async def complete(self, interaction: discord.Interaction, button: Button):
        if self.vouch_phase:
            await interaction.response.send_message("Please submit your vouch using the prompt.", ephemeral=True)
            return

        self.completions.add(interaction.user.id)
        if len(self.completions) >= 2:
            # Start vouch phase instead of archiving immediately
            self.vouch_phase = True
            await interaction.channel.send(
                "✅ Both parties marked complete! Now please submit your vouch (1-5 stars + comment) using the prompt below."
            )
            # Prompt both users for vouch modal
            overwrites = interaction.channel.overwrites
            users = [member for member in interaction.channel.members if not member.bot]

            for user in users:
                try:
                    await user.send_modal(VouchModal(
                        user_to_vouch=[m for m in users if m != user][0],
                        ticket_channel=interaction.channel,
                        interaction_user=user
                    ))
                except Exception:
                    # If user DMs are closed, send a message in ticket channel instead
                    await interaction.channel.send(
                        f"{user.mention}, please submit your vouch using the slash command /vouch in this channel."
                    )

            # Store this view instance for modal reference
            interaction.channel.ticket_actions_view = self

            # Update button states to disabled (optional)
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message("Please check your DMs to submit your vouch.", ephemeral=True)
        else:
            await interaction.response.send_message("Waiting for the other party to confirm completion.", ephemeral=True)

    @discord.ui.button(label="❌ Cancel Trade", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.send("❌ Trade has been cancelled.")
        await self.archive_ticket(interaction.channel, self.listing_message)

    async def finish_vouching(self):
        # Called when both users submit vouch
        channel = self.listing_message.channel

        # Post all vouches to the vouch channel
        vouch_channel = self.listing_message.guild.get_channel(CHANNELS["vouch_post"])
        if not vouch_channel:
            print("Vouch post channel not found!")
            return

        users = [m for m in channel.members if not m.bot]
        for user in users:
            data = vouch_data.get(user.id)
            if data:
                avg_stars = sum(data["stars"]) / len(data["stars"])
                count = data["count"]
                comments = "\n".join(f"- {c}" for c in data["comments"])
                embed = discord.Embed(
                    title=f"Vouch Summary for {user.display_name}",
                    description=f"⭐ Average Stars: {avg_stars:.2f} ({count} vouches)\n\n**Comments:**\n{comments}",
                    color=EMBED_COLOR,
                    timestamp=datetime.utcnow()
                )
                embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
                await vouch_channel.send(embed=embed)

        # Archive ticket as normal
        await self.archive_ticket(channel, self.listing_message)

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

        # Delete the original listing message too (remove listing after trade completion/cancel)
        try:
            await listing_message.delete()
        except Exception:
            pass

        await channel.delete()


# --- MODALS ---

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
            view=TicketActions(interaction.message)
        )

        await interaction.response.send_message(f"📨 Ticket created: {ticket_channel.mention}", ephemeral=True)


# --- SLASH COMMANDS FOR VOUCHES ---

@bot.tree.command(name="vouchleader", description="Show top 10 vouched users")
async def vouchleader(interaction: discord.Interaction):
    if not vouch_data:
        await interaction.response.send_message("No vouches recorded yet.", ephemeral=True)
        return

    # Sort users by total vouch count desc, then average stars desc
    def sort_key(item):
        uid, data = item
        avg_stars = sum(data["stars"]) / len(data["stars"]) if data["stars"] else 0
        return (data["count"], avg_stars)

    sorted_vouches = sorted(vouch_data.items(), key=sort_key, reverse=True)[:10]

    embed = discord.Embed(title="🏆 Vouch Leaderboard (Top 10)", color=EMBED_COLOR)

    for i, (user_id, data) in enumerate(sorted_vouches, 1):
        user = interaction.guild.get_member(user_id)
        if user:
            avg_stars = sum(data["stars"]) / len(data["stars"])
            embed.add_field(
                name=f"{i}. {user.display_name}",
                value=f"⭐ Avg: {avg_stars:.2f} | {data['count']} vouches",
                inline=False
            )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="vouchcount", description="Check your personal vouch count")
async def vouchcount(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = vouch_data.get(user_id)

    if not data:
        await interaction.response.send_message("You have no vouches recorded yet.", ephemeral=True)
        return

    avg_stars = sum(data["stars"]) / len(data["stars"]) if data["stars"] else 0
    await interaction.response.send_message(
        f"You have {data['count']} vouches with an average rating of {avg_stars:.2f} stars.", ephemeral=True
    )


# --- COMMANDS ---


@bot.event
async def on_ready():
    print(f"Bot is live as {bot.user}.")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


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


# --- START ---
TOKEN = os.getenv("RELLY_DISCORD")
bot.run(TOKEN)
