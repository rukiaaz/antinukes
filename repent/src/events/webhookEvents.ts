import { TextChannel, NewsChannel, VoiceChannel, ForumChannel, AuditLogEvent } from 'discord.js';
import { WebhookProtection } from '../modules/WebhookProtection';
import { Logger } from '../utils/Logger';

const protection = new WebhookProtection();
const logger = Logger.getInstance();

export const webhookEvents = {
  async handleWebhooksUpdate(channel: TextChannel | NewsChannel | VoiceChannel | ForumChannel): Promise<void> {
    if (!channel.guild) return;

    try {
      const auditLogs = await channel.guild.fetchAuditLogs({
        limit: 5,
      });

      const entries = auditLogs.entries.filter(entry =>
        entry.targetType === 'Webhook' &&
        Date.now() - entry.createdTimestamp < 5000
      );

      for (const [, entry] of entries) {
        if (entry.action === AuditLogEvent.WebhookCreate) {
          const webhook = entry.extra as any;
          if (webhook) {
            await protection.handleWebhookCreate(webhook);
          }
        } else if (entry.action === AuditLogEvent.WebhookDelete) {
          await protection.handleWebhookDelete({
            id: entry.targetId,
            guild: channel.guild,
          } as any);
        } else if (entry.action === AuditLogEvent.WebhookUpdate) {
          const webhook = entry.extra as any;
          if (webhook) {
            await protection.handleWebhookUpdate(webhook, webhook);
          }
        }
      }
    } catch (error) {
      logger.error('Webhook protection error', { error, channelId: channel.id });
    }
  },
};
