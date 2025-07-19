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
    "archive": 1395791949969231945  # your actual archive channel ID here
}

# Emojis and color scheme
EMBED_COLOR = discord.Color.gold()
BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"

# --- VIEWS ---

class TicketActions(View):
    def __init__(self, message):
        super().__init__()
        self.message = message
        self.completions = set()

    @discord.ui.button(label="✅ Mark as Complete", style=discord.ButtonStyle.success)
    async def complete(self, interaction: discord.Interaction, button: Button):
        self.completions.add(interaction.user.id)
        if len(self.completions) >= 2:
            await interaction.channel.send("✅ Trade marked as complete. Archiving ticket.")
            await self.archive_ticket(interaction.channel, self.message)
        else:
            await interaction.response.send_message("Waiting for the other party to confirm completion.", ephemeral=True)

    @discord.ui.button(label="❌ Cancel Trade", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.send("❌ Trade has been cancelled.")
        await self.archive_ticket(interaction.channel, self.message)

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
                # DO NOT delete the image message here — wait until after listing sent
            else:
                await create_trade_channel.send(f"{interaction.user.mention} Please upload images or type 'done' to finish.", delete_after=10)

        # Prepare files for the listing embed message
        files = []
        for img in images[:5]:
            try:
                files.append(await img.to_file())
            except:
                pass

        # Send the listing embed with attached images and BUY button
        msg = await listing_channel.send(embed=listing_embed, view=view, files=files)

        # NOW delete all the user's messages in create_trade channel to clean up (including image upload messages)
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

        # Clean up create_trade channel messages from this user except original message
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

# --- COMMANDS ---

@bot.event
async def on_ready():
    print(f"Bot is live as {bot.user}.")

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
