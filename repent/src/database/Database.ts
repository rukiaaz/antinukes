import DatabaseConstructor from 'better-sqlite3';
import type { Database as DatabaseType } from 'better-sqlite3';
import { Logger } from '../utils/Logger';

export class Database {
  private static instance: Database | null = null;
  private db: DatabaseType;
  private logger: Logger;

  private constructor(dbPath: string) {
    this.logger = Logger.getInstance();
    this.db = new DatabaseConstructor(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('foreign_keys = ON');
    this.initializeTables();
    this.logger.info('Database initialized', { path: dbPath });
  }

  static getInstance(dbPath?: string): Database {
    if (!Database.instance) {
      if (!dbPath) {
        throw new Error('Database path required for first initialization');
      }
      Database.instance = new Database(dbPath);
    }
    return Database.instance;
  }

  static resetInstance(): void {
    Database.instance = null;
  }

  getDatabase(): DatabaseType {
    return this.db;
  }

  private initializeTables(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS guild_configs (
        guild_id TEXT PRIMARY KEY,
        log_channel_id TEXT,
        punishment_type TEXT DEFAULT 'ban',
        enabled INTEGER DEFAULT 1,
        created_at INTEGER DEFAULT (unixepoch()),
        updated_at INTEGER DEFAULT (unixepoch())
      );

      CREATE TABLE IF NOT EXISTS threshold_configs (
        guild_id TEXT PRIMARY KEY,
        channel_delete_limit INTEGER DEFAULT 2,
        channel_delete_window INTEGER DEFAULT 10,
        channel_create_limit INTEGER DEFAULT 5,
        channel_create_window INTEGER DEFAULT 10,
        channel_update_limit INTEGER DEFAULT 10,
        channel_update_window INTEGER DEFAULT 10,
        role_delete_limit INTEGER DEFAULT 2,
        role_delete_window INTEGER DEFAULT 10,
        role_create_limit INTEGER DEFAULT 5,
        role_create_window INTEGER DEFAULT 10,
        role_update_limit INTEGER DEFAULT 10,
        role_update_window INTEGER DEFAULT 10,
        webhook_create_limit INTEGER DEFAULT 2,
        webhook_create_window INTEGER DEFAULT 10,
        webhook_delete_limit INTEGER DEFAULT 2,
        webhook_delete_window INTEGER DEFAULT 10,
        webhook_update_limit INTEGER DEFAULT 5,
        webhook_update_window INTEGER DEFAULT 10,
        ban_limit INTEGER DEFAULT 3,
        ban_window INTEGER DEFAULT 10,
        kick_limit INTEGER DEFAULT 3,
        kick_window INTEGER DEFAULT 10,
        timeout_limit INTEGER DEFAULT 5,
        timeout_window INTEGER DEFAULT 10,
        bot_add_limit INTEGER DEFAULT 1,
        bot_add_window INTEGER DEFAULT 30,
        FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS whitelist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        target_type TEXT NOT NULL CHECK(target_type IN ('user', 'role')),
        added_by TEXT NOT NULL,
        added_at INTEGER DEFAULT (unixepoch()),
        UNIQUE(guild_id, target_id)
      );

      CREATE INDEX IF NOT EXISTS idx_whitelist_guild ON whitelist(guild_id);

      CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        name TEXT NOT NULL,
        data TEXT NOT NULL,
        created_at INTEGER DEFAULT (unixepoch())
      );

      CREATE INDEX IF NOT EXISTS idx_snapshots_guild ON snapshots(guild_id);

      CREATE TABLE IF NOT EXISTS lockdown_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT UNIQUE NOT NULL,
        channel_permissions TEXT NOT NULL,
        created_at INTEGER DEFAULT (unixepoch())
      );

      CREATE TABLE IF NOT EXISTS action_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        action TEXT NOT NULL,
        target_id TEXT,
        timestamp INTEGER DEFAULT (unixepoch())
      );

      CREATE INDEX IF NOT EXISTS idx_action_history_lookup ON action_history(guild_id, user_id, action, timestamp);
    `);
  }

  close(): void {
    this.db.close();
    Database.instance = null;
    this.logger.info('Database connection closed');
  }
}
