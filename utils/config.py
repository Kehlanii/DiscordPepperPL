class Config:
    # Colors
    COLOR_PRIMARY = 0xFF6B35  # Pepper Orange
    COLOR_SUCCESS = 0x00FF00  # Green
    COLOR_ERROR = 0xFF0000  # Red
    COLOR_WARNING = 0xFFA500  # Orange
    COLOR_NEUTRAL = 0x808080  # Grey

    # Limits
    DEFAULT_SEARCH_LIMIT = 7
    MAX_CLEAN_LIMIT = 100

    # Timeouts
    REQUEST_TIMEOUT = 15

    # Scraper
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    FLIGHT_CATEGORY_URL = "https://www.pepper.pl/grupa/bilety-lotnicze"
    GROUP_URL_TEMPLATE = "https://www.pepper.pl/grupa/{}"

    # Discord
    FLIGHT_CHANNEL_ID = 1448267942826475574
    FLIGHT_SCHEDULE_HOUR = 8  # 8:00 AM

    # Storage
    SENT_DEALS_FILE = "sent_flights.json"
    ALERTS_FILE = "alerts.json"

    # Watcher
    WATCH_INTERVAL_MINUTES = 15
