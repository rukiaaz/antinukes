import { Database } from './Database';
import { Logger } from '../utils/Logger';
import type { GuildConfig, PunishmentType } from '../types';

export class GuildConfigRepo {
  private db: Database;
  private logger: Logger;

  constructor() {
    this.db = Database.getInstance();
    this.logger = Logger.getInstance();
  }

  get(guildId: string): GuildConfig | null {
    try {
      const row = this.db.getDatabase()
        .prepare('SELECT * FROM guild_configs WHERE guild_id = ?')
        .get(guildId) as any;

      if (!row) return null;

      return {
        guildId: row.guild_id,
        logChannelId: row.log_channel_id,
        punishmentType: row.punishment_type as PunishmentType,
        enabled: Boolean(row.enabled),
        createdAt: row.created_at,
        updatedAt: row.updated_at,
      };
    } catch (error) {
      this.logger.error('Error fetching guild config', { error, guildId });
      return null;
    }
  }

  create(config: Omit<GuildConfig, 'createdAt' | 'updatedAt'>): boolean {
    try {
      this.db.getDatabase()
        .prepare(`
          INSERT INTO guild_configs (guild_id, log_channel_id, punishment_type, enabled)
          VALUES (?, ?, ?, ?)
        `)
        .run(config.guildId, config.logChannelId, config.punishmentType, config.enabled ? 1 : 0);

      this.logger.info('Guild config created', { guildId: config.guildId });
      return true;
    } catch (error) {
      this.logger.error('Error creating guild config', { error, guildId: config.guildId });
      return false;
    }
  }

  update(guildId: string, updates: Partial<Omit<GuildConfig, 'guildId' | 'createdAt' | 'updatedAt'>>): boolean {
    try {
      const fields: string[] = [];
      const values: any[] = [];

      if (updates.logChannelId !== undefined) {
        fields.push('log_channel_id = ?');
        values.push(updates.logChannelId);
      }
      if (updates.punishmentType !== undefined) {
        fields.push('punishment_type = ?');
        values.push(updates.punishmentType);
      }
      if (updates.enabled !== undefined) {
        fields.push('enabled = ?');
        values.push(updates.enabled ? 1 : 0);
      }

      if (fields.length === 0) return false;

      fields.push('updated_at = unixepoch()');
      values.push(guildId);

      this.db.getDatabase()
        .prepare(`UPDATE guild_configs SET ${fields.join(', ')} WHERE guild_id = ?`)
        .run(...values);

      this.logger.info('Guild config updated', { guildId, updates: Object.keys(updates) });
      return true;
    } catch (error) {
      this.logger.error('Error updating guild config', { error, guildId });
      return false;
    }
  }

  delete(guildId: string): boolean {
    try {
      this.db.getDatabase()
        .prepare('DELETE FROM guild_configs WHERE guild_id = ?')
        .run(guildId);
      return true;
    } catch (error) {
      this.logger.error('Error deleting guild config', { error, guildId });
      return false;
    }
  }

  isEnabled(guildId: string): boolean {
    const config = this.get(guildId);
    return config?.enabled ?? false;
  }

  getOrCreateDefault(guildId: string): GuildConfig {
    let config = this.get(guildId);
    if (!config) {
      this.create({
        guildId,
        logChannelId: null,
        punishmentType: 'ban',
        enabled: false,
      });
      config = this.get(guildId)!;
    }
    return config;
  }
}
