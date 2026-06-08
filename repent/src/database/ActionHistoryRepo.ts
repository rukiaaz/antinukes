import { Database } from './Database';
import { Logger } from '../utils/Logger';
import type { ActionRecord, TrackedAction } from '../types';

export class ActionHistoryRepo {
  private db: Database;
  private logger: Logger;

  constructor() {
    this.db = Database.getInstance();
    this.logger = Logger.getInstance();
  }

  recordAction(guildId: string, userId: string, action: TrackedAction, targetId: string | null): boolean {
    try {
      this.db.getDatabase()
        .prepare(`
          INSERT INTO action_history (guild_id, user_id, action, target_id, timestamp)
          VALUES (?, ?, ?, ?, ?)
        `)
        .run(guildId, userId, action, targetId, Date.now());

      return true;
    } catch (error) {
      this.logger.error('Error recording action', { error, guildId, userId, action });
      return false;
    }
  }

  getRecentActions(guildId: string, userId: string, action: TrackedAction, windowMs: number): ActionRecord[] {
    try {
      const cutoff = Date.now() - windowMs;
      const rows = this.db.getDatabase()
        .prepare(`
          SELECT * FROM action_history
          WHERE guild_id = ? AND user_id = ? AND action = ? AND timestamp > ?
          ORDER BY timestamp DESC
        `)
        .all(guildId, userId, action, cutoff) as any[];

      return rows.map(row => ({
        id: row.id,
        guildId: row.guild_id,
        userId: row.user_id,
        action: row.action as TrackedAction,
        targetId: row.target_id,
        timestamp: row.timestamp,
      }));
    } catch (error) {
      this.logger.error('Error fetching recent actions', { error, guildId, userId, action });
      return [];
    }
  }

  getActionCount(guildId: string, userId: string, action: TrackedAction, windowMs: number): number {
    try {
      const cutoff = Date.now() - windowMs;
      const row = this.db.getDatabase()
        .prepare(`
          SELECT COUNT(*) as count FROM action_history
          WHERE guild_id = ? AND user_id = ? AND action = ? AND timestamp > ?
        `)
        .get(guildId, userId, action, cutoff) as any;

      return row?.count ?? 0;
    } catch (error) {
      this.logger.error('Error counting actions', { error, guildId, userId, action });
      return 0;
    }
  }

  cleanupOldActions(olderThanMs: number): number {
    try {
      const cutoff = Date.now() - olderThanMs;
      const result = this.db.getDatabase()
        .prepare('DELETE FROM action_history WHERE timestamp < ?')
        .run(cutoff);

      return result.changes;
    } catch (error) {
      this.logger.error('Error cleaning up old actions', { error });
      return 0;
    }
  }
}
