# Repent — Advanced Discord Antinuke & Security Bot

A production-ready Discord bot built as a direct competitor to Mataru, Auth.gg, and other top-tier antinuke/security bots. Designed to be impossible to bypass via selfbots, nuke bots, or compromised trusted users.

---

## Features

| Module | Description |
|--------|-------------|
| **Antinuke** | Audit-log-based detection for mass ban/kick, mass channel/role delete, dangerous role updates, webhook spam, server updates, unauthorized bot adds, owner transfer attempts |
| **Moderation** | Full slash command suite: ban, unban, kick, timeout, warn, purge, lock, unlock, slowmode, nick, role management, hardban |
| **AutoMod** | Anti-spam, anti-mass-mention, anti-invite, anti-link, anti-caps, anti-emoji-spam, bad word filter |
| **Logging** | Comprehensive event logging: member join/leave/ban, message edit/delete, channel/role changes, voice, server updates, invites |
| **Welcome/Farewell** | Custom join/leave messages with variables, autorole assignment |
| **Leveling** | XP per message, rank cards, leaderboard, level roles, admin overrides |
| **Utility** | userinfo, serverinfo, avatar, roleinfo, channelinfo, ping, uptime, afk, botinfo |
| **Configuration** | Interactive setup wizard, whitelist management, per-guild thresholds, punished user management |

---

## Installation

### 1. Clone / Download

```bash
git clone <repo-url>
cd repent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create Environment File

Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_bot_token_here
OWNER_ID=your_discord_user_id_here
```

> **Never share your token or .env file.**

### 4. Run the Bot

```bash
python main.py
```

---

## Required Bot Intents

All intents are required for full functionality:

| Intent | Purpose |
|--------|---------|
| `Guilds` | Server management |
| `Members` | Member tracking, welcome, antinuke |
| `Bans` | Ban/unban logging |
| `Emojis` | Emoji count |
| `Integrations` | Webhook tracking |
| `Webhooks` | Webhook antinuke |
| `Invites` | Invite tracking |
| `Voice States` | Voice logging |
| `Presences` | Status tracking |
| `Guild Messages` | Automod, leveling, AFK |
| `Guild Message Reactions` | Reaction tracking |
| `Guild Message Typing` | Typing indicators |
| `Message Content` | Automod content scanning |
| `Guild Scheduled Events` | Event tracking |
| `Auto Moderation` | Discord native automod |
| `Auto Moderation Configuration` | Automod config |
| `Auto Moderation Execution` | Automod actions |

**Enable all intents in the [Discord Developer Portal](https://discord.com/developers/applications) > Bot > Privileged Gateway Intents.**

---

## Required Bot Permissions

**Administrator** is strongly recommended for the bot to function properly, especially for:
- Antinuke rollback (restoring deleted channels/roles)
- Punishing attackers (ban/kick/strip/timeout)
- Channel/role management
- Webhook deletion

### Minimum Permissions (not recommended)
If you cannot grant Administrator, these are the minimum required permissions:

- `Ban Members`
- `Kick Members`
- `Manage Channels`
- `Manage Roles`
- `Manage Messages`
- `Manage Nicknames`
- `Manage Webhooks`
- `Moderate Members` (timeout)
- `View Audit Log`
- `Read Messages / View Channels`
- `Send Messages`
- `Manage Threads`
- `Read Message History`
- `Add Reactions`
- `Use Slash Commands`

---

## Invite URL

Generate an invite link with Administrator permission:

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

Replace `YOUR_BOT_CLIENT_ID` with your bot's application ID.

Or use the `/invite` command after the bot is running.

---

## Quick Setup

After inviting the bot to your server:

1. **Run the setup wizard:**
   ```
   /setup
   ```

2. **Set log channel:**
   ```
   /config logchannel #your-log-channel
   ```

3. **Configure punishment:**
   ```
   /config punishment ban
   ```

4. **Enable antinuke:**
   ```
   /antinuke enable
   ```

5. **Whitelist yourself (required):**
   ```
   /whitelist add @yourself 2
   ```
   > Trust level `2` = full exemption. Level `1` = partial (channel/role limits only).

6. **Enable automod:**
   ```
   /automod enable
   ```

7. **View all settings:**
   ```
   /config view
   ```

---

## Antinuke Protection Details

All detection uses `on_audit_log_entry_create` — the only reliable method that cannot be bypassed by selfbots or nukers who avoid sending events.

| Threat | Detection Method | Response |
|--------|-----------------|----------|
| Mass Ban | Audit log rolling window | Ban attacker, log to owner |
| Mass Kick | Audit log rolling window | Ban attacker, log to owner |
| Mass Channel Delete | Audit log rolling window | Ban attacker, log to owner |
| Mass Channel Create | Audit log rolling window | Ban attacker |
| Mass Role Delete | Audit log rolling window | Ban attacker |
| Mass Role Create | Audit log rolling window | Ban attacker |
| Admin Role Grant | Audit log permission change | Ban attacker |
| Server Update | Audit log guild update | Ban attacker |
| Webhook Spam | Audit log webhook create | Ban attacker + auto-delete webhooks |
| Unauthorized Bot Add | Audit log bot_add | Kick bot + ban adder |
| Owner Transfer | Audit log (always blocked) | Always blocked, always punished |

### Punishment Types

| Type | Effect |
|------|--------|
| `ban` | Immediate permanent ban |
| `kick` | Kick from server |
| `strip` | Remove all roles + deafen |
| `timeout` | 28-day timeout (max Discord allows) |

---

## Command Reference

### Moderation
| Command | Description | Permission |
|---------|-------------|------------|
| `/ban @user [reason] [delete_days]` | Ban a user | Ban Members |
| `/unban user_id [reason]` | Unban by ID | Ban Members |
| `/kick @user [reason]` | Kick a user | Kick Members |
| `/timeout @user duration [reason]` | Timeout user (e.g., 10m, 1h, 1d) | Moderate Members |
| `/untimeout @user` | Remove timeout | Moderate Members |
| `/warn @user [reason]` | Issue a warning | Manage Messages |
| `/warnings @user` | List warnings | Manage Messages |
| `/clearwarns @user` | Clear all warnings | Manage Messages |
| `/purge amount` | Bulk delete messages | Manage Messages |
| `/purgeuser @user amount` | Purge messages by user | Manage Messages |
| `/lock [channel]` | Lock channel | Manage Channels |
| `/unlock [channel]` | Unlock channel | Manage Channels |
| `/slowmode seconds [channel]` | Set slowmode | Manage Channels |
| `/nick @user [nickname]` | Change nickname | Manage Nicknames |
| `/roleadd @user @role` | Add role | Manage Roles |
| `/roleremove @user @role` | Remove role | Manage Roles |
| `/hardban @user [reason]` | Ban + auto-reban on rejoin | Ban Members |
| `/unhardban user_id` | Remove from hardban list | Ban Members |

### Configuration
| Command | Description |
|---------|-------------|
| `/setup` | Interactive setup wizard |
| `/config view` | View all settings |
| `/config logchannel #channel` | Set log channel |
| `/config punishment type` | Set antinuke punishment |
| `/config threshold action count seconds` | Set antinuke thresholds |
| `/antinuke enable/disable/status` | Manage antinuke |
| `/automod enable/disable` | Toggle automod |
| `/whitelist add @user level` | Whitelist a user |
| `/whitelist remove @user` | Remove from whitelist |
| `/whitelist list` | List whitelisted users |
| `/pardon @user` | Remove from punished list |

### AutoMod
| Command | Description |
|---------|-------------|
| `/badword add word` | Add bad word |
| `/badword remove word` | Remove bad word |
| `/badword list` | List bad words |
| `/ignore #channel module` | Ignore channel |
| `/unignore #channel` | Unignore channel |

### Welcome
| Command | Description |
|---------|-------------|
| `/welcome set #channel` | Set welcome channel |
| `/welcome message text` | Set welcome message |
| `/welcome autorole @role` | Set autorole |
| `/farewell set #channel` | Set farewell channel |
| `/farewell message text` | Set farewell message |

### Leveling
| Command | Description |
|---------|-------------|
| `/rank [@user]` | Show rank card |
| `/leaderboard` | Top 20 XP leaderboard |
| `/setlevel @user level` | Set user level |
| `/resetxp @user` | Reset user XP |
| `/levelrole add level @role` | Add level reward |
| `/levelrole remove level` | Remove level reward |
| `/levelrole list` | List level roles |

### Utility
| Command | Description |
|---------|-------------|
| `/userinfo [@user]` | User information |
| `/serverinfo` | Server information |
| `/avatar [@user]` | Show avatar |
| `/roleinfo @role` | Role information |
| `/channelinfo [channel]` | Channel information |
| `/ping` | Bot latency |
| `/uptime` | Bot uptime |
| `/afk [reason]` | Set AFK status |
| `/botinfo` | Bot statistics |
| `/invite` | Bot invite link |

### Antinuke
| Command | Description |
|---------|-------------|
| `/restore type` | Restore channels/roles from cache |
| `/punished list` | List punished users |
| `/punished pardon @user` | Pardon a user |

---

## Database

Repent uses **SQLite** via `aiosqlite` for persistence. The database file is created at `data/repent.db` on first run.

### Tables

| Table | Purpose |
|-------|---------|
| `guilds` | Per-guild settings |
| `whitelist` | Trusted users with trust levels |
| `action_log` | Audit trail of all actions |
| `cached_roles` | Role snapshots for rollback |
| `cached_channels` | Channel snapshots for rollback |
| `rate_tracker` | Rolling window rate tracking |
| `punished_users` | Antinuke punished users |
| `warnings` | User warnings |
| `hardbans` | Persistent ban list |
| `xp` | User XP and levels |
| `level_roles` | Level reward roles |
| `automod_config` | Per-guild automod settings |
| `bad_words` | Filtered words |
| `antinuke_thresholds` | Per-action thresholds |
| `afk` | AFK status |
| `ignored_channels` | Channel ignore list |

---

## Anti-Bypass Design

Repent is built from the ground up to be unbypassable:

1. **Audit Log Only** — All detection uses `on_audit_log_entry_create`, not client events like `on_member_ban` which can be avoided by selfbots.

2. **Database Rate Windows** — Rate tracking uses SQLite timestamps, not in-memory dictionaries. Survives bot restarts mid-nuke.

3. **Hardcoded Owner** — The owner ID is loaded from `config.py` (environment variable), never from the database. Prevents DB tampering.

4. **Whitelist Check Order** — Whitelist verification happens BEFORE any action is taken, inside the audit log handler itself.

5. **Hardban Persistence** — Hardbanned users are checked on EVERY `on_member_join` and automatically re-banned.

6. **< 2 Second Response** — All punishment actions use `asyncio.gather` and execute in under 2 seconds from detection.

7. **Owner DM Fallback** — If the bot lacks permissions to punish, the server owner is DM'd immediately.

---

## File Structure

```
repent/
├── main.py                  # Bot entry, cog loader, cache loop
├── config.py                # TOKEN, OWNER_ID, defaults, colors
├── database.py              # Full DB schema + async helpers
├── utils/
│   ├── embeds.py            # Embed builder helpers
│   ├── checks.py            # Permission decorators
│   ├── paginator.py         # Leaderboard pagination
│   └── cache.py             # Role/channel snapshot logic
├── cogs/
│   ├── antinuke.py          # Audit log listeners + punishment + rollback
│   ├── automod.py           # Message-based automod
│   ├── moderation.py        # All mod slash commands
│   ├── logging.py           # Event logging
│   ├── welcome.py           # Join/leave events + autorole
│   ├── leveling.py          # XP, rank, leaderboard
│   ├── utility.py           # Info, ping, afk, etc.
│   └── config.py            # Configuration commands
├── requirements.txt
└── README.md
```

---

## Tech Stack

- **Python 3.9+**
- **discord.py 2.3.2+** — Discord API wrapper
- **aiosqlite 0.19.0+** — Async SQLite
- **python-dotenv 1.0.0+** — Environment variable management

---

## Legal & Compliance

This bot includes comprehensive legal documentation for Discord verification and compliance:

### Legal Documents
- **[Privacy Policy](PRIVACY_POLICY.md)** - Detailed information about data collection, usage, and user rights
- **[Terms of Service](TERMS_OF_SERVICE.md)** - Acceptable use policy and legal terms
- **[Legal Compliance Guide](LEGAL_COMPLIANCE_GUIDE.md)** - Instructions for Discord bot verification
- **[Quick Legal Reference](QUICK_LEGAL_REFERENCE.md)** - User-friendly summary of legal terms

### Discord Bot Verification
Before submitting for Discord verification, you must:
1. Update placeholder information in the legal documents with your actual contact details
2. Host the documents publicly (website, GitHub, etc.)
3. Add the URLs to your Discord Developer Portal application
4. Ensure data collection is accurately disclosed in the Discord Developer Portal
5. Review the [Legal Compliance Guide](LEGAL_COMPLIANCE_GUIDE.md) for detailed instructions

### Data Collection Disclosure
This bot collects the following data types (must be disclosed in Discord Developer Portal):
- **Guilds** - Server names, IDs, member counts, and configuration
- **Guild Members** - User IDs, usernames, and basic profile information
- **Messages** - Message content for moderation and security purposes
- **Channels** - Channel names, IDs, types, and permissions
- **Roles** - Role names, IDs, colors, and permissions
- **Audit Logs** - Audit log entries for security monitoring
- **Voice States** - Voice channel participation for security monitoring

### User Data Rights
- Users can request data deletion by removing the bot from their server
- Data is automatically deleted according to the retention policy specified in the Privacy Policy
- Contact information is provided for privacy inquiries and data requests

---

## License

MIT License — Free for personal and commercial use. Attribution appreciated.

---

## Support

For issues, feature requests, or questions, contact the bot owner (`OWNER_ID` in `.env`).
