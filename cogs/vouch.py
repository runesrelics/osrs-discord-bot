import discord
from discord.ext import commands
from discord import app_commands
from database.db import Database
from config import EMBED_COLOR, CHANNELS

class Vouch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vouchleader", description="Show top 10 vouched users")
    async def vouchleader(self, interaction: discord.Interaction):
        rows = await Database.get_top_vouches(10)

        if not rows:
            await interaction.response.send_message("No vouches recorded yet.")
            return

        embed = discord.Embed(title="🏆 Runes & Relics Vouch Leaderboard", color=EMBED_COLOR)
        embed.set_image(url="https://i.postimg.cc/0jHw8mRV/glowww.png")
        embed.set_footer(text="Based on average rating and number of vouches")

        for user_id, total_stars, count in rows:
            member = interaction.guild.get_member(int(user_id))
            if member:
                avg = total_stars / count
                embed.add_field(name=member.display_name, value=f"⭐ {avg:.2f} from {count} vouches", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vouchcheck", description="Check how many vouches you have.")
    async def vouchcheck(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        row = await Database.get_vouch_data(user_id)

        if not row:
            await interaction.response.send_message("You have no recorded vouches yet.", ephemeral=True)
            return

        total_stars, count, _ = row
        avg = total_stars / count if count > 0 else 0
        await interaction.response.send_message(
            f"📊 You have {count} vouches with an average rating of {avg:.2f}⭐.",
            ephemeral=True
        )

    @app_commands.command(name="addvouch", description="Manually add a vouch for a user")
    @app_commands.checks.has_any_role("Admin", "Moderator")  # Restrict to admins and moderators
    async def addvouch(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        stars: app_commands.Range[int, 1, 5],  # Limit stars to 1-5
        comment: str
    ):
        try:
            # Add the vouch to the database
            await Database.update_vouch(str(user.id), stars, comment)
            
            # Get updated vouch data
            row = await Database.get_vouch_data(str(user.id))
            if not row:
                await interaction.response.send_message("❌ Error adding vouch.", ephemeral=True)
                return
                
            total_stars, count, _ = row
            avg = total_stars / count if count > 0 else 0

            # Create embed for vouch notification
            embed = discord.Embed(
                title="🛡️ Manual Vouch Added",
                color=discord.Color.green(),
                timestamp=interaction.created_at
            )
            embed.add_field(name="User", value=user.mention, inline=True)
            embed.add_field(name="Rating", value=f"{stars}⭐", inline=True)
            embed.add_field(name="New Average", value=f"{avg:.2f}⭐", inline=True)
            embed.add_field(name="Total Vouches", value=str(count), inline=True)
            embed.add_field(name="Comment", value=comment, inline=False)
            embed.set_footer(text=f"Added by {interaction.user.display_name}")

            # Send confirmation
            await interaction.response.send_message(embed=embed)

            # Try to send notification to the user
            try:
                user_embed = embed.copy()
                user_embed.title = "🌟 You received a vouch!"
                await user.send(embed=user_embed)
            except discord.Forbidden:
                pass  # User might have DMs disabled

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error adding vouch: {str(e)}",
                ephemeral=True
            )

    @addvouch.error
    async def addvouch_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingAnyRole):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Vouch(bot))