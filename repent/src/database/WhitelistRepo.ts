import { Database } from './Database';
import { Logger } from '../utils/Logger';
import type { WhitelistEntry } from '../types';

export class WhitelistRepo {
  private db: Database;
  private logger: Logger;

  constructor() {
    this.db = Database.getInstance();
    this.logger = Logger.getInstance();
  }

  get(guildId: string, targetId: string): WhitelistEntry | null {
    try {
      const row = this.db.getDatabase()
        .prepare('SELECT * FROM whitelist WHERE guild_id = ? AND target_id = ?')
        .get(guildId, targetId) as any;

      if (!row) return null;

      return {
        id: row.id,
        guildId: row.guild_id,
        targetId: row.target_id,
        targetType: row.target_type,
        addedBy: row.added_by,
        addedAt: row.added_at,
      };
    } catch (error) {
      this.logger.error('Error fetching whitelist entry', { error, guildId, targetId });
      return null;
    }
  }

  getAllForGuild(guildId: string): WhitelistEntry[] {
    try {
      const rows = this.db.getDatabase()
        .prepare('SELECT * FROM whitelist WHERE guild_id = ?')
        .all(guildId) as any[];

      return rows.map(row => ({
        id: row.id,
        guildId: row.guild_id,
        targetId: row.target_id,
        targetType: row.target_type,
        addedBy: row.added_by,
        addedAt: row.added_at,
      }));
    } catch (error) {
      this.logger.error('Error fetching whitelist entries', { error, guildId });
      return [];
    }
  }

  add(entry: Omit<WhitelistEntry, 'id' | 'addedAt'>): boolean {
    try {
      this.db.getDatabase()
        .prepare(`
          INSERT INTO whitelist (guild_id, target_id, target_type, added_by)
          VALUES (?, ?, ?, ?)
          ON CONFLICT(guild_id, target_id) DO UPDATE SET
            target_type = excluded.target_type,
            added_by = excluded.added_by,
            added_at = unixepoch()
        `)
        .run(entry.guildId, entry.targetId, entry.targetType, entry.addedBy);

      this.logger.info('Whitelist entry added', { guildId: entry.guildId, targetId: entry.targetId });
      return true;
    } catch (error) {
      this.logger.error('Error adding whitelist entry', { error, guildId: entry.guildId, targetId: entry.targetId });
      return false;
    }
  }

  remove(guildId: string, targetId: string): boolean {
    try {
      const result = this.db.getDatabase()
        .prepare('DELETE FROM whitelist WHERE guild_id = ? AND target_id = ?')
        .run(guildId, targetId);

      return result.changes > 0;
    } catch (error) {
      this.logger.error('Error removing whitelist entry', { error, guildId, targetId });
      return false;
    }
  }

  isWhitelisted(guildId: string, userId: string, userRoleIds: string[]): boolean {
    try {
      const userEntry = this.db.getDatabase()
        .prepare('SELECT 1 FROM whitelist WHERE guild_id = ? AND target_id = ? AND target_type = ?')
        .get(guildId, userId, 'user');

      if (userEntry) return true;

      for (const roleId of userRoleIds) {
        const roleEntry = this.db.getDatabase()
          .prepare('SELECT 1 FROM whitelist WHERE guild_id = ? AND target_id = ? AND target_type = ?')
          .get(guildId, roleId, 'role');

        if (roleEntry) return true;
      }

      return false;
    } catch (error) {
      this.logger.error('Error checking whitelist', { error, guildId, userId });
      return false;
    }
  }
}
