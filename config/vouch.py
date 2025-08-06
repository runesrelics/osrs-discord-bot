import discord
from discord.ext import commands
import sqlite3
import json
import asyncio
from datetime import datetime

class VouchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DB_PATH = "/app/data/vouches.db"
        self.EMBED_COLOR = discord.Color.gold()
        self.BRANDING_IMAGE = "https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png"
        
        # Initialize database
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
            conn.commit()

    def get_vouch_data(self, user_id):
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT total_stars, count, comments FROM vouches WHERE user_id = ?', (user_id,))
            return cursor.fetchone()

    def update_vouch(self, user_id, stars, comment):
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.cursor()
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

    @commands.hybrid_command(name="vouchleader", description="Show top 10 vouched users")
    async def vouchleader(self, ctx):
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, total_stars, count FROM vouches WHERE count > 0')
            rows = cursor.fetchall()

        if not rows:
            await ctx.send("No vouches recorded yet.")
            return

        # Sort by average stars (total_stars/count) descending, then count descending
        rows.sort(key=lambda r: (r[1]/r[2], r[2]), reverse=True)
        top10 = rows[:10]

        embed = discord.Embed(title="🏆 Runes & Relics Vouch Leaderboard", color=self.EMBED_COLOR)
        embed.set_image(url="https://i.postimg.cc/0jHw8mRV/glowww.png")
        embed.set_footer(text="Based on average rating and number of vouches")

        for user_id, total_stars, count in top10:
            member = ctx.guild.get_member(int(user_id))
            if member:
                avg = total_stars / count
                embed.add_field(name=member.display_name, value=f"⭐ {avg:.2f} from {count} vouches", inline=False)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="vouchcheck", description="Check how many vouches you have.")
    async def vouchcheck(self, ctx):
        user_id = str(ctx.author.id)
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT total_stars, count FROM vouches WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()

        if not row:
            await ctx.send("You have no recorded vouches yet.", ephemeral=True)
            return

        total_stars, count = row
        avg = total_stars / count if count > 0 else 0
        await ctx.send(
            f"📊 You have {count} vouches with an average rating of {avg:.2f}⭐.",
            ephemeral=True
        )

    @commands.hybrid_command(name="addvouch", description="Add a vouch for a user (Admin/Mod only)")
    @commands.has_permissions(administrator=True)
    async def addvouch(self, ctx):
        # Create a modal for admin to input user and vouch details
        class AddVouchModal(discord.ui.Modal, title="Add Vouch"):
            user_id_input = discord.ui.TextInput(
                label="User ID to vouch",
                placeholder="Enter the Discord user ID",
                required=True,
                min_length=17,
                max_length=20
            )
            
            stars_input = discord.ui.TextInput(
                label="Stars (1-5)",
                placeholder="Enter rating from 1 to 5",
                required=True,
                min_length=1,
                max_length=1
            )
            
            comment_input = discord.ui.TextInput(
                label="Vouch Comment",
                placeholder="Enter your vouch comment",
                required=True,
                max_length=500,
                style=discord.TextStyle.paragraph
            )

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    user_id = int(self.user_id_input.value)
                    stars = int(self.stars_input.value)
                    
                    if stars < 1 or stars > 5:
                        await interaction.response.send_message("❌ Stars must be between 1 and 5.", ephemeral=True)
                        return
                    
                    # Get the user
                    user = interaction.guild.get_member(user_id)
                    if not user:
                        await interaction.response.send_message("❌ User not found in this server.", ephemeral=True)
                        return
                    
                    # Create vouch comment
                    comment = f"Admin vouch by {interaction.user.display_name}: {self.comment_input.value}"
                    
                    # Update vouch in database
                    self.cog.update_vouch(str(user_id), stars, comment)
                    
                    # Post to vouch thread
                    vouch_thread_id = 1383401756335149087
                    vouch_thread = interaction.guild.get_channel(vouch_thread_id)
                    
                    if vouch_thread:
                        embed = discord.Embed(
                            title="⭐ New Vouch Added",
                            description=f"**{user.display_name}** received a vouch from **{interaction.user.display_name}**",
                            color=discord.Color.gold()
                        )
                        embed.add_field(name="Rating", value="⭐" * stars, inline=True)
                        embed.add_field(name="Comment", value=self.comment_input.value, inline=False)
                        embed.set_footer(text=f"Admin vouch • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                        
                        await vouch_thread.send(embed=embed)
                    
                    await interaction.response.send_message(
                        f"✅ Successfully added vouch for {user.display_name} with {stars}⭐ rating.",
                        ephemeral=True
                    )
                    
                except ValueError:
                    await interaction.response.send_message("❌ Invalid user ID or stars value.", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"❌ Error adding vouch: {str(e)}", ephemeral=True)

        # For hybrid commands, we need to check if it's an interaction or context
        if ctx.interaction:
            # It's a slash command
            modal = AddVouchModal()
            modal.cog = self
            await ctx.interaction.response.send_modal(modal)
        else:
            # It's a text command, send instructions
            await ctx.send("❌ This command must be used as a slash command. Use `/addvouch` instead of `!addvouch`.")

    @commands.hybrid_command(name="vouchreq", description="Request a vouch with another user")
    async def vouchreq(self, ctx):
        # For hybrid commands, we need to check if it's an interaction or context
        if ctx.interaction:
            # It's a slash command - prompt for user mention
            await ctx.interaction.response.send_message("Please mention the user you want to vouch with (e.g., @username):", ephemeral=True)
            
            # Set up a check for the next message from the user
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            
            try:
                # Wait for the user's response
                message = await self.bot.wait_for('message', timeout=30.0, check=check)
                
                # Parse the mentioned user
                if not message.mentions:
                    await ctx.followup.send("❌ Please mention a user with @username", ephemeral=True)
                    return
                
                user = message.mentions[0]
                
                # Check if user is trying to vouch with themselves
                if user.id == ctx.author.id:
                    await ctx.followup.send("❌ You cannot vouch with yourself.", ephemeral=True)
                    return
                
                # Create vouch request ticket
                category = ctx.guild.get_channel(1395791949969231945)  # Archived tickets category
                if not category:
                    await ctx.followup.send("❌ Could not find tickets category.", ephemeral=True)
                    return
                
                # Create ticket channel
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                }
                
                # Add admin and moderator roles
                admin_role = discord.utils.get(ctx.guild.roles, name="Admin")
                mod_role = discord.utils.get(ctx.guild.roles, name="Moderator")
                
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                if mod_role:
                    overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                
                ticket_channel = await ctx.guild.create_text_channel(
                    f"vouch-request-{ctx.author.name}-{user.name}",
                    category=category,
                    overwrites=overwrites
                )
                
                # Create TicketActions view for vouch request
                from cogs.tickets import TicketActions
                
                # Create a dummy message for the ticket actions (since there's no listing)
                dummy_message = type('obj', (object,), {'id': 0})()
                
                # Create ticket actions view
                ticket_actions = TicketActions(
                    ticket_message=dummy_message,
                    listing_message=dummy_message,
                    account_message=dummy_message,
                    user1=ctx.author,
                    user2=user
                )
                
                # Send initial message with ticket actions
                embed = discord.Embed(
                    title="🤝 Vouch Request",
                    description=f"**{ctx.author.display_name}** has requested to vouch with **{user.display_name}**",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Requested by", value=ctx.author.mention, inline=True)
                embed.add_field(name="Requested with", value=user.mention, inline=True)
                embed.set_footer(text=f"Use !complete when both users are ready to complete the vouch")
                
                # Tag admin and moderator roles
                admin_mentions = ""
                if admin_role:
                    admin_mentions += f"{admin_role.mention} "
                if mod_role:
                    admin_mentions += f"{mod_role.mention}"
                
                await ticket_channel.send(f"{admin_mentions}\n{ctx.author.mention} {user.mention}", embed=embed, view=ticket_actions)
                
                await ctx.followup.send(
                    f"✅ Vouch request ticket created: {ticket_channel.mention}",
                    ephemeral=True
                )
                
            except asyncio.TimeoutError:
                await ctx.followup.send("❌ Timed out. Please try again.", ephemeral=True)
            except Exception as e:
                await ctx.followup.send(f"❌ Error creating vouch request: {str(e)}", ephemeral=True)
        else:
            # It's a text command, send instructions
            await ctx.send("❌ This command must be used as a slash command. Use `/vouchreq` instead of `!vouchreq`.")

async def setup(bot):
    await bot.add_cog(VouchCog(bot))