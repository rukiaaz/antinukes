"""
Repent - Configuration file
All constants and defaults for the bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Bot Identity ──
TOKEN = os.getenv("DISCORD_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
BOT_NAME = "Repent"
VERSION = "1.0.0"

# ── Default Antinuke Thresholds ──
# Format: (max_count, window_seconds)
DEFAULT_ANTINUKE_THRESHOLDS = {
    "ban": (3, 10),
    "kick": (3, 10),
    "channel_delete": (3, 10),
    "channel_create": (3, 10),
    "role_delete": (3, 10),
    "role_create": (3, 10),
    "role_update": (3, 10),
    "webhook_create": (3, 10),
    "webhook_delete": (3, 10),
    "server_update": (3, 10),
    "bot_add": (2, 60),
    "emoji_delete": (3, 10),
    "sticker_delete": (3, 10),
}

# ── Dangerous Permissions for Permission Escalation Detection ──
DANGEROUS_PERMISSIONS = [
    "administrator",
    "ban_members",
    "kick_members",
    "manage_roles",
    "manage_channels",
    "manage_guild",
    "manage_webhooks"
]

# ── Raid Defaults ──
RAID_JOIN_THRESHOLD = 10
RAID_JOIN_WINDOW = 10
RAID_ACCOUNT_AGE = 7  # days

# ── Punishment Types ──
PUNISHMENT_TYPES = ["ban", "kick", "strip", "timeout"]
DEFAULT_PUNISHMENT = "ban"

# ── Embed Colors ──
COLOR_ALERT = 0xFF4444    # Danger / Punishment / Antinuke trigger
COLOR_SUCCESS = 0x44FF88  # Success / Enabled
COLOR_INFO = 0x4488FF     # Info / Status
COLOR_WARNING = 0xFFAA00  # Warning / Caution

# ── Leveling ──
DEFAULT_XP_MIN = 15
DEFAULT_XP_MAX = 25
DEFAULT_XP_COOLDOWN = 60  # seconds between XP gains per user
LEVEL_UP_FORMULA = "floor(0.1 * sqrt(xp))"

# ── AutoMod Defaults ──
DEFAULT_AUTOMOD = {
    "anti_spam": True,
    "anti_invite": True,
    "anti_link": False,
    "anti_caps": True,
    "anti_mention": True,
    "anti_emoji": True,
    "spam_threshold": 5,
    "spam_window": 5,
    "mention_limit": 5,
    "caps_percent": 70,
    "emoji_limit": 8,
}

# ── Cache ──
CACHE_AUTO_SAVE_INTERVAL = 120  # seconds (reduced from 300 for faster restore)

# ── Logging ──
MAX_LOG_FIELDS = 4

# ── Database ──
DB_PATH = "data/repent.db"
