import discord
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime
from config import CHANNELS, EMBED_COLOR, BRANDING_IMAGE
from database.db import Database

class VouchView:
    def __init__(self, ticket_actions, channel, listing_message, user1, user2, lister):
        self.ticket_actions = ticket_actions
        self.channel = channel
        self.listing_message = listing_message
        self.users = {str(user1.id): user1, str(user2.id): user2}
        self.vouches = {}
        self.lister = lister

    async def submit_vouch(self, user_id, stars, comment):
        user_id_str = str(user_id)
        self.vouches[user_id_str] = {"stars": stars, "comment": comment}
        await Database.update_vouch(user_id_str, stars, comment)

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
        await self.vouch_view.submit_vouch(self.user_submitting.id, self.star_rating, comment_value)
        await interaction.response.send_message("✅ Your vouch has been recorded! Waiting for other party to vouch.", ephemeral=True)
        if self.vouch_view.all_vouches_submitted():
            await self.vouch_view.finish_vouching()