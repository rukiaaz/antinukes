import { Database } from './Database';
import { Logger } from '../utils/Logger';
import type { Snapshot, SnapshotData } from '../types';

export class SnapshotRepo {
  private db: Database;
  private logger: Logger;

  constructor() {
    this.db = Database.getInstance();
    this.logger = Logger.getInstance();
  }

  create(guildId: string, name: string, data: SnapshotData): boolean {
    try {
      this.db.getDatabase()
        .prepare(`
          INSERT INTO snapshots (guild_id, name, data)
          VALUES (?, ?, ?)
        `)
        .run(guildId, name, JSON.stringify(data));

      this.logger.info('Snapshot created', { guildId, name });
      return true;
    } catch (error) {
      this.logger.error('Error creating snapshot', { error, guildId, name });
      return false;
    }
  }

  getLatest(guildId: string): Snapshot | null {
    try {
      const row = this.db.getDatabase()
        .prepare(`
          SELECT * FROM snapshots
          WHERE guild_id = ?
          ORDER BY created_at DESC
          LIMIT 1
        `)
        .get(guildId) as any;

      if (!row) return null;

      return {
        id: row.id,
        guildId: row.guild_id,
        name: row.name,
        data: JSON.parse(row.data) as SnapshotData,
        createdAt: row.created_at,
      };
    } catch (error) {
      this.logger.error('Error fetching latest snapshot', { error, guildId });
      return null;
    }
  }

  getAllForGuild(guildId: string): Snapshot[] {
    try {
      const rows = this.db.getDatabase()
        .prepare('SELECT * FROM snapshots WHERE guild_id = ? ORDER BY created_at DESC')
        .all(guildId) as any[];

      return rows.map(row => ({
        id: row.id,
        guildId: row.guild_id,
        name: row.name,
        data: JSON.parse(row.data) as SnapshotData,
        createdAt: row.created_at,
      }));
    } catch (error) {
      this.logger.error('Error fetching snapshots', { error, guildId });
      return [];
    }
  }

  delete(id: number): boolean {
    try {
      this.db.getDatabase()
        .prepare('DELETE FROM snapshots WHERE id = ?')
        .run(id);
      return true;
    } catch (error) {
      this.logger.error('Error deleting snapshot', { error, id });
      return false;
    }
  }

  cleanupOldSnapshots(guildId: string, keepCount: number): number {
    try {
      const result = this.db.getDatabase()
        .prepare(`
          DELETE FROM snapshots
          WHERE guild_id = ? AND id NOT IN (
            SELECT id FROM snapshots
            WHERE guild_id = ?
            ORDER BY created_at DESC
            LIMIT ?
          )
        `)
        .run(guildId, guildId, keepCount);

      return result.changes;
    } catch (error) {
      this.logger.error('Error cleaning up old snapshots', { error, guildId });
      return 0;
    }
  }
}
