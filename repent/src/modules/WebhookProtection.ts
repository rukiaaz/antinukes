import { Webhook, Guild, Client } from 'discord.js';
import { BaseProtection } from './BaseProtection';

export class WebhookProtection extends BaseProtection {
  private async getGuildFromWebhook(webhook: Webhook): Promise<Guild | null> {
    if (!webhook.guildId) return null;
    try {
      const client = webhook.client as Client;
      return await client.guilds.fetch(webhook.guildId);
    } catch {
      return null;
    }
  }

  async handleWebhookCreate(webhook: Webhook): Promise<void> {
    const guild = await this.getGuildFromWebhook(webhook);
    if (!guild || !this.configRepo.isEnabled(guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      guild.id,
      'system',
      'webhook_create',
      webhook.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(guild, 'webhook_create', webhook.id, 'webhook', detectionResult);

      try {
        await webhook.delete('Repent: Malicious webhook detected');
      } catch (error) {
        this.logger.error('Failed to delete malicious webhook', { error, webhookId: webhook.id });
      }
    }
  }

  async handleWebhookDelete(webhook: Webhook): Promise<void> {
    const guild = await this.getGuildFromWebhook(webhook);
    if (!guild || !this.configRepo.isEnabled(guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      guild.id,
      'system',
      'webhook_delete',
      webhook.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(guild, 'webhook_delete', webhook.id, 'webhook', detectionResult);
    }
  }

  async handleWebhookUpdate(_oldWebhook: Webhook, newWebhook: Webhook): Promise<void> {
    const guild = await this.getGuildFromWebhook(newWebhook);
    if (!guild || !this.configRepo.isEnabled(guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      guild.id,
      'system',
      'webhook_update',
      newWebhook.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(guild, 'webhook_update', newWebhook.id, 'webhook', detectionResult);
    }
  }
}
