import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import io
from datetime import datetime
import sqlite3
import json
import asyncio

class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.EMBED_COLOR = discord.Color.gold()
        self.BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"
        self.CHANNELS = {
            "archive": 1395791949969231945,
            "vouch_post": 1383401756335149087
        }

    @commands.command(name="complete")
    async def complete_trade(self, ctx):
        """Mark the trade/vouch as complete and start the vouching process"""
        # Check if this is a ticket channel
        if not (ctx.channel.name.startswith("ticket-") or ctx.channel.name.startswith("vouch-request-")):
            await ctx.send("❌ This command can only be used in trade or vouch request ticket channels.", ephemeral=True)
            return
        
        # Find the ticket actions view in the channel
        ticket_actions = None
        async for message in ctx.channel.history(limit=50):
            if message.components and any(view for view in message.components if isinstance(view, TicketActions)):
                for view in message.components:
                    if isinstance(view, TicketActions):
                        ticket_actions = view
                        break
                if ticket_actions:
                    break
        
        if not ticket_actions:
            await ctx.send("❌ Could not find trade actions in this ticket.", ephemeral=True)
            return
        
        # Check if user is part of the trade/vouch
        if ctx.author.id not in ticket_actions.users:
            await ctx.send("❌ You are not part of this trade/vouch.", ephemeral=True)
            return
        
        # Check if already completed
        if ctx.author.id in ticket_actions.completions:
            await ctx.send("❌ You have already marked this as complete.", ephemeral=True)
            return
        
        # Mark as complete
        ticket_actions.completions.add(ctx.author.id)
        await ctx.send("✅ You marked this as complete. Waiting for other user to mark as complete", ephemeral=True)
        
        # Check if both users have completed
        if len(ticket_actions.completions) == 2:
            await ctx.channel.send("✅ Both parties have marked this as complete.")
            await ticket_actions.start_vouching(ctx.channel)

    @commands.command(name="vouch")
    async def manual_vouch(self, ctx):
        """Manually trigger the vouching process if the modal was accidentally closed"""
        # Check if this is a ticket channel
        if not (ctx.channel.name.startswith("ticket-") or ctx.channel.name.startswith("vouch-request-")):
            await ctx.send("❌ This command can only be used in trade or vouch request ticket channels.", ephemeral=True)
            return
        
        # Find the ticket actions view in the channel
        ticket_actions = None
        async for message in ctx.channel.history(limit=50):
            if message.components and any(view for view in message.components if isinstance(view, TicketActions)):
                for view in message.components:
                    if isinstance(view, TicketActions):
                        ticket_actions = view
                        break
                if ticket_actions:
                    break
        
        if not ticket_actions:
            await ctx.send("❌ Could not find trade actions in this ticket.", ephemeral=True)
            return
        
        # Check if user is part of the trade/vouch
        if ctx.author.id not in ticket_actions.users:
            await ctx.send("❌ You are not part of this trade/vouch.", ephemeral=True)
            return
        
        # Check if vouching has already started
        if hasattr(ticket_actions, 'vouch_view') and ticket_actions.vouch_view:
            await ctx.send("✅ Vouching process is already active. Please use the rating buttons above.", ephemeral=True)
            return
        
        # Check if both users have completed the trade/vouch
        if len(ticket_actions.completions) != 2:
            await ctx.send("❌ Both users must mark this as complete first. Use `!complete` to mark as complete.", ephemeral=True)
            return
        
        # Start vouching process
        await ctx.send("⭐ Manually starting vouching process...", ephemeral=True)
        await ticket_actions.start_vouching(ctx.channel)

class TicketActions(View):
    def __init__(self, ticket_message, listing_message, account_message, user1, user2):
        super().__init__(timeout=None)
        self.ticket_message = ticket_message
        self.listing_message = listing_message
        self.account_message = account_message
        self.users = {user1.id: user1, user2.id: user2}
        self.completions = set()
        self.vouch_view = None
        self.lister = user2
        self.CHANNELS = {
            "archive": 1395791949969231945,
            "vouch_post": 1383401756335149087
        }

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
        await self.archive_ticket(interaction.channel)

    async def start_vouching(self, channel):
        user_list = list(self.users.values())
        self.vouch_view = VouchView(self, channel, self.listing_message, user_list[0], user_list[1], self.lister)
        await cleanup_bot_messages(channel)
        
        # Send vouching instructions
        await channel.send("⭐ **Vouching Process Started** ⭐\n\nBoth users need to rate each other to complete the trade.")
        
        # Create and send rating views for each user
        view1 = StarRatingView(self.vouch_view, user_list[0])
        view2 = StarRatingView(self.vouch_view, user_list[1])
        
        await channel.send(f"{user_list[0].mention}, please rate your trade partner:", view=view1)
        await channel.send(f"{user_list[1].mention}, please rate your trade partner:", view=view2)

    async def archive_ticket(self, channel):
        archive = channel.guild.get_channel(self.CHANNELS["archive"])
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

        await channel.delete()

class VouchView:
    def __init__(self, ticket_actions, channel, listing_message, user1, user2, lister):
        self.ticket_actions = ticket_actions
        self.channel = channel
        self.listing_message = listing_message
        self.user1 = user1
        self.user2 = user2
        self.lister = lister
        self.ratings = {}
        self.comments = {}
        self.DB_PATH = "/app/data/vouches.db"

    def add_rating(self, user_id, rating, comment):
        self.ratings[user_id] = rating
        self.comments[user_id] = comment
        
        # Check if both users have rated
        if len(self.ratings) == 2:
            asyncio.create_task(self.complete_vouching())

    async def complete_vouching(self):
        try:
            # Update vouches in database
            for user_id, rating in self.ratings.items():
                comment = self.comments.get(user_id, "")
                self.update_vouch(str(user_id), rating, comment)
            
            # Send completion message
            await self.channel.send("✅ Both users have left vouches! Trade completed successfully.")
            
            # Post vouches to vouch thread channel
            await self.post_vouches_to_thread()
            
            # Ask lister if they want to delete or keep their listing
            await self.ask_listing_deletion()
            
        except Exception as e:
            await self.channel.send(f"❌ Error completing vouching: {str(e)}")

    async def post_vouches_to_thread(self):
        """Post the vouches to the vouch thread channel"""
        try:
            vouch_channel = self.channel.guild.get_channel(self.ticket_actions.CHANNELS["vouch_post"])
            if not vouch_channel:
                await self.channel.send("❌ Could not find vouch thread channel.")
                return
            
            # Create vouch post content
            user_list = list(self.ticket_actions.users.values())
            user1, user2 = user_list[0], user_list[1]
            
            vouch_content = f"⭐ **Trade Completed** ⭐\n\n"
            vouch_content += f"**Trade Participants:** {user1.mention} & {user2.mention}\n"
            vouch_content += f"**Channel:** {self.channel.mention}\n\n"
            
            # Add individual vouch details
            for user_id, rating in self.ratings.items():
                user = self.channel.guild.get_member(int(user_id))
                comment = self.comments.get(user_id, "")
                stars = "⭐" * rating
                vouch_content += f"**{user.display_name if user else f'User {user_id}'}:** {stars} ({rating}/5)\n"
                if comment and comment != "No comment provided":
                    vouch_content += f"*Comment:* {comment}\n"
                vouch_content += "\n"
            
            await vouch_channel.send(vouch_content)
            
        except Exception as e:
            await self.channel.send(f"❌ Error posting vouches to thread: {str(e)}")

    def update_vouch(self, user_id, stars, comment):
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vouches (
                    user_id TEXT PRIMARY KEY,
                    total_stars INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    comments TEXT
                )
            ''')
            
            row = self.get_vouch_data(user_id)
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

    def get_vouch_data(self, user_id):
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT total_stars, count, comments FROM vouches WHERE user_id = ?', (user_id,))
            return cursor.fetchone()

    async def ask_listing_deletion(self):
        """Ask the lister if they want to delete or keep their listing"""
        # Check if this is a GP listing by checking if listing_message and account_message are the same
        is_gp_listing = (self.listing_message == self.ticket_actions.account_message)
        
        if is_gp_listing:
            # For GP listings, only pass the listing_message (don't pass account_message to avoid double deletion)
            view = ListingDeletionView(self.listing_message, self.ticket_actions, None, self.lister)
        else:
            # For account listings, pass both messages
            view = ListingDeletionView(self.listing_message, self.ticket_actions, self.ticket_actions.account_message, self.lister)
        
        await self.channel.send(
            f"{self.lister.mention}, would you like to delete your listing or keep it active?",
            view=view
        )

class StarRatingView(View):
    def __init__(self, vouch_view, user):
        super().__init__(timeout=300)  # 5 minute timeout
        self.vouch_view = vouch_view
        self.user = user
        self.rating = None
        self.comment = None

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.secondary)
    async def one_star(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Only you can rate your trade partner.", ephemeral=True)
            return
        await self.handle_rating(interaction, 1)

    @discord.ui.button(label="⭐⭐", style=discord.ButtonStyle.secondary)
    async def two_stars(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Only you can rate your trade partner.", ephemeral=True)
            return
        await self.handle_rating(interaction, 2)

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.secondary)
    async def three_stars(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Only you can rate your trade partner.", ephemeral=True)
            return
        await self.handle_rating(interaction, 3)

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.secondary)
    async def four_stars(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Only you can rate your trade partner.", ephemeral=True)
            return
        await self.handle_rating(interaction, 4)

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.secondary)
    async def five_stars(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Only you can rate your trade partner.", ephemeral=True)
            return
        await self.handle_rating(interaction, 5)

    async def handle_rating(self, interaction: discord.Interaction, stars):
        self.rating = stars
        await interaction.response.send_modal(VouchCommentModal(self.vouch_view, self.user.id, stars))

class VouchCommentModal(Modal):
    def __init__(self, vouch_view, user_id, stars):
        super().__init__(title="Leave a Comment")
        self.vouch_view = vouch_view
        self.user_id = user_id
        self.stars = stars
        
        self.comment = TextInput(
            label="Comment (optional)",
            placeholder="Leave a comment about your trade experience...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        comment = self.comment.value or "No comment provided"
        self.vouch_view.add_rating(self.user_id, self.stars, comment)
        
        await interaction.response.send_message(
            f"✅ Thank you for your {self.stars}⭐ rating! Your vouch has been recorded.",
            ephemeral=True
        )

class ListingDeletionView(View):
    def __init__(self, listing_message, ticket_actions=None, account_message=None, lister=None):
        super().__init__(timeout=300)  # 5 minute timeout
        self.listing_message = listing_message
        self.ticket_actions = ticket_actions
        self.account_message = account_message
        self.lister = lister

    @discord.ui.button(label="🗑️ Delete Listing", style=discord.ButtonStyle.danger)
    async def delete_listing(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the user is the lister
        if self.lister and interaction.user.id != self.lister.id:
            await interaction.response.send_message("❌ Only the lister can delete this listing.", ephemeral=True)
            return
        
        try:
            # Delete the listing message (image message with buttons)
            await self.listing_message.delete()
            
            # Delete the account message if we have it (only for account listings)
            if self.account_message and self.account_message != self.listing_message:
                await self.account_message.delete()
            
            await interaction.response.send_message("✅ Listing has been deleted.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to delete listing: {str(e)}", ephemeral=True)
        
        # Archive the ticket after listing decision
        if self.ticket_actions:
            await self.ticket_actions.archive_ticket(interaction.channel)

    @discord.ui.button(label="✅ Keep Listing", style=discord.ButtonStyle.success)
    async def keep_listing(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the user is the lister
        if self.lister and interaction.user.id != self.lister.id:
            await interaction.response.send_message("❌ Only the lister can keep this listing.", ephemeral=True)
            return
        
        await interaction.response.send_message("✅ Listing will remain active.", ephemeral=True)
        
        # Archive the ticket after listing decision
        if self.ticket_actions:
            await self.ticket_actions.archive_ticket(interaction.channel)

async def cleanup_bot_messages(channel, limit=100):
    async for msg in channel.history(limit=limit):
        if msg.author == channel.guild.me:
            try:
                await msg.delete()
            except discord.Forbidden:
                pass

async def setup(bot):
    await bot.add_cog(TicketCog(bot))