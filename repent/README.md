# Repent - Discord Anti-Nuke Bot

**Repent** is a production-grade Discord anti-nuke bot designed to prevent, stop, punish, and recover from server attacks. Built with speed, security, and reliability as core priorities.

## Features

### Protection Modules

- **Channel Protection** - Detects mass channel deletion, creation, and modification
- **Role Protection** - Detects mass role deletion, creation, and modification
- **Permission Escalation Protection** - Instant detection and reversion of dangerous permission grants
- **Member Protection** - Detects mass bans, kicks, timeouts, and role changes
- **Webhook Protection** - Detects and removes malicious webhooks
- **Bot Protection** - Automatically kicks unauthorized bots and punishes inviters
- **Emoji & Sticker Protection** - Detects mass emoji/sticker deletion
- **Server Protection** - Detects and reverts guild setting changes

### Security Features

- **Rolling Window Detection** - Uses time-based sliding windows, not simple counters
- **Audit Log Verification** - Every action is verified via Discord audit logs before punishment
- **Whitelist System** - Per-guild user and role whitelists (server owner always exempt)
- **Auto-Recovery** - Automatic snapshot-based recovery of deleted/modified objects
- **Panic Mode** - Emergency mode that strips all dangerous permissions and locks the server
- **Lockdown** - Disables messaging across all channels

### Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `/setup` | Interactive setup wizard | Administrator |
| `/status` | View protection status | Administrator |
| `/config` | View/edit thresholds and settings | Administrator |
| `/whitelist add/remove` | Manage user whitelist | Administrator |
| `/whitelist role_add/role_remove` | Manage role whitelist | Administrator |
| `/lockdown enable/disable` | Lock/unlock all channels | Administrator |
| `/panic on/off` | Emergency panic mode | Administrator |
| `/backup create/restore/list` | Manage snapshots | Administrator |

## Installation

### Prerequisites

- Node.js 20+
- SQLite (included via better-sqlite3)

### Setup

1. **Clone and install:**
```bash
git clone <repository>
cd repent
npm install
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your values:
# DISCORD_TOKEN=your_bot_token
# CLIENT_ID=your_application_id
# OWNER_ID=your_discord_user_id
```

3. **Build:**
```bash
npm run build
```

4. **Start:**
```bash
npm start
# Or for development:
npm run watch
```

### Discord Setup

1. Create a new application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a bot and copy the token to `.env`
3. Copy the Application ID to `.env` as `CLIENT_ID`
4. Enable these **Privileged Gateway Intents**:
   - Server Members Intent
   - Message Content Intent (optional, not required)
5. Generate an invite URL with these permissions:
   - Administrator (required for full protection)
   - Or minimally: Manage Server, Manage Channels, Manage Roles, Ban Members, Kick Members, Manage Webhooks, Manage Emojis and Stickers

### Server Setup

1. Invite Repent to your server
2. Run `/setup` in your server
3. Follow the interactive wizard (takes under one minute)
4. Done. Your server is now protected.

## Configuration

### Default Thresholds

| Action | Limit | Window |
|--------|-------|--------|
| Channel Delete | 2 | 10s |
| Channel Create | 5 | 10s |
| Channel Update | 10 | 10s |
| Role Delete | 2 | 10s |
| Role Create | 5 | 10s |
| Role Update | 10 | 10s |
| Webhook Create | 2 | 10s |
| Webhook Delete | 2 | 10s |
| Webhook Update | 5 | 10s |
| Ban | 3 | 10s |
| Kick | 3 | 10s |
| Timeout | 5 | 10s |
| Bot Add | 1 | 30s |

Customize via `/config threshold`

### Punishment Types

- **Remove Roles** - Removes all dangerous roles from the offender
- **Timeout** - 28-day timeout
- **Kick** - Removes the user from the server
- **Ban** - Bans the user (default)

## Architecture

```
src/
  commands/       - Slash command definitions
  database/       - SQLite repositories
  events/         - Discord event handlers
  modules/        - Protection modules
  services/       - Core business logic
  types/          - TypeScript type definitions
  utils/          - Utilities (logger, etc.)
  index.ts        - Entry point
```

### Security Philosophy

- Staff accounts can be compromised
- Admin accounts can be compromised
- Selfbots exist
- Raid bots exist
- Protection must happen immediately
- Logging is secondary to protection
- Never punish before audit log verification
- Never stop protecting because a secondary system failed

## Performance

- Target response time: Under 500ms
- Memory-safe action tracking with rolling windows
- Automatic cleanup of old action records
- Efficient SQLite queries with proper indexing

## License

MIT
