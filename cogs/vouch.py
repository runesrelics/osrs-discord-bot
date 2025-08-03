import discord
from discord.ext import commands
import sqlite3
import json
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

async def setup(bot):
    await bot.add_cog(VouchCog(bot))