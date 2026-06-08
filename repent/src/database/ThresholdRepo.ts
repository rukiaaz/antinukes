import { Database } from './Database';
import { Logger } from '../utils/Logger';
import type { ThresholdConfig, ThresholdValues, TrackedAction } from '../types';

const ACTION_TO_COLUMNS: Record<TrackedAction, { limit: string; window: string }> = {
  channel_delete: { limit: 'channel_delete_limit', window: 'channel_delete_window' },
  channel_create: { limit: 'channel_create_limit', window: 'channel_create_window' },
  channel_update: { limit: 'channel_update_limit', window: 'channel_update_window' },
  role_delete: { limit: 'role_delete_limit', window: 'role_delete_window' },
  role_create: { limit: 'role_create_limit', window: 'role_create_window' },
  role_update: { limit: 'role_update_limit', window: 'role_update_window' },
  webhook_create: { limit: 'webhook_create_limit', window: 'webhook_create_window' },
  webhook_delete: { limit: 'webhook_delete_limit', window: 'webhook_delete_window' },
  webhook_update: { limit: 'webhook_update_limit', window: 'webhook_update_window' },
  ban: { limit: 'ban_limit', window: 'ban_window' },
  kick: { limit: 'kick_limit', window: 'kick_window' },
  timeout: { limit: 'timeout_limit', window: 'timeout_window' },
  bot_add: { limit: 'bot_add_limit', window: 'bot_add_window' },
  emoji_delete: { limit: 'channel_delete_limit', window: 'channel_delete_window' },
  emoji_create: { limit: 'channel_create_limit', window: 'channel_create_window' },
  emoji_update: { limit: 'channel_update_limit', window: 'channel_update_window' },
  sticker_delete: { limit: 'channel_delete_limit', window: 'channel_delete_window' },
  sticker_create: { limit: 'channel_create_limit', window: 'channel_create_window' },
  sticker_update: { limit: 'channel_update_limit', window: 'channel_update_window' },
  guild_update: { limit: 'channel_update_limit', window: 'channel_update_window' },
  member_role_update: { limit: 'role_update_limit', window: 'role_update_window' },
  member_nickname_update: { limit: 'role_update_limit', window: 'role_update_window' },
  permission_escalation: { limit: 'role_delete_limit', window: 'role_delete_window' },
};

export class ThresholdRepo {
  private db: Database;
  private logger: Logger;

  constructor() {
    this.db = Database.getInstance();
    this.logger = Logger.getInstance();
  }

  get(guildId: string): ThresholdConfig | null {
    try {
      const row = this.db.getDatabase()
        .prepare('SELECT * FROM threshold_configs WHERE guild_id = ?')
        .get(guildId) as any;

      if (!row) return null;

      return {
        guildId: row.guild_id,
        channelDeleteLimit: row.channel_delete_limit,
        channelDeleteWindow: row.channel_delete_window,
        channelCreateLimit: row.channel_create_limit,
        channelCreateWindow: row.channel_create_window,
        channelUpdateLimit: row.channel_update_limit,
        channelUpdateWindow: row.channel_update_window,
        roleDeleteLimit: row.role_delete_limit,
        roleDeleteWindow: row.role_delete_window,
        roleCreateLimit: row.role_create_limit,
        roleCreateWindow: row.role_create_window,
        roleUpdateLimit: row.role_update_limit,
        roleUpdateWindow: row.role_update_window,
        webhookCreateLimit: row.webhook_create_limit,
        webhookCreateWindow: row.webhook_create_window,
        webhookDeleteLimit: row.webhook_delete_limit,
        webhookDeleteWindow: row.webhook_delete_window,
        webhookUpdateLimit: row.webhook_update_limit,
        webhookUpdateWindow: row.webhook_update_window,
        banLimit: row.ban_limit,
        banWindow: row.ban_window,
        kickLimit: row.kick_limit,
        kickWindow: row.kick_window,
        timeoutLimit: row.timeout_limit,
        timeoutWindow: row.timeout_window,
        botAddLimit: row.bot_add_limit,
        botAddWindow: row.bot_add_window,
      };
    } catch (error) {
      this.logger.error('Error fetching threshold config', { error, guildId });
      return null;
    }
  }

  getThresholdForAction(guildId: string, action: TrackedAction): ThresholdValues | null {
    const columns = ACTION_TO_COLUMNS[action];
    if (!columns) return null;

    try {
      const row = this.db.getDatabase()
        .prepare(`SELECT ${columns.limit} as limit_val, ${columns.window} as window_val FROM threshold_configs WHERE guild_id = ?`)
        .get(guildId) as any;

      if (!row) return null;

      return {
        limit: row.limit_val,
        window: row.window_val,
      };
    } catch (error) {
      this.logger.error('Error fetching threshold for action', { error, guildId, action });
      return null;
    }
  }

  createDefaults(guildId: string): boolean {
    try {
      this.db.getDatabase()
        .prepare('INSERT OR IGNORE INTO threshold_configs (guild_id) VALUES (?)')
        .run(guildId);
      return true;
    } catch (error) {
      this.logger.error('Error creating default thresholds', { error, guildId });
      return false;
    }
  }

  update(guildId: string, updates: Partial<ThresholdConfig>): boolean {
    try {
      const fieldMap: Record<string, string> = {
        channelDeleteLimit: 'channel_delete_limit',
        channelDeleteWindow: 'channel_delete_window',
        channelCreateLimit: 'channel_create_limit',
        channelCreateWindow: 'channel_create_window',
        channelUpdateLimit: 'channel_update_limit',
        channelUpdateWindow: 'channel_update_window',
        roleDeleteLimit: 'role_delete_limit',
        roleDeleteWindow: 'role_delete_window',
        roleCreateLimit: 'role_create_limit',
        roleCreateWindow: 'role_create_window',
        roleUpdateLimit: 'role_update_limit',
        roleUpdateWindow: 'role_update_window',
        webhookCreateLimit: 'webhook_create_limit',
        webhookCreateWindow: 'webhook_create_window',
        webhookDeleteLimit: 'webhook_delete_limit',
        webhookDeleteWindow: 'webhook_delete_window',
        webhookUpdateLimit: 'webhook_update_limit',
        webhookUpdateWindow: 'webhook_update_window',
        banLimit: 'ban_limit',
        banWindow: 'ban_window',
        kickLimit: 'kick_limit',
        kickWindow: 'kick_window',
        timeoutLimit: 'timeout_limit',
        timeoutWindow: 'timeout_window',
        botAddLimit: 'bot_add_limit',
        botAddWindow: 'bot_add_window',
      };

      const fields: string[] = [];
      const values: any[] = [];

      for (const [key, value] of Object.entries(updates)) {
        const column = fieldMap[key];
        if (column && typeof value === 'number') {
          fields.push(`${column} = ?`);
          values.push(value);
        }
      }

      if (fields.length === 0) return false;

      values.push(guildId);

      this.db.getDatabase()
        .prepare(`UPDATE threshold_configs SET ${fields.join(', ')} WHERE guild_id = ?`)
        .run(...values);

      return true;
    } catch (error) {
      this.logger.error('Error updating thresholds', { error, guildId });
      return false;
    }
  }

  getOrCreateDefault(guildId: string): ThresholdConfig {
    let config = this.get(guildId);
    if (!config) {
      this.createDefaults(guildId);
      config = this.get(guildId)!;
    }
    return config;
  }
}
