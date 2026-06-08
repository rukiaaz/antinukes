"""
Repent - Database layer
SQLite via aiosqlite. All operations are async.
"""

import os
import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from config import DB_PATH

# ── Helpers ──
def _now() -> str:
    return datetime.utcnow().isoformat()


async def _get_db() -> aiosqlite.Connection:
    """Get or create a database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


# ── Initialization ──
async def init_db():
    """Create all tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)

    await db.executescript("""
        -- Guild settings
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            log_channel INTEGER DEFAULT 0,
            mod_channel INTEGER DEFAULT 0,
            welcome_channel INTEGER DEFAULT 0,
            farewell_channel INTEGER DEFAULT 0,
            autorole INTEGER DEFAULT 0,
            punishment TEXT DEFAULT 'ban',
            antinuke_enabled INTEGER DEFAULT 1,
            automod_enabled INTEGER DEFAULT 1,
            welcome_msg TEXT DEFAULT '',
            farewell_msg TEXT DEFAULT '',
            level_up_channel INTEGER DEFAULT 0,
            level_up_dm INTEGER DEFAULT 0,
            raid_mode INTEGER DEFAULT 0,
            raid_join_threshold INTEGER DEFAULT 10,
            raid_join_window INTEGER DEFAULT 10,
            raid_account_age INTEGER DEFAULT 7,
            verification_channel INTEGER DEFAULT 0
        );

        -- Raid log for history
        CREATE TABLE IF NOT EXISTS raid_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            started_at TEXT DEFAULT '',
            ended_at TEXT DEFAULT '',
            joins_detected INTEGER DEFAULT 0,
            lockdown_triggered INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0
        );

        -- Automod strikes for escalating punishments
        CREATE TABLE IF NOT EXISTS automod_strikes (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            strikes INTEGER DEFAULT 0,
            last_strike_at TEXT DEFAULT '',
            PRIMARY KEY (guild_id, user_id)
        );

        -- Whitelist: trusted users per guild
        CREATE TABLE IF NOT EXISTS whitelist (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            trust_level INTEGER DEFAULT 1,
            added_by INTEGER DEFAULT 0,
            added_at TEXT DEFAULT '',
            PRIMARY KEY (guild_id, user_id)
        );

        -- Action log (moderation + antinuke actions)
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER DEFAULT 0,
            action_type TEXT NOT NULL,
            details TEXT DEFAULT '{}',
            timestamp TEXT DEFAULT ''
        );

        -- Cached roles for rollback
        CREATE TABLE IF NOT EXISTS cached_roles (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            name TEXT DEFAULT '',
            permissions INTEGER DEFAULT 0,
            color INTEGER DEFAULT 0,
            hoist INTEGER DEFAULT 0,
            mentionable INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            json_overwrites TEXT DEFAULT '{}',
            cached_at TEXT DEFAULT '',
            PRIMARY KEY (guild_id, role_id)
        );

        -- Cached channels for rollback
        CREATE TABLE IF NOT EXISTS cached_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            name TEXT DEFAULT '',
            type INTEGER DEFAULT 0,
            category_id INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            topic TEXT DEFAULT '',
            nsfw INTEGER DEFAULT 0,
            slowmode INTEGER DEFAULT 0,
            json_overwrites TEXT DEFAULT '{}',
            cached_at TEXT DEFAULT '',
            PRIMARY KEY (guild_id, channel_id)
        );

        -- Rate tracker for antinuke rolling window
        CREATE TABLE IF NOT EXISTS rate_tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            timestamp TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_rate_tracker_lookup
            ON rate_tracker(guild_id, user_id, action_type, timestamp);

        -- Punished users (antinuke punishments)
        CREATE TABLE IF NOT EXISTS punished_users (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            punished_at TEXT DEFAULT '',
            punished_by INTEGER DEFAULT 0,
            punishment_type TEXT DEFAULT 'ban',
            PRIMARY KEY (guild_id, user_id)
        );

        -- Warnings
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            warned_by INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT ''
        );

        -- Hardbans (auto-reban on rejoin)
        CREATE TABLE IF NOT EXISTS hardbans (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            banned_by INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT '',
            PRIMARY KEY (guild_id, user_id)
        );

        -- XP / Leveling
        CREATE TABLE IF NOT EXISTS xp (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            last_message TEXT DEFAULT '',
            PRIMARY KEY (guild_id, user_id)
        );

        -- Level roles (role rewards at levels)
        CREATE TABLE IF NOT EXISTS level_roles (
            guild_id INTEGER NOT NULL,
            level INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, level)
        );

        -- XP cooldown
        CREATE TABLE IF NOT EXISTS xp_cooldown (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            last_xp TEXT DEFAULT '',
            PRIMARY KEY (guild_id, user_id)
        );

        -- AutoMod config per guild
        CREATE TABLE IF NOT EXISTS automod_config (
            guild_id INTEGER PRIMARY KEY,
            anti_spam INTEGER DEFAULT 1,
            anti_invite INTEGER DEFAULT 1,
            anti_link INTEGER DEFAULT 0,
            anti_caps INTEGER DEFAULT 1,
            anti_mention INTEGER DEFAULT 1,
            anti_emoji INTEGER DEFAULT 1,
            spam_threshold INTEGER DEFAULT 5,
            spam_window INTEGER DEFAULT 5,
            mention_limit INTEGER DEFAULT 5,
            caps_percent INTEGER DEFAULT 70,
            emoji_limit INTEGER DEFAULT 8
        );

        -- Bad words per guild
        CREATE TABLE IF NOT EXISTS bad_words (
            guild_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            PRIMARY KEY (guild_id, word)
        );

        -- Antinuke thresholds per guild per action
        CREATE TABLE IF NOT EXISTS antinuke_thresholds (
            guild_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            max_count INTEGER DEFAULT 3,
            window_seconds INTEGER DEFAULT 10,
            PRIMARY KEY (guild_id, action_type)
        );

        -- AFK
        CREATE TABLE IF NOT EXISTS afk (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            set_at TEXT DEFAULT '',
            PRIMARY KEY (guild_id, user_id)
        );

        -- Ignored channels for modules
        CREATE TABLE IF NOT EXISTS ignored_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            module TEXT DEFAULT 'all',
            PRIMARY KEY (guild_id, channel_id, module)
        );

        -- Backups metadata
        CREATE TABLE IF NOT EXISTS backups (
            backup_id TEXT PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT ''
        );

        -- Backup roles
        CREATE TABLE IF NOT EXISTS backup_roles (
            backup_id TEXT NOT NULL,
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            name TEXT DEFAULT '',
            permissions INTEGER DEFAULT 0,
            color INTEGER DEFAULT 0,
            hoist INTEGER DEFAULT 0,
            mentionable INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            json_overwrites TEXT DEFAULT '{}',
            PRIMARY KEY (backup_id, role_id)
        );

        -- Backup channels
        CREATE TABLE IF NOT EXISTS backup_channels (
            backup_id TEXT NOT NULL,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            name TEXT DEFAULT '',
            type INTEGER DEFAULT 0,
            category_id INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            topic TEXT DEFAULT '',
            nsfw INTEGER DEFAULT 0,
            slowmode INTEGER DEFAULT 0,
            json_overwrites TEXT DEFAULT '{}',
            PRIMARY KEY (backup_id, channel_id)
        );
    """)

    # Run migrations for existing database to add columns
    columns_to_add = [
        ("raid_mode", "INTEGER DEFAULT 0"),
        ("raid_join_threshold", "INTEGER DEFAULT 10"),
        ("raid_join_window", "INTEGER DEFAULT 10"),
        ("raid_account_age", "INTEGER DEFAULT 7"),
        ("verification_channel", "INTEGER DEFAULT 0"),
    ]
    for col_name, col_def in columns_to_add:
        try:
            await db.execute(f"ALTER TABLE guilds ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass

    await db.commit()
    await db.close()


async def purge_old_data():
    """Remove action_log and rate_tracker entries older than 30 days."""
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    db = await _get_db()
    await db.execute("DELETE FROM action_log WHERE timestamp < ?", (cutoff,))
    await db.execute("DELETE FROM rate_tracker WHERE timestamp < ?", (cutoff,))
    await db.commit()
    await db.close()


# ── Guild Settings ──
async def get_guild(guild_id: int) -> Dict[str, Any]:
    db = await _get_db()
    row = await db.execute(
        "SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)
    )
    row = await row.fetchone()
    if not row:
        await db.execute(
            "INSERT INTO guilds (guild_id) VALUES (?)", (guild_id,)
        )
        await db.commit()
        row = await db.execute(
            "SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)
        )
        row = await row.fetchone()
    await db.close()
    return dict(row) if row else {}


async def update_guild(guild_id: int, **kwargs):
    db = await _get_db()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [guild_id]
    await db.execute(
        f"UPDATE guilds SET {fields} WHERE guild_id = ?", values
    )
    await db.commit()
    await db.close()


# ── Whitelist ──
async def get_whitelist(guild_id: int) -> List[Dict[str, Any]]:
    db = await _get_db()
    rows = await db.execute(
        "SELECT * FROM whitelist WHERE guild_id = ?", (guild_id,)
    )
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_whitelist_entry(guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    db = await _get_db()
    row = await db.execute(
        "SELECT * FROM whitelist WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = await row.fetchone()
    await db.close()
    return dict(row) if row else None


async def add_whitelist(guild_id: int, user_id: int, trust_level: int, added_by: int):
    db = await _get_db()
    await db.execute(
        """INSERT OR REPLACE INTO whitelist
           (guild_id, user_id, trust_level, added_by, added_at)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, user_id, trust_level, added_by, _now()),
    )
    await db.commit()
    await db.close()


async def remove_whitelist(guild_id: int, user_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM whitelist WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await db.commit()
    await db.close()


# ── Rate Tracker (rolling window) ──
async def add_rate_event(guild_id: int, user_id: int, action_type: str):
    db = await _get_db()
    await db.execute(
        "INSERT INTO rate_tracker (guild_id, user_id, action_type, timestamp) VALUES (?, ?, ?, ?)",
        (guild_id, user_id, action_type, _now()),
    )
    await db.commit()
    await db.close()


async def count_rate_events(guild_id: int, user_id: int, action_type: str, window_seconds: int) -> int:
    cutoff = (datetime.utcnow() - timedelta(seconds=window_seconds)).isoformat()
    db = await _get_db()
    row = await db.execute(
        """SELECT COUNT(*) as cnt FROM rate_tracker
           WHERE guild_id = ? AND user_id = ? AND action_type = ? AND timestamp > ?""",
        (guild_id, user_id, action_type, cutoff),
    )
    row = await row.fetchone()
    await db.close()
    return row["cnt"] if row else 0


async def clear_rate_events(guild_id: int, user_id: int, action_type: str):
    db = await _get_db()
    await db.execute(
        "DELETE FROM rate_tracker WHERE guild_id = ? AND user_id = ? AND action_type = ?",
        (guild_id, user_id, action_type),
    )
    await db.commit()
    await db.close()


# ── Punished Users ──
async def add_punished_user(
    guild_id: int, user_id: int, reason: str, punished_by: int, punishment_type: str
):
    db = await _get_db()
    await db.execute(
        """INSERT OR REPLACE INTO punished_users
           (guild_id, user_id, reason, punished_at, punished_by, punishment_type)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (guild_id, user_id, reason, _now(), punished_by, punishment_type),
    )
    await db.commit()
    await db.close()


async def remove_punished_user(guild_id: int, user_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM punished_users WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await db.commit()
    await db.close()


async def get_punished_users(guild_id: int) -> List[Dict[str, Any]]:
    db = await _get_db()
    rows = await db.execute(
        "SELECT * FROM punished_users WHERE guild_id = ?", (guild_id,)
    )
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def is_punished(guild_id: int, user_id: int) -> bool:
    db = await _get_db()
    row = await db.execute(
        "SELECT 1 FROM punished_users WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = await row.fetchone()
    await db.close()
    return row is not None


# ── Warnings ──
async def add_warning(guild_id: int, user_id: int, reason: str, warned_by: int) -> int:
    db = await _get_db()
    cursor = await db.execute(
        """INSERT INTO warnings (guild_id, user_id, reason, warned_by, timestamp)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, user_id, reason, warned_by, _now()),
    )
    await db.commit()
    warn_id = cursor.lastrowid
    await db.close()
    return warn_id


async def get_warnings(guild_id: int, user_id: int) -> List[Dict[str, Any]]:
    db = await _get_db()
    rows = await db.execute(
        "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
        (guild_id, user_id),
    )
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def clear_warnings(guild_id: int, user_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await db.commit()
    await db.close()


async def get_warning_by_id(warn_id: int) -> Optional[Dict[str, Any]]:
    db = await _get_db()
    row = await db.execute(
        "SELECT * FROM warnings WHERE id = ?", (warn_id,)
    )
    row = await row.fetchone()
    await db.close()
    return dict(row) if row else None


# ── Hardbans ──
async def add_hardban(guild_id: int, user_id: int, reason: str, banned_by: int):
    db = await _get_db()
    await db.execute(
        """INSERT OR REPLACE INTO hardbans
           (guild_id, user_id, reason, banned_by, timestamp)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, user_id, reason, banned_by, _now()),
    )
    await db.commit()
    await db.close()


async def remove_hardban(guild_id: int, user_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM hardbans WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await db.commit()
    await db.close()


async def is_hardbanned(guild_id: int, user_id: int) -> bool:
    db = await _get_db()
    row = await db.execute(
        "SELECT 1 FROM hardbans WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = await row.fetchone()
    await db.close()
    return row is not None


# ── Role / Channel Cache ──
async def cache_role(guild_id: int, role):
    """Cache a single role."""
    db = await _get_db()
    overwrites = {}
    for target, perm in role.overwrites.items():
        overwrites[str(target.id)] = {
            "type": "member" if isinstance(target, type(role.guild.me)) else "role",
            "allow": perm.pair()[0].value,
            "deny": perm.pair()[1].value,
        }
    await db.execute(
        """INSERT OR REPLACE INTO cached_roles
           (guild_id, role_id, name, permissions, color, hoist, mentionable, position, json_overwrites, cached_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            guild_id, role.id, role.name, role.permissions.value,
            role.color.value, int(role.hoist), int(role.mentionable),
            role.position, json.dumps(overwrites), _now(),
        ),
    )
    await db.commit()
    await db.close()


async def cache_channel(guild_id: int, channel):
    """Cache a single channel."""
    db = await _get_db()
    overwrites = {}
    for target, perm in channel.overwrites.items():
        overwrites[str(target.id)] = {
            "type": "member" if hasattr(target, "guild") else "role",
            "allow": perm.pair()[0].value,
            "deny": perm.pair()[1].value,
        }
    await db.execute(
        """INSERT OR REPLACE INTO cached_channels
           (guild_id, channel_id, name, type, category_id, position, topic, nsfw, slowmode, json_overwrites, cached_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            guild_id, channel.id, channel.name, channel.type.value,
            channel.category_id or 0, channel.position,
            getattr(channel, "topic", "") or "", int(getattr(channel, "nsfw", False)),
            getattr(channel, "slowmode_delay", 0), json.dumps(overwrites), _now(),
        ),
    )
    await db.commit()
    await db.close()


async def get_cached_roles(guild_id: int) -> List[Dict[str, Any]]:
    db = await _get_db()
    rows = await db.execute(
        "SELECT * FROM cached_roles WHERE guild_id = ?", (guild_id,)
    )
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_cached_channels(guild_id: int) -> List[Dict[str, Any]]:
    db = await _get_db()
    rows = await db.execute(
        "SELECT * FROM cached_channels WHERE guild_id = ?", (guild_id,)
    )
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def delete_cached_role(guild_id: int, role_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM cached_roles WHERE guild_id = ? AND role_id = ?",
        (guild_id, role_id),
    )
    await db.commit()
    await db.close()


async def delete_cached_channel(guild_id: int, channel_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM cached_channels WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id),
    )
    await db.commit()
    await db.close()


# ── XP / Leveling ──
async def get_xp(guild_id: int, user_id: int) -> Dict[str, Any]:
    db = await _get_db()
    row = await db.execute(
        "SELECT * FROM xp WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = await row.fetchone()
    if not row:
        await db.execute(
            "INSERT INTO xp (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        await db.commit()
        row = await db.execute(
            "SELECT * FROM xp WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        row = await row.fetchone()
    await db.close()
    return dict(row) if row else {"xp": 0, "level": 0}


async def add_xp(guild_id: int, user_id: int, amount: int) -> Tuple[int, int]:
    """Add XP, return (new_level, did_level_up)."""
    db = await _get_db()
    row = await db.execute(
        "SELECT xp, level FROM xp WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = await row.fetchone()
    if not row:
        await db.execute(
            "INSERT INTO xp (guild_id, user_id, xp) VALUES (?, ?, ?)",
            (guild_id, user_id, amount),
        )
        new_xp = amount
        old_level = 0
    else:
        new_xp = row["xp"] + amount
        old_level = row["level"]
        await db.execute(
            "UPDATE xp SET xp = ?, last_message = ? WHERE guild_id = ? AND user_id = ?",
            (new_xp, _now(), guild_id, user_id),
        )

    new_level = int((new_xp ** 0.5) * 0.1)
    if new_level > old_level:
        await db.execute(
            "UPDATE xp SET level = ? WHERE guild_id = ? AND user_id = ?",
            (new_level, guild_id, user_id),
        )

    await db.commit()
    await db.close()
    return new_level, new_level > old_level


async def set_xp_level(guild_id: int, user_id: int, level: int):
    xp_needed = int((level / 0.1) ** 2)
    db = await _get_db()
    await db.execute(
        """INSERT INTO xp (guild_id, user_id, xp, level)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET xp=excluded.xp, level=excluded.level""",
        (guild_id, user_id, xp_needed, level),
    )
    await db.commit()
    await db.close()


async def reset_xp(guild_id: int, user_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM xp WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await db.commit()
    await db.close()


async def get_leaderboard(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    db = await _get_db()
    rows = await db.execute(
        "SELECT * FROM xp WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
        (guild_id, limit),
    )
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


# ── XP Cooldown ──
async def get_xp_cooldown(guild_id: int, user_id: int) -> Optional[str]:
    db = await _get_db()
    row = await db.execute(
        "SELECT last_xp FROM xp_cooldown WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = await row.fetchone()
    await db.close()
    return row["last_xp"] if row else None


async def set_xp_cooldown(guild_id: int, user_id: int):
    db = await _get_db()
    await db.execute(
        """INSERT INTO xp_cooldown (guild_id, user_id, last_xp)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET last_xp=excluded.last_xp""",
        (guild_id, user_id, _now()),
    )
    await db.commit()
    await db.close()


# ── Level Roles ──
async def get_level_roles(guild_id: int) -> List[Dict[str, Any]]:
    db = await _get_db()
    rows = await db.execute(
        "SELECT * FROM level_roles WHERE guild_id = ? ORDER BY level ASC",
        (guild_id,),
    )
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def add_level_role(guild_id: int, level: int, role_id: int):
    db = await _get_db()
    await db.execute(
        """INSERT INTO level_roles (guild_id, level, role_id)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, level) DO UPDATE SET role_id=excluded.role_id""",
        (guild_id, level, role_id),
    )
    await db.commit()
    await db.close()


async def remove_level_role(guild_id: int, level: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM level_roles WHERE guild_id = ? AND level = ?",
        (guild_id, level),
    )
    await db.commit()
    await db.close()


# ── AutoMod ──
async def get_automod_config(guild_id: int) -> Dict[str, Any]:
    db = await _get_db()
    row = await db.execute(
        "SELECT * FROM automod_config WHERE guild_id = ?", (guild_id,)
    )
    row = await row.fetchone()
    if not row:
        from config import DEFAULT_AUTOMOD
        await db.execute(
            """INSERT INTO automod_config
               (guild_id, anti_spam, anti_invite, anti_link, anti_caps, anti_mention, anti_emoji,
                spam_threshold, spam_window, mention_limit, caps_percent, emoji_limit)
               VALUES (?, 1, 1, 0, 1, 1, 1, 5, 5, 5, 70, 8)""",
            (guild_id,),
        )
        await db.commit()
        row = await db.execute(
            "SELECT * FROM automod_config WHERE guild_id = ?", (guild_id,)
        )
        row = await row.fetchone()
    await db.close()
    return dict(row) if row else {}


async def update_automod_config(guild_id: int, **kwargs):
    db = await _get_db()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [guild_id]
    await db.execute(
        f"UPDATE automod_config SET {fields} WHERE guild_id = ?", values
    )
    await db.commit()
    await db.close()


# ── Bad Words ──
async def get_bad_words(guild_id: int) -> List[str]:
    db = await _get_db()
    rows = await db.execute(
        "SELECT word FROM bad_words WHERE guild_id = ?", (guild_id,)
    )
    rows = await rows.fetchall()
    await db.close()
    return [r["word"] for r in rows]


async def add_bad_word(guild_id: int, word: str):
    db = await _get_db()
    await db.execute(
        "INSERT OR IGNORE INTO bad_words (guild_id, word) VALUES (?, ?)",
        (guild_id, word.lower()),
    )
    await db.commit()
    await db.close()


async def remove_bad_word(guild_id: int, word: str):
    db = await _get_db()
    await db.execute(
        "DELETE FROM bad_words WHERE guild_id = ? AND word = ?",
        (guild_id, word.lower()),
    )
    await db.commit()
    await db.close()


# ── Antinuke Thresholds ──
async def get_antinuke_threshold(guild_id: int, action_type: str) -> Tuple[int, int]:
    from config import DEFAULT_ANTINUKE_THRESHOLDS
    db = await _get_db()
    row = await db.execute(
        "SELECT max_count, window_seconds FROM antinuke_thresholds WHERE guild_id = ? AND action_type = ?",
        (guild_id, action_type),
    )
    row = await row.fetchone()
    await db.close()
    if row:
        return row["max_count"], row["window_seconds"]
    defaults = DEFAULT_ANTINUKE_THRESHOLDS.get(action_type, (3, 10))
    return defaults


async def set_antinuke_threshold(guild_id: int, action_type: str, max_count: int, window_seconds: int):
    db = await _get_db()
    await db.execute(
        """INSERT OR REPLACE INTO antinuke_thresholds
           (guild_id, action_type, max_count, window_seconds)
           VALUES (?, ?, ?, ?)""",
        (guild_id, action_type, max_count, window_seconds),
    )
    await db.commit()
    await db.close()


# ── AFK ──
async def set_afk(guild_id: int, user_id: int, reason: str):
    db = await _get_db()
    await db.execute(
        """INSERT OR REPLACE INTO afk (guild_id, user_id, reason, set_at)
           VALUES (?, ?, ?, ?)""",
        (guild_id, user_id, reason, _now()),
    )
    await db.commit()
    await db.close()


async def get_afk(guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    db = await _get_db()
    row = await db.execute(
        "SELECT * FROM afk WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = await row.fetchone()
    await db.close()
    return dict(row) if row else None


async def remove_afk(guild_id: int, user_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM afk WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await db.commit()
    await db.close()


# ── Ignored Channels ──
async def get_ignored_channels(guild_id: int, module: str = "all") -> List[int]:
    db = await _get_db()
    rows = await db.execute(
        """SELECT channel_id FROM ignored_channels
           WHERE guild_id = ? AND (module = ? OR module = 'all')""",
        (guild_id, module),
    )
    rows = await rows.fetchall()
    await db.close()
    return [r["channel_id"] for r in rows]


async def add_ignored_channel(guild_id: int, channel_id: int, module: str = "all"):
    db = await _get_db()
    await db.execute(
        "INSERT OR IGNORE INTO ignored_channels (guild_id, channel_id, module) VALUES (?, ?, ?)",
        (guild_id, channel_id, module),
    )
    await db.commit()
    await db.close()


async def remove_ignored_channel(guild_id: int, channel_id: int, module: str = "all"):
    db = await _get_db()
    await db.execute(
        "DELETE FROM ignored_channels WHERE guild_id = ? AND channel_id = ? AND module = ?",
        (guild_id, channel_id, module),
    )
    await db.commit()
    await db.close()


# ── Action Log ──
async def log_action(guild_id: int, action_type: str, user_id: int = 0, details: dict = None):
    db = await _get_db()
    await db.execute(
        """INSERT INTO action_log (guild_id, user_id, action_type, details, timestamp)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, user_id, action_type, json.dumps(details or {}), _now()),
    )
    await db.commit()
    await db.close()


# ── Automod Strikes ──
async def get_strikes(guild_id: int, user_id: int) -> int:
    db = await _get_db()
    row = await db.execute(
        "SELECT strikes FROM automod_strikes WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = await row.fetchone()
    await db.close()
    return row["strikes"] if row else 0


async def add_strike(guild_id: int, user_id: int) -> int:
    new_strikes = await get_strikes(guild_id, user_id) + 1
    db = await _get_db()
    await db.execute(
        """INSERT INTO automod_strikes (guild_id, user_id, strikes, last_strike_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET strikes = excluded.strikes, last_strike_at = excluded.last_strike_at""",
        (guild_id, user_id, new_strikes, _now()),
    )
    await db.commit()
    await db.close()
    return new_strikes


async def clear_strikes(guild_id: int, user_id: int):
    db = await _get_db()
    await db.execute(
        "DELETE FROM automod_strikes WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await db.commit()
    await db.close()


# ── Raid Log ──
async def log_raid_start(guild_id: int, joins_detected: int, lockdown_triggered: int) -> int:
    db = await _get_db()
    cursor = await db.execute(
        """INSERT INTO raid_log (guild_id, started_at, joins_detected, lockdown_triggered)
           VALUES (?, ?, ?, ?)""",
        (guild_id, _now(), joins_detected, lockdown_triggered),
    )
    await db.commit()
    raid_id = cursor.lastrowid
    await db.close()
    return raid_id


async def log_raid_end(raid_id: int, resolved: int):
    db = await _get_db()
    await db.execute(
        "UPDATE raid_log SET ended_at = ?, resolved = ? WHERE id = ?",
        (_now(), resolved, raid_id),
    )
    await db.commit()
    await db.close()


# ── Backups ──
async def save_backup(guild_id: int, backup_id: str, name: str, roles: list, channels: list):
    db = await _get_db()
    # Insert backup metadata
    await db.execute(
        "INSERT INTO backups (backup_id, guild_id, name, created_at) VALUES (?, ?, ?, ?)",
        (backup_id, guild_id, name, _now())
    )

    # Insert backup roles
    for r in roles:
        overwrites = {}
        for target, perm in r.overwrites.items():
            overwrites[str(target.id)] = {
                "type": "member" if isinstance(target, type(r.guild.me)) else "role",
                "allow": perm.pair()[0].value,
                "deny": perm.pair()[1].value,
            }
        await db.execute(
            """INSERT OR REPLACE INTO backup_roles
               (backup_id, guild_id, role_id, name, permissions, color, hoist, mentionable, position, json_overwrites)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                backup_id, guild_id, r.id, r.name, r.permissions.value,
                r.color.value, int(r.hoist), int(r.mentionable),
                r.position, json.dumps(overwrites)
            )
        )

    # Insert backup channels
    for ch in channels:
        overwrites = {}
        for target, perm in ch.overwrites.items():
            overwrites[str(target.id)] = {
                "type": "member" if hasattr(target, "guild") else "role",
                "allow": perm.pair()[0].value,
                "deny": perm.pair()[1].value,
            }
        await db.execute(
            """INSERT OR REPLACE INTO backup_channels
               (backup_id, guild_id, channel_id, name, type, category_id, position, topic, nsfw, slowmode, json_overwrites)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                backup_id, guild_id, ch.id, ch.name, ch.type.value,
                ch.category_id or 0, ch.position,
                getattr(ch, "topic", "") or "", int(getattr(ch, "nsfw", False)),
                getattr(ch, "slowmode_delay", 0), json.dumps(overwrites)
            )
        )

    await db.commit()
    await db.close()


async def get_backups(guild_id: int) -> list:
    db = await _get_db()
    rows = await db.execute("SELECT * FROM backups WHERE guild_id = ? ORDER BY created_at DESC", (guild_id,))
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_backup(guild_id: int, backup_id: str) -> dict | None:
    db = await _get_db()
    row = await db.execute("SELECT * FROM backups WHERE guild_id = ? AND backup_id = ?", (guild_id, backup_id))
    row = await row.fetchone()
    await db.close()
    return dict(row) if row else None


async def get_backup_roles(backup_id: str) -> list:
    db = await _get_db()
    rows = await db.execute("SELECT * FROM backup_roles WHERE backup_id = ? ORDER BY position ASC", (backup_id,))
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_backup_channels(backup_id: str) -> list:
    db = await _get_db()
    rows = await db.execute("SELECT * FROM backup_channels WHERE backup_id = ? ORDER BY position ASC", (backup_id,))
    rows = await rows.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def delete_backup(guild_id: int, backup_id: str):
    db = await _get_db()
    await db.execute("DELETE FROM backups WHERE guild_id = ? AND backup_id = ?", (guild_id, backup_id))
    await db.execute("DELETE FROM backup_roles WHERE backup_id = ?", (backup_id,))
    await db.execute("DELETE FROM backup_channels WHERE backup_id = ?", (backup_id,))
    await db.commit()
    await db.close()
