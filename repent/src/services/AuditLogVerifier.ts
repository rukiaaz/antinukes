import { Guild, AuditLogEvent, User, GuildAuditLogsEntry } from 'discord.js';
import { Logger } from '../utils/Logger';
import type { TrackedAction } from '../types';

const ACTION_TO_AUDIT_EVENT: Partial<Record<TrackedAction, AuditLogEvent>> = {
  channel_delete: AuditLogEvent.ChannelDelete,
  channel_create: AuditLogEvent.ChannelCreate,
  channel_update: AuditLogEvent.ChannelUpdate,
  role_delete: AuditLogEvent.RoleDelete,
  role_create: AuditLogEvent.RoleCreate,
  role_update: AuditLogEvent.RoleUpdate,
  webhook_create: AuditLogEvent.WebhookCreate,
  webhook_delete: AuditLogEvent.WebhookDelete,
  webhook_update: AuditLogEvent.WebhookUpdate,
  ban: AuditLogEvent.MemberBanAdd,
  kick: AuditLogEvent.MemberKick,
  timeout: AuditLogEvent.MemberUpdate,
  bot_add: AuditLogEvent.BotAdd,
  emoji_delete: AuditLogEvent.EmojiDelete,
  emoji_create: AuditLogEvent.EmojiCreate,
  emoji_update: AuditLogEvent.EmojiUpdate,
  sticker_delete: AuditLogEvent.StickerDelete,
  sticker_create: AuditLogEvent.StickerCreate,
  sticker_update: AuditLogEvent.StickerUpdate,
  guild_update: AuditLogEvent.GuildUpdate,
  member_role_update: AuditLogEvent.MemberRoleUpdate,
  member_nickname_update: AuditLogEvent.MemberUpdate,
};

export interface AuditLogVerification {
  verified: boolean;
  executor: User | null;
  targetId: string | null;
  reason: string | null;
  timestamp: number | null;
}

export class AuditLogVerifier {
  private logger: Logger;

  constructor() {
    this.logger = Logger.getInstance();
  }

  async verify(
    guild: Guild,
    action: TrackedAction,
    expectedTargetId?: string
  ): Promise<AuditLogVerification> {
    const auditEvent = ACTION_TO_AUDIT_EVENT[action];
    if (!auditEvent) {
      return { verified: false, executor: null, targetId: null, reason: null, timestamp: null };
    }

    try {
      const auditLogs = await guild.fetchAuditLogs({
        limit: 10,
        type: auditEvent,
      });

      const entries = auditLogs.entries.filter(entry => {
        const entryTime = entry.createdTimestamp;
        const now = Date.now();
        return now - entryTime < 10000;
      });

      if (entries.size === 0) {
        return { verified: false, executor: null, targetId: null, reason: null, timestamp: null };
      }

      let matchingEntry: GuildAuditLogsEntry | undefined;

      if (expectedTargetId) {
        matchingEntry = entries.find(e => {
          const target = e.target;
          if (!target) return false;
          if (typeof target === 'string') return target === expectedTargetId;
          if ('id' in target) return target.id === expectedTargetId;
          return false;
        });
      }

      if (!matchingEntry) {
        matchingEntry = entries.first();
      }

      if (!matchingEntry) {
        return { verified: false, executor: null, targetId: null, reason: null, timestamp: null };
      }

      const executor = matchingEntry.executor;
      const targetId = matchingEntry.target
        ? typeof matchingEntry.target === 'string'
          ? matchingEntry.target
          : 'id' in matchingEntry.target
            ? matchingEntry.target.id
            : null
        : null;

      return {
        verified: executor !== null && executor.id !== guild.client.user?.id,
        executor: executor as User | null,
        targetId: targetId ?? null,
        reason: matchingEntry.reason ?? null,
        timestamp: matchingEntry.createdTimestamp,
      };
    } catch (error) {
      this.logger.error('Audit log verification failed', {
        error,
        guildId: guild.id,
        action,
      });
      return { verified: false, executor: null, targetId: null, reason: null, timestamp: null };
    }
  }

  async fetchExecutor(
    guild: Guild,
    action: TrackedAction,
    targetId?: string
  ): Promise<User | null> {
    const result = await this.verify(guild, action, targetId);
    return result.executor;
  }
}
