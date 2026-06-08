import {
  AuditLogEvent,
  type Guild,
  type User,
  type GuildAuditLogsEntry,
} from 'discord.js';
import { CONFIG } from './config';
import type { ActionType } from '../types';

const ACTION_TO_AUDIT_EVENT: Partial<Record<ActionType, AuditLogEvent>> = {
  channelDelete: AuditLogEvent.ChannelDelete,
  channelCreate: AuditLogEvent.ChannelCreate,
  channelUpdate: AuditLogEvent.ChannelUpdate,
  categoryDelete: AuditLogEvent.ChannelDelete,
  categoryUpdate: AuditLogEvent.ChannelUpdate,
  roleDelete: AuditLogEvent.RoleDelete,
  roleCreate: AuditLogEvent.RoleCreate,
  roleUpdate: AuditLogEvent.RoleUpdate,
  webhookCreate: AuditLogEvent.WebhookCreate,
  webhookDelete: AuditLogEvent.WebhookDelete,
  webhookUpdate: AuditLogEvent.WebhookUpdate,
  massBan: AuditLogEvent.MemberBanAdd,
  massKick: AuditLogEvent.MemberKick,
  massTimeout: AuditLogEvent.MemberUpdate,
  emojiDelete: AuditLogEvent.EmojiDelete,
  emojiCreate: AuditLogEvent.EmojiCreate,
  stickerDelete: AuditLogEvent.StickerDelete,
  stickerCreate: AuditLogEvent.StickerCreate,
  serverUpdate: AuditLogEvent.GuildUpdate,
  botAdd: AuditLogEvent.BotAdd,
};

export class AuditLogReader {
  public static async getExecutor(
    guild: Guild,
    actionType: ActionType,
    targetId?: string
  ): Promise<{ executor: User | null; entry: GuildAuditLogsEntry | null }> {
    const event = ACTION_TO_AUDIT_EVENT[actionType];
    if (!event) return { executor: null, entry: null };

    try {
      const logs = await guild.fetchAuditLogs({
        limit: CONFIG.AUDIT_LOG_FETCH_LIMIT,
        type: event,
      });

      const now = Date.now();

      const eligible = logs.entries.filter(entry => {
        if (!entry.executor || entry.executor.bot) return false;
        const age = now - entry.createdTimestamp;
        return age <= CONFIG.AUDIT_LOG_MAX_AGE_MS;
      });

      // If targetId is provided, prefer exact matches on common audit-log fields.
      // Fallback to newest eligible entry if we can't confidently match target.
      if (targetId) {
        const strict = eligible.filter(entry => {
          // discord.js audit logs often expose `targetId` in addition to `target`
          const anyEntry = entry as any;

          if (typeof anyEntry.targetId === 'string') {
            if (anyEntry.targetId === targetId) return true;
          }

          const targetAny = entry.target as any | undefined | null;
          if (!targetAny) return false;

          const candidateId = targetAny.id ?? targetAny.userId;
          return typeof candidateId === 'string' && candidateId === targetId;
        });

        const strictFirst = strict.first();
        if (strictFirst?.executor) {
          return { executor: strictFirst.executor as User, entry: strictFirst };
        }
      }

      // Fallback: newest eligible entry (target matching may be unreliable for some audit logs).
      const first = eligible.first();
      if (first?.executor) {
        return { executor: first.executor as User, entry: first };
      }

      return { executor: null, entry: null };
    } catch {
      return { executor: null, entry: null };
    }
  }

  public static async getRecentEntries(
    guild: Guild,
    actionType: ActionType,
    limit: number = 10
  ): Promise<GuildAuditLogsEntry[]> {
    const event = ACTION_TO_AUDIT_EVENT[actionType];
    if (!event) return [];

    try {
      const logs = await guild.fetchAuditLogs({ limit, type: event });
      const now = Date.now();

      return logs.entries
        .filter(entry => {
          if (!entry.executor || entry.executor.bot) return false;
          const age = now - entry.createdTimestamp;
          return age <= CONFIG.AUDIT_LOG_MAX_AGE_MS;
        })
        .toJSON();
    } catch {
      return [];
    }
  }

  public static async getPermissionEscalationEntry(
    guild: Guild,
    roleId?: string
  ): Promise<{ executor: User | null; entry: GuildAuditLogsEntry | null }> {
    try {
      const logs = await guild.fetchAuditLogs({
        limit: CONFIG.AUDIT_LOG_FETCH_LIMIT,
        type: AuditLogEvent.RoleUpdate,
      });

      const now = Date.now();

      const entries = logs.entries.filter(entry => {
        if (!entry.executor || entry.executor.bot) return false;

        const age = now - entry.createdTimestamp;
        if (age > CONFIG.AUDIT_LOG_MAX_AGE_MS) return false;

        if (roleId && entry.target) {
          const target = entry.target as { id?: string };
          if (target.id !== roleId) return false;
        }

        const changes = entry.changes.filter(
          c => c.key === 'permissions' || c.key === 'allow' || c.key === 'deny'
        );

        return changes.length > 0;
      });

      const entry = entries.first();
      if (!entry?.executor) return { executor: null, entry: null };

      return { executor: entry.executor as User, entry };
    } catch {
      return { executor: null, entry: null };
    }
  }
}
