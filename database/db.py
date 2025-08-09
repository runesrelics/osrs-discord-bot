import aiosqlite
import json
from config import DB_PATH

class Database:
    @staticmethod
    async def initialize():
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS vouches (
                    user_id TEXT PRIMARY KEY,
                    total_stars INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    comments TEXT
                )
            ''')
            await db.commit()

    @staticmethod
    async def get_vouch_data(user_id: str):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT total_stars, count, comments FROM vouches WHERE user_id = ?',
                (user_id,)
            ) as cursor:
                return await cursor.fetchone()

    @staticmethod
    async def update_vouch(user_id: str, stars: int, comment: str):
        async with aiosqlite.connect(DB_PATH) as db:
            row = await Database.get_vouch_data(user_id)

            if row:
                total_stars, count, comments_json = row
                comments_list = json.loads(comments_json) if comments_json else []
                total_stars += stars
                count += 1
                comments_list.append(comment)
                comments_json = json.dumps(comments_list)
                await db.execute(
                    'UPDATE vouches SET total_stars=?, count=?, comments=? WHERE user_id=?',
                    (total_stars, count, comments_json, user_id)
                )
            else:
                comments_json = json.dumps([comment])
                await db.execute(
                    'INSERT INTO vouches (user_id, total_stars, count, comments) VALUES (?, ?, ?, ?)',
                    (user_id, stars, 1, comments_json)
                )
            await db.commit()

    @staticmethod
    async def get_top_vouches(limit: int = 10):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT user_id, total_stars, count FROM vouches WHERE count > 0'
            ) as cursor:
                rows = await cursor.fetchall()
                # Sort by average stars (total_stars/count) descending, then count descending
                rows = sorted(rows, key=lambda r: (r[1]/r[2], r[2]), reverse=True)
                return rows[:limit]