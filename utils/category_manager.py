import datetime
import logging
from typing import Any, Dict, List, Optional

import discord

from .config import Config
from .db import Database
from .scraper import PepperScraper

logger = logging.getLogger("PepperBot.CategoryManager")


class CategoryManager:
    def __init__(self, db: Database):
        self.db = db

    async def validate_slug(self, scraper: PepperScraper, slug: str) -> tuple[bool, Optional[str]]:
        result = await scraper.get_group_deals(slug, limit=1)
        if result["success"] and result["deals"]:
            return True, None
        return False, f"Category '{slug}' not found on Pepper.pl"

    async def validate_channel_permissions(
        self, bot: discord.Client, channel: discord.TextChannel
    ) -> tuple[bool, Optional[str]]:
        permissions = channel.permissions_for(channel.guild.me)
        if not permissions.send_messages:
            return False, f"Missing 'Send Messages' permission in {channel.mention}"
        if not permissions.embed_links:
            return False, f"Missing 'Embed Links' permission in {channel.mention}"
        return True, None

    async def parse_schedule(
        self, frequency: str, time: str, day: str = None, date: int = None
    ) -> tuple[bool, Optional[Dict], Optional[str]]:
        import re
        
        time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
        if not time_pattern.match(time):
            return False, None, "Time must be in HH:MM format (e.g., 09:00)"
        
        schedule = {
            'type': frequency.lower(),
            'time': time,
            'day': day.lower() if day else None,
            'date': date
        }
        
        valid_frequencies = ['daily', 'weekly', 'biweekly', 'monthly']
        if schedule['type'] not in valid_frequencies:
            return False, None, f"Frequency must be one of: {', '.join(valid_frequencies)}"
        
        if schedule['type'] in ['weekly', 'biweekly'] and not day:
            return False, None, f"{frequency} requires a day (e.g., monday)"
        
        if schedule['type'] == 'monthly' and not date:
            return False, None, "Monthly requires a date (1-31)"
        
        if schedule['type'] == 'monthly' and (date < 1 or date > 31):
            return False, None, "Monthly date must be between 1-31"
        
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        if day and day.lower() not in valid_days:
            return False, None, f"Day must be one of: {', '.join(valid_days)}"
        
        return True, schedule, None

    def should_run_now(self, category: Dict[str, Any]) -> bool:
        now = datetime.datetime.now()
        
        schedule_time_parts = category['schedule_time'].split(':')
        schedule_hour = int(schedule_time_parts[0])
        schedule_minute = int(schedule_time_parts[1])
        
        if now.hour != schedule_hour or now.minute != schedule_minute:
            return False
        
        if category['schedule_type'] == 'daily':
            return True
        
        if category['schedule_type'] in ['weekly', 'biweekly']:
            day_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            target_day = day_map.get(category['schedule_day'])
            if now.weekday() != target_day:
                return False
            
            if category['schedule_type'] == 'biweekly':
                if category['last_run']:
                    last_run = datetime.datetime.fromisoformat(category['last_run'])
                    days_since = (now - last_run).days
                    if days_since < 13:
                        return False
            
            return True
        
        if category['schedule_type'] == 'monthly':
            return now.day == category['schedule_date']
        
        return False

    def format_schedule(self, category: Dict[str, Any]) -> str:
        if category['schedule_type'] == 'daily':
            return f"Daily at {category['schedule_time']}"
        elif category['schedule_type'] == 'weekly':
            return f"Weekly ({category['schedule_day'].capitalize()}) at {category['schedule_time']}"
        elif category['schedule_type'] == 'biweekly':
            return f"Biweekly ({category['schedule_day'].capitalize()}) at {category['schedule_time']}"
        elif category['schedule_type'] == 'monthly':
            return f"Monthly (day {category['schedule_date']}) at {category['schedule_time']}"
        return "Unknown schedule"

    def get_category_emoji(self, slug: str) -> str:
        emoji_map = {
            'bilety-lotnicze': '✈️',
            'podzespoly-komputerowe': '💻',
            'smartfony': '📱',
            'gry': '🎮',
            'lego': '🧱',
            'laptopy': '💻',
            'dom-i-ogrod': '🏡',
            'narzedzia': '🔧',
            'elektronika': '⚡',
            'konsole': '🎮',
        }
        return emoji_map.get(slug, '📂')