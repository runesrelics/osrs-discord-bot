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
    async def vouchreq(self, ctx, user: discord.Member):
        """Request a vouch with another user"""
        # Check if user is trying to vouch with themselves
        if user.id == ctx.author.id:
            await ctx.send("❌ You cannot vouch with yourself.", ephemeral=True)
            return
        
        # Create ticket channel (same as GP and account tickets - no category specified)
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
        
        # Get the tickets category
        tickets_category = ctx.guild.get_channel(1307491683461763132)
        
        ticket_channel = await ctx.guild.create_text_channel(
            f"vouch-request-{ctx.author.name}-{user.name}",
            category=tickets_category,
            overwrites=overwrites,
            topic="Vouch request ticket between users."
        )
        
        # Create custom view for vouch request tickets (no "Mark as Complete" button)
        from cogs.tickets import TicketActions
        
        # Create a dummy message for the ticket actions (since there's no listing)
        dummy_message = type('obj', (object,), {'id': 0})()
        
        # Create custom vouch request view
        class VouchRequestView(discord.ui.View):
            def __init__(self, user1, user2):
                super().__init__(timeout=None)
                self.users = {user1.id: user1, user2.id: user2}
                self.ticket_actions = TicketActions(
                    ticket_message=dummy_message,
                    listing_message=dummy_message,
                    account_message=dummy_message,
                    user1=user1,
                    user2=user2
                )
                # Store reference to this view in the cog for easy access
                if not hasattr(ctx.bot.get_cog('VouchCog'), 'vouch_requests'):
                    ctx.bot.get_cog('VouchCog').vouch_requests = {}
            
            @discord.ui.button(label="❌ Cancel Request", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id not in self.users:
                    await interaction.response.send_message("You are not part of this vouch request.", ephemeral=True)
                    return
                await interaction.channel.send("❌ Vouch request has been cancelled.")
                await self.ticket_actions.archive_ticket(interaction.channel)
        
        vouch_request_view = VouchRequestView(ctx.author, user)
        
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
        
        await ticket_channel.send(f"{admin_mentions}\n{ctx.author.mention} {user.mention}", embed=embed, view=vouch_request_view)
        
        # Store reference to the vouch request view for easy access
        if not hasattr(self, 'vouch_requests'):
            self.vouch_requests = {}
        self.vouch_requests[ticket_channel.id] = vouch_request_view
        
        await ctx.send(
            f"✅ Vouch request ticket created: {ticket_channel.mention}",
            ephemeral=True
        )

    @commands.command(name="accept")
    @commands.has_permissions(administrator=True)
    async def accept_vouch_request(self, ctx):
        """Accept a vouch request and start the vouching process (Admin only)"""
        # Check if this is a vouch request ticket
        if not ctx.channel.name.startswith("vouch-request-"):
            await ctx.send("❌ This command can only be used in vouch request ticket channels.", ephemeral=True)
            return
        
        # Get the stored vouch request view
        vouch_request_view = None
        if hasattr(self, 'vouch_requests') and ctx.channel.id in self.vouch_requests:
            vouch_request_view = self.vouch_requests[ctx.channel.id]
        
        # If not found in stored references, try to find it in channel history
        if not vouch_request_view:
            async for message in ctx.channel.history(limit=50):
                if message.components:
                    for view in message.components:
                        # Check if this is our custom VouchRequestView
                        if hasattr(view, 'ticket_actions') and hasattr(view, 'users') and hasattr(view, 'cancel'):
                            vouch_request_view = view
                            break
                    if vouch_request_view:
                        break
        
        if not vouch_request_view:
            await ctx.send("❌ Could not find vouch request actions in this ticket.", ephemeral=True)
            return
        
        # Check if vouching has already started
        if hasattr(vouch_request_view.ticket_actions, 'vouch_view') and vouch_request_view.ticket_actions.vouch_view:
            await ctx.send("✅ Vouching process is already active. Please use the rating buttons above.", ephemeral=True)
            return
        
        # Start the vouching process
        await ctx.send("✅ Admin has approved this vouch request. Starting vouching process...")
        await vouch_request_view.ticket_actions.start_vouching(ctx.channel)

    @commands.command(name="sync_commands")
    @commands.has_permissions(administrator=True)
    async def sync_commands(self, ctx):
        """Force sync slash commands"""
        try:
            synced = await ctx.bot.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} commands")
        except Exception as e:
            await ctx.send(f"❌ Error syncing commands: {str(e)}")

async def setup(bot):
    await bot.add_cog(VouchCog(bot))