import datetime
import logging
import re
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
        """Validate category slug format and existence on Pepper.pl."""
        
        # IMPROVED: Validate slug format first (security)
        if not re.match(r'^[a-z0-9-]+$', slug):
            return False, "Invalid slug format. Use only lowercase letters, numbers, and hyphens."
        
        if len(slug) > 50:
            return False, "Slug too long (maximum 50 characters)."
        
        # Then check if exists on Pepper.pl
        result = await scraper.get_group_deals(slug, limit=1)
        if result["success"] and result["deals"]:
            return True, None
        return False, f"Category '{slug}' not found on Pepper.pl"

    async def validate_channel_permissions(
        self, bot: discord.Client, channel: discord.TextChannel
    ) -> tuple[bool, Optional[str]]:
        """Validate bot has necessary permissions in target channel."""
        permissions = channel.permissions_for(channel.guild.me)
        if not permissions.send_messages:
            return False, f"Missing 'Send Messages' permission in {channel.mention}"
        if not permissions.embed_links:
            return False, f"Missing 'Embed Links' permission in {channel.mention}"
        return True, None

    async def parse_schedule(
        self, frequency: str, time: str, day: str = None, date: int = None
    ) -> tuple[bool, Optional[Dict], Optional[str]]:
        """Parse and validate schedule configuration."""
        
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
        """
        IMPROVED: Check if category should run now with better time matching.
        Uses a time window approach to avoid missing scheduled runs.
        """
        now = datetime.datetime.now()
        
        # Parse scheduled time
        schedule_time_parts = category['schedule_time'].split(':')
        schedule_hour = int(schedule_time_parts[0])
        schedule_minute = int(schedule_time_parts[1])
        
        # Build the scheduled datetime for today
        scheduled_today = now.replace(
            hour=schedule_hour, 
            minute=schedule_minute, 
            second=0, 
            microsecond=0
        )
        
        # IMPROVED: Check if we're within 2-minute window of scheduled time
        # This prevents missing runs if task runs at 08:59 instead of 09:00
        time_diff_seconds = abs((now - scheduled_today).total_seconds())
        within_time_window = time_diff_seconds < 120  # 2-minute window
        
        if not within_time_window:
            return False
        
        # IMPROVED: Check if already ran recently (prevents duplicate runs)
        if category.get('last_run'):
            try:
                last_run = datetime.datetime.fromisoformat(category['last_run'])
                minutes_since_last_run = (now - last_run).total_seconds() / 60
                
                # If ran within last 30 minutes, skip
                if minutes_since_last_run < 30:
                    return False
            except (ValueError, TypeError):
                # Invalid last_run timestamp, continue with check
                pass
        
        # Apply frequency-specific logic
        if category['schedule_type'] == 'daily':
            return True
        
        if category['schedule_type'] in ['weekly', 'biweekly']:
            day_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            target_day = day_map.get(category['schedule_day'])
            if target_day is None or now.weekday() != target_day:
                return False
            
            # For biweekly, check if 14 days passed since last run
            if category['schedule_type'] == 'biweekly':
                if category.get('last_run'):
                    try:
                        last_run = datetime.datetime.fromisoformat(category['last_run'])
                        days_since = (now - last_run).days
                        if days_since < 13:  # Less than 2 weeks
                            return False
                    except (ValueError, TypeError):
                        pass
            
            return True
        
        if category['schedule_type'] == 'monthly':
            return now.day == category['schedule_date']
        
        return False

    def format_schedule(self, category: Dict[str, Any]) -> str:
        """Format schedule configuration for display."""
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
        """Get emoji for category based on slug."""
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
            'moda-i-akcesoria': '👔',
            'zabawki': '🧸',
            'sport-i-wypoczynek': '⚽',
            'ksiazki': '📚',
            'zdrowie-i-uroda': '💄',
            'jedzenie-i-napoje': '🍕',
            'dom-i-meble': '🛋️',
            'tv-audio-foto': '📺',
            'auto-moto': '🚗',
        }
        return emoji_map.get(slug, '📂')