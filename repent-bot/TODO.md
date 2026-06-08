# Repent-bot task TODO

## Goal: scan repo, make it work, and provide database instructions

### Step 1: Repo scan (done)
- Reviewed DB connection + schemas (GuildSettings, Backup)
- Reviewed core runtime structures (Repent, ProtectionHandler, PunishmentHandler, ActionTracker, BackupManager, LogHandler)

### Step 2: Identify breakages (done)
- MongoDB connection fails (ECONNREFUSED localhost:27017)

### Step 3: Transition DB to SQLite (approved choice)
- [ ] Add SQLite util/connection + init tables
- [ ] Replace Mongoose GuildSettings persistence with SQLite
- [ ] Replace Mongoose Backup persistence with SQLite
- [ ] Update database connection entrypoint (utils/database.ts)
- [ ] Update config/env expectations

### Step 4: Build + run smoke test
- [ ] npm install (new dependency)
- [ ] npm run build
- [ ] npm run dev

### Step 5: Database instructions (final write-up)
- [ ] Provide .env changes (SQLITE_PATH)
- [ ] Explain DB file creation + table layout
- [ ] Explain how to verify data created

