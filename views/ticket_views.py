import discord
from discord.ui import View, Button
import io
from config import CHANNELS
from views.vouch_views import VouchView

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
        await self.cleanup_bot_messages(channel)
        view1 = StarRatingView(self.vouch_view, user_list[0])
        view2 = StarRatingView(self.vouch_view, user_list[1])
        
        await channel.send(f"{user_list[0].mention}, please rate your trade partner:", view=view1)
        await channel.send(f"{user_list[1].mention}, please rate your trade partner:", view=view2)

    async def cleanup_bot_messages(self, channel, limit=100):
        async for msg in channel.history(limit=limit):
            if msg.author == self.bot.user:
                try:
                    await msg.delete()
                except discord.Forbidden:
                    pass

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

class ListingRemoveView(View):
    def __init__(self, lister, channel, listing_message, ticket_actions):
        super().__init__(timeout=60)
        self.lister = lister
        self.channel = channel
        self.listing_message = listing_message
        self.ticket_actions = ticket_actions
        self.decision = None

    @discord.ui.button(label="🗑️ Yes, remove listing", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("🚫 Only the listing owner can use this.", ephemeral=True, delete_after=3)
            return

        await interaction.response.send_message("🛑Listing will be removed and the ticket archived.", ephemeral=True)
        self.decision = True
        self.stop()

    @discord.ui.button(label="❌ No, keep listing", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.lister.id:
            await interaction.response.send_message("🚫 Only the listing owner can use this.", ephemeral=True, delete_after=3)
            return

        await interaction.response.send_message("✅ Listing will be kept. Archiving the ticket.", ephemeral=True)
        self.decision = False
        self.stop()