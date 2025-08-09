import discord
from discord.ext import commands
from discord import app_commands
from config import EMBED_COLOR

class ReactRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_emojis = {
            "🎉": "Giveaways",  # party emoji
            "💀": "PvP",        # skull emoji
            "⚔️": "PvM",        # crossswords emoji
            "🤖": "Botters"     # robot emoji
        }

    @app_commands.command(name="react", description="Create a react roles message")
    @app_commands.checks.has_any_role("Admin", "Moderator")  # Restrict to admins and moderators
    async def react(self, interaction: discord.Interaction):
        """Create a react roles message"""
        try:
            # Create the embed
            embed = discord.Embed(
                title="🎭 React Roles",
                description="React below to receive role notifications!",
                color=EMBED_COLOR
            )
            
            # Add role information
            role_info = ""
            for emoji, role_name in self.role_emojis.items():
                role_info += f"{emoji} **{role_name}**\n"
            
            embed.add_field(name="Available Roles", value=role_info, inline=False)
            embed.set_footer(text="Click the reactions below to get your roles!")
            
            # Send the message
            message = await interaction.channel.send(embed=embed)
            
            # Add reactions
            for emoji in self.role_emojis.keys():
                await message.add_reaction(emoji)
            
            await interaction.response.send_message("✅ React roles message created!", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error creating react roles message: {str(e)}",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle when a user adds a reaction"""
        # Check if the reaction is one of our role emojis
        emoji_str = str(payload.emoji)
        if emoji_str not in self.role_emojis:
            return
            
        # Get the guild and member
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
            
        role_name = self.role_emojis[emoji_str]
        
        # Find the role in the guild
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            # Try to create the role if it doesn't exist
            try:
                role = await guild.create_role(name=role_name, reason="React roles system")
            except discord.Forbidden:
                return
            except Exception:
                return
        
        # Add the role to the user
        try:
            await member.add_roles(role, reason="React roles system")
        except discord.Forbidden:
            return
        except Exception:
            return

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle when a user removes a reaction"""
        # Check if the reaction is one of our role emojis
        emoji_str = str(payload.emoji)
        if emoji_str not in self.role_emojis:
            return
            
        role_name = self.role_emojis[emoji_str]
        
        # Find the role in the guild
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            return
        
        # Get the member
        member = guild.get_member(payload.user_id)
        if not member:
            return
        
        # Remove the role from the user
        try:
            await member.remove_roles(role, reason="React roles system")
        except discord.Forbidden:
            return
        except Exception:
            return

    @react.error
    async def react_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(ReactRoles(bot))
