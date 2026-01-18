import logging
import os
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger("PepperBot.Database")


class Database:
    def __init__(self, db_name="pepperbot.db"):
        self.db_name = db_name

    async def init(self):
        """Initialize the database and create tables if they don't exist."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sent_deals (
                    deal_id TEXT PRIMARY KEY,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    max_price REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, query)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    alert_id INTEGER,
                    deal_id TEXT,
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(alert_id) REFERENCES alerts(id) ON DELETE CASCADE,
                    PRIMARY KEY(alert_id, deal_id)
                )
            """)

            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_user_id ON alerts(user_id)"
            )
            
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_query ON alerts(query)"
            )
            
 
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_history_alert_id ON alert_history(alert_id)"
            )
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_history_lookup 
                ON alert_history(alert_id, deal_id)
            """)
            
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sent_deals_deal_id ON sent_deals(deal_id)"
            )
            
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sent_deals_sent_at ON sent_deals(sent_at)"
            )

            await db.commit()
            logger.info("Database initialized with performance indexes.")

        await self.run_migration()

    async def run_migration(self):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='category_configs'"
            ) as cursor:
                if await cursor.fetchone():
                    logger.info("Category tables already exist, skipping migration")
                    return
            
            try:
                migration_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations', 'migration_001_category_system.sql')
                if not os.path.exists(migration_path):
                     migration_path = "PEPPER/migrations/migration_001_category_system.sql"

                with open(migration_path, 'r') as f:
                    migration_sql = f.read()
                await db.executescript(migration_sql)
                logger.info("Successfully applied category system migration")
            except Exception as e:
                logger.error(f"Migration failed: {e}", exc_info=True)
                raise

    async def close(self):
        """Placeholder if we need to close persistent connections later."""
        pass

    async def add_sent_deal(self, deal_id: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT OR IGNORE INTO sent_deals (deal_id) VALUES (?)", (deal_id,))
            await db.commit()

    async def is_deal_sent(self, deal_id: str) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT 1 FROM sent_deals WHERE deal_id = ?", (deal_id,)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def cleanup_old_deals(self, days=30):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "DELETE FROM sent_deals WHERE sent_at < datetime('now', ?)", (f"-{days} days",)
            )
            await db.commit()

    async def add_alert(self, user_id: int, query: str, max_price: Optional[float] = None) -> bool:
        """Adds or updates an alert."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute(
                    """
                    INSERT INTO alerts (user_id, query, max_price) 
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, query) DO UPDATE SET
                    max_price = excluded.max_price
                """,
                    (user_id, query, max_price),
                )
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding alert: {e}")
            return False

    async def remove_alert(self, user_id: int, query: str) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "DELETE FROM alerts WHERE user_id = ? AND query = ?", (user_id, query)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_user_alerts(self, user_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM alerts WHERE user_id = ?", (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_unique_queries(self) -> List[str]:
        """Returns a list of unique queries to search for."""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT DISTINCT query FROM alerts") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def get_alerts_by_query(self, query: str) -> List[Dict[str, Any]]:
        """Returns all alerts watching a specific query."""
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM alerts WHERE query = ?", (query,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def is_deal_seen_by_alert(self, alert_id: int, deal_id: str) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT 1 FROM alert_history WHERE alert_id = ? AND deal_id = ?",
                (alert_id, deal_id),
            ) as cursor:
                return await cursor.fetchone() is not None

    async def mark_deal_seen(self, alert_id: int, deal_id: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR IGNORE INTO alert_history (alert_id, deal_id) VALUES (?, ?)",
                (alert_id, deal_id),
            )
            await db.commit()

    async def mark_deals_seen_batch(self, records: List[tuple]):
        """Batch insert for alert history.
        
        Args:
            records: List of (alert_id, deal_id) tuples
        """
        if not records:
            return
        
        async with aiosqlite.connect(self.db_name) as db:
            await db.executemany(
                "INSERT OR IGNORE INTO alert_history (alert_id, deal_id) VALUES (?, ?)",
                records
            )
            await db.commit()
        
        logger.debug(f"Batch marked {len(records)} deals as seen")

    async def add_category_config(
        self,
        guild_id: int,
        slug: str,
        channel_id: int,
        schedule_type: str,
        schedule_time: str,
        schedule_day: str = None,
        schedule_date: int = None,
        name: str = None,
        min_temperature: int = 0,
        max_price: float = None,
    ) -> Optional[int]:
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO category_configs 
                    (guild_id, slug, name, channel_id, schedule_type, schedule_time, 
                     schedule_day, schedule_date, min_temperature, max_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (guild_id, slug, name, channel_id, schedule_type, schedule_time,
                     schedule_day, schedule_date, min_temperature, max_price),
                )
                await db.commit()
                return cursor.lastrowid
        except aiosqlite.IntegrityError:
            logger.warning(f"Category {slug} already exists for guild {guild_id}")
            return None
        except Exception as e:
            logger.error(f"Error adding category: {e}")
            return None

    async def remove_category_config(self, guild_id: int, slug: str) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "DELETE FROM category_configs WHERE guild_id = ? AND slug = ?",
                (guild_id, slug),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_guild_categories(self, guild_id: int, status: str = None) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            if status:
                query = "SELECT * FROM category_configs WHERE guild_id = ? AND status = ?"
                params = (guild_id, status)
            else:
                query = "SELECT * FROM category_configs WHERE guild_id = ?"
                params = (guild_id,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_category_by_slug(self, guild_id: int, slug: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM category_configs WHERE guild_id = ? AND slug = ?",
                (guild_id, slug),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_category_status(self, guild_id: int, slug: str, status: str) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                """
                UPDATE category_configs 
                SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE guild_id = ? AND slug = ?
                """,
                (status, guild_id, slug),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_category_last_run(self, category_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "UPDATE category_configs SET last_run = CURRENT_TIMESTAMP WHERE id = ?",
                (category_id,),
            )
            await db.commit()

    async def get_active_categories_for_schedule(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM category_configs WHERE status = 'active' ORDER BY guild_id, id"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def is_category_deal_sent(self, category_id: int, deal_id: str) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT 1 FROM category_sent_deals WHERE category_id = ? AND deal_id = ?",
                (category_id, deal_id),
            ) as cursor:
                return await cursor.fetchone() is not None

    async def mark_category_deal_sent(self, category_id: int, deal_id: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR IGNORE INTO category_sent_deals (category_id, deal_id) VALUES (?, ?)",
                (category_id, deal_id),
            )
            await db.commit()

    async def mark_category_deals_sent_batch(self, records: List[tuple]):
        if not records:
            return
        async with aiosqlite.connect(self.db_name) as db:
            await db.executemany(
                "INSERT OR IGNORE INTO category_sent_deals (category_id, deal_id) VALUES (?, ?)",
                records,
            )
            await db.commit()

    async def cleanup_category_deals(self, days: int = 30):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "DELETE FROM category_sent_deals WHERE sent_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            await db.commit()

    async def update_category_stats(self, category_id: int, deals_found: int, deals_sent: int, errors: int = 0):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                """
                INSERT INTO category_stats (category_id, date, deals_found, deals_sent, scrape_errors)
                VALUES (?, DATE('now'), ?, ?, ?)
                ON CONFLICT(category_id, date) DO UPDATE SET
                    deals_found = deals_found + excluded.deals_found,
                    deals_sent = deals_sent + excluded.deals_sent,
                    scrape_errors = scrape_errors + excluded.scrape_errors
                """,
                (category_id, deals_found, deals_sent, errors),
            )
            await db.commit()