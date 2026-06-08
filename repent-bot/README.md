# Repent

A fast, strict, professional Discord anti-nuke bot. Security first. No bloat.

## Philosophy

- Security first
- Fast response
- Minimal setup
- No AI features
- No economy
- No leveling
- No fun commands
- No dashboards
- No bloated embeds
- Direct, clean, professional

## Features

### Anti-Nuke Modules

Repent protects against the following attack vectors:

| Module | Description |
|--------|-------------|
| `channelDelete` | Mass channel deletion |
| `channelCreate` | Mass channel creation spam |
| `channelUpdate` | Unauthorized channel modifications |
| `categoryDelete` | Category deletion attacks |
| `categoryUpdate` | Unauthorized category modifications |
| `roleDelete` | Mass role deletion |
| `roleCreate` | Unauthorized role creation |
| `roleUpdate` | Role modifications including permission escalation |
| `permissionEscalation` | Administrator/dangerous permission grants |
| `webhookCreate` | Unauthorized webhook creation |
| `webhookDelete` | Webhook deletion attacks |
| `webhookUpdate` | Unauthorized webhook modifications |
| `massBan` | Mass member bans |
| `massKick` | Mass member kicks |
| `massTimeout` | Mass member timeouts |
| `botAdd` | Unauthorized bot invitations |
| `emojiDelete` | Mass emoji deletion |
| `emojiCreate` | Unauthorized emoji creation |
| `stickerDelete` | Mass sticker deletion |
| `stickerCreate` | Unauthorized sticker creation |
| `serverUpdate` | Unauthorized server setting changes |

### Detection System

- Uses Discord audit logs for executor identification
- Rolling time-window tracking per user per action type
- Instant punishment when thresholds are exceeded
- Pre-damage permission escalation detection
- Whitelist bypass protection

### Punishments

- **Ban** (default)
- **Kick**
- **Timeout**
- **Remove Dangerous Roles**

### Auto Recovery

Repent continuously maintains backups and automatically restores:

- Channels and categories
- Roles and permissions
- Webhooks
- Emojis and stickers
- Server settings

### Emergency Protection

- `/lockdown` - Lock all channels
- `/unlockdown` - Remove lockdown
- `/panic` - Full panic mode (lock channels, delete webhooks, freeze actions, alert owner)

## Installation

### Requirements

- Node.js 18+
- MongoDB 5.0+
- Discord Bot Token

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd repent-bot
```

2. Install dependencies:
```bash
npm install
```

3. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env`:
```env
TOKEN=your_bot_token_here
MONGODB_URI=mongodb://localhost:27017/repent
OWNER_ID=your_discord_user_id
```

4. Build:
```bash
npm run build
```

5. Start:
```bash
npm start
```

Or for development with auto-reload:
```bash
npm run dev
```

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section and create a bot
4. Enable these **Privileged Gateway Intents**:
   - Server Members Intent
   - Message Content Intent (optional, not required for Repent)
5. Copy the bot token to your `.env` file
6. Use the OAuth2 URL Generator with `bot` and `applications.commands` scopes
7. Grant these permissions:
   - Administrator (recommended for full protection)
   - Or minimum: Manage Server, Manage Channels, Manage Roles, Manage Webhooks, Kick Members, Ban Members, Moderate Members, View Audit Log

## Configuration

### Initial Setup

Use `/setup` in your server. The interactive setup takes under 60 seconds:

1. Select log channel
2. Select default punishment
3. Done

### Whitelist Management

Only the **server owner** can manage the whitelist.

```
/whitelist-add user:@user
/whitelist-add role:@role
/whitelist-remove user:@user
/whitelist-remove role:@role
```

### Per-Module Configuration

```
/config module:channelDelete
```

This opens an interactive menu to toggle the module and change its punishment.

### Status Check

```
/status
```

Shows all protection modules, whitelist entries, and current mode.

### Emergency Commands

```
/lockdown     - Lock all channels
/unlockdown   - Remove lockdown
/panic        - Toggle panic mode
```

## Architecture

```
src/
  index.ts              - Entry point
  types/                - TypeScript type definitions
    index.ts
  structures/           - Core bot structures
    Repent.ts           - Main client
    ActionTracker.ts    - Rolling window action tracking
    BackupManager.ts    - Snapshot and restore system
    PunishmentHandler.ts - Punishment execution
    LogHandler.ts       - Single-channel logging
    ProtectionHandler.ts - Event listeners and command registration
  handlers/
    CommandHandler.ts   - Slash command implementations
  models/
    GuildSettings.ts    - Guild configuration persistence
    Backup.ts           - Backup data persistence
  utils/
    config.ts           - Environment and default configuration
    database.ts         - MongoDB connection
    AuditLogReader.ts   - Discord audit log parsing
```

## Performance

- In-memory action tracking with periodic cleanup
- MongoDB caching with lean queries
- Protection prioritized over logging
- Silent failure on non-critical operations
- Backup snapshots with automatic rotation (max 5)
- Configurable cleanup intervals

## Security Rules

Repent enforces these security principles:

1. Never trusts interaction data alone - always verifies with audit logs
2. Prevents bypass through rapid action bursts via rolling windows
3. Prevents bypass through alternate accounts (per-user tracking)
4. Prevents bypass through newly invited bots (botAdd protection)
5. Prevents bypass through webhook spam (webhookCreate protection)
6. Prevents bypass through role hierarchy abuse (role permission checks)
7. Prevents bypass through permission escalation (pre-change detection)
8. Only the server owner can manage the whitelist
9. Owner cannot be punished
10. Panic mode provides instant full lockdown

## Default Thresholds

| Action | Threshold | Window | Punishment |
|--------|-----------|--------|------------|
| Channel Delete | 3 | 10s | Ban |
| Channel Create | 5 | 10s | Ban |
| Role Delete | 3 | 10s | Ban |
| Role Create | 5 | 10s | Ban |
| Category Delete | 2 | 10s | Ban |
| Permission Escalation | 1 | 1s | Ban |
| Mass Ban | 3 | 10s | Ban |
| Mass Kick | 3 | 10s | Ban |
| Bot Add | 2 | 60s | Ban |
| Webhook Create | 3 | 10s | Ban |
| Emoji Delete | 5 | 10s | Ban |
| Sticker Delete | 5 | 10s | Ban |

## License

MIT
