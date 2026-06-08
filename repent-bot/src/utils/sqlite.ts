import sqlite3 from 'sqlite3';
import path from 'path';
import fs from 'fs';
import { CONFIG } from './config';

let db: sqlite3.Database | null = null;

function resolveDbPath(): string {
  const rel = CONFIG.SQLITE_PATH;
  // Ensure path is inside repo if user passed a relative path.
  if (rel.includes('..')) {
    throw new Error('SQLITE_PATH must not contain ..');
  }

  const abs = path.isAbsolute(rel) ? rel : path.join(process.cwd(), rel);
  return abs;
}

export async function initSqlite(): Promise<void> {
  if (db) return;

  const absPath = resolveDbPath();
  const dir = path.dirname(absPath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  db = await new Promise<sqlite3.Database>((resolve, reject) => {
    const conn = new sqlite3.Database(absPath, err => {
      if (err) reject(err);
      else resolve(conn);
    });
  });

  // Pragmas for better concurrency/consistency.
  db.exec(`PRAGMA journal_mode = WAL; PRAGMA synchronous = NORMAL; PRAGMA foreign_keys = ON;`);

  await run(
    `CREATE TABLE IF NOT EXISTS guild_settings (\n` +
    `  guild_id TEXT PRIMARY KEY,\n` +
    `  log_channel_id TEXT NULL,\n` +
    `  owner_id TEXT NOT NULL,\n` +
    `  protections_json TEXT NOT NULL,\n` +
    `  whitelist_users_json TEXT NOT NULL,\n` +
    `  whitelist_roles_json TEXT NOT NULL,\n` +
    `  panic_mode INTEGER NOT NULL DEFAULT 0,\n` +
    `  lockdown_channels_json TEXT NOT NULL,\n` +
    `  setup INTEGER NOT NULL DEFAULT 0,\n` +
    `  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),\n` +
    `  updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))\n` +
    `);`
  );

  await run(
    `CREATE TABLE IF NOT EXISTS backups (\n` +
    `  id INTEGER PRIMARY KEY AUTOINCREMENT,\n` +
    `  guild_id TEXT NOT NULL,\n` +
    `  backup_json TEXT NOT NULL,\n` +
    `  timestamp_ms INTEGER NOT NULL,\n` +
    `  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),\n` +
    `  FOREIGN KEY(guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE\n` +
    `);`
  );

  await run(`CREATE INDEX IF NOT EXISTS idx_backups_guild_time ON backups(guild_id, timestamp_ms DESC);`);
}

function getDb(): sqlite3.Database {
  if (!db) throw new Error('SQLite not initialized');
  return db;
}

export async function run(sql: string, params: any[] = []): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    getDb().run(sql, params, err => (err ? reject(err) : resolve()));
  });
}

export async function get<T = any>(sql: string, params: any[] = []): Promise<T | undefined> {
  return await new Promise<T | undefined>((resolve, reject) => {
    getDb().get(sql, params, (err, row) => {
      if (err) reject(err);
      else resolve(row as T | undefined);
    });
  });
}

export async function all<T = any>(sql: string, params: any[] = []): Promise<T[]> {
  return await new Promise<T[]>((resolve, reject) => {
    getDb().all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows as T[]);
    });
  });
}

