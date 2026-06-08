# Repent Bot Hardening TODO

## 0) Repository audit (done/ongoing)
- [ ] Scan all files for:
  - [ ] silent `except Exception: pass` without logging
  - [ ] indentation / syntax issues
  - [ ] inconsistent cog setup/registration
  - [ ] duplicated antinuke flows
  - [ ] suspicious security logic (webhook deletion, permission escalation detection)

## 1) Runtime-critical correctness fixes
- [x] Verify `cogs/moderation.py` has a valid `async def setup(bot)` at module level (not nested/indented incorrectly)
- [x] Verify all cogs import cleanly on startup (`python -m py_compile` and import loader)
- [x] Fix startup cog load failure in `cogs/antinuke.py`: `CommandAlreadyRegistered: Command 'antinuke_restore' already registered.`

## 2) Antinuke de-duplication + event pipeline hardening
- [ ] Ensure antinuke incident handling runs exactly once per audit log entry (avoid double punish/restore/log)
  - [ ] Decide single source of truth for triggers (audit-log only vs mixed fast-path listeners)
  - [x] Disable fast-path duplicate-processing path that re-ran incident handling
- [ ] Strengthen incident fingerprinting if needed (e.g., key by guild_id+action_type+target_id+time bucket)

## 3) Rate limiter decorator validation
- [x] Confirm `utils/rate_limiter.py` decorator reviewed (basic wiring sanity)
- [ ] Fix `dynamic_cooldown` decorator wiring if it is incompatible with installed discord.py version (next: validate at runtime)
- [ ] Add minimal tests or a dry-run runtime check for decorated commands

## 4) Logging & observability improvements
- [x] Replace silent exception swallowing in antinuke + automod + moderation with `logger.error(..., exc_info=True)`
- [x] Standardize structured context on key security events
- [ ] Replace remaining broad `except Exception: pass` with logged exceptions across all cogs

## 5) Automod performance & hardening
- [ ] Cache bad words per guild with TTL to avoid DB query per message
- [ ] Review webhook deletion logic for safety (preserve trusted/managed webhooks correctly)
- [ ] Add logging for rule triggers when deletions/timeouts fail

## 6) Database consistency & performance
- [ ] Ensure connection pool usage is consistent (avoid raw connections except where justified)
- [ ] Add/verify indexes for queries used heavily (whitelist, ignored_channels, bad_words)
- [ ] Confirm foreign keys + WAL + busy_timeout behavior under concurrency

## 7) Verification
- [ ] `python -m py_compile` across repo
- [ ] Start bot and check:
  - [ ] cogs load
  - [ ] slash commands sync
  - [ ] no new errors in `logs/error.log`
- [ ] Run one simulated incident and confirm:
  - [ ] exactly one punishment + one security log per incident

