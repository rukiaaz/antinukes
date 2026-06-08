import { EmbedBuilder, Guild, User, TextChannel, ChannelType } from 'discord.js';
import { GuildConfigRepo } from '../database/GuildConfigRepo';
import { Logger } from '../utils/Logger';
import type { ProtectionEvent } from '../types';

export class LoggingService {
  private configRepo: GuildConfigRepo;
  private logger: Logger;

  constructor() {
    this.configRepo = new GuildConfigRepo();
    this.logger = Logger.getInstance();
  }

  async logProtection(event: ProtectionEvent): Promise<void> {
    const config = this.configRepo.get(event.guild.id);
    if (!config?.logChannelId) return;

    try {
      const channel = await event.guild.channels.fetch(config.logChannelId);
      if (!channel || channel.type !== ChannelType.GuildText) return;

      const embed = new EmbedBuilder()
        .setColor(0xFF0000)
        .setTitle('Protection Triggered')
        .addFields(
          { name: 'User', value: `${event.executor.tag} (<@${event.executor.id}>)`, inline: true },
          { name: 'Action', value: this.formatAction(event.action), inline: true },
          { name: 'Target', value: event.targetId ? `<${event.targetType === 'channel' ? '#' : '@&'}${event.targetId}>` : 'N/A', inline: true },
          { name: 'Count', value: event.detectionResult.count.toString(), inline: true },
          { name: 'Threshold', value: `${event.detectionResult.threshold} in ${event.detectionResult.window}s`, inline: true },
          { name: 'Punishment', value: this.formatPunishment(config.punishmentType), inline: true },
          { name: 'Time', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: false }
        )
        .setTimestamp();

      await (channel as TextChannel).send({ embeds: [embed] });
    } catch (error) {
      this.logger.error('Failed to send protection log', {
        error,
        guildId: event.guild.id,
        logChannelId: config.logChannelId,
      });
    }
  }

  async logPunishment(guild: Guild, user: User, action: string, success: boolean, error?: string): Promise<void> {
    const config = this.configRepo.get(guild.id);
    if (!config?.logChannelId) return;

    try {
      const channel = await guild.channels.fetch(config.logChannelId);
      if (!channel || channel.type !== ChannelType.GuildText) return;

      const embed = new EmbedBuilder()
        .setColor(success ? 0x00FF00 : 0xFF0000)
        .setTitle(success ? 'Punishment Applied' : 'Punishment Failed')
        .addFields(
          { name: 'User', value: `${user.tag} (<@${user.id}>)`, inline: true },
          { name: 'Action', value: action, inline: true },
          ...(error ? [{ name: 'Error', value: error, inline: false }] : [])
        )
        .setTimestamp();

      await (channel as TextChannel).send({ embeds: [embed] });
    } catch (err) {
      this.logger.error('Failed to send punishment log', { error: err, guildId: guild.id });
    }
  }

  async logRecovery(guild: Guild, itemType: string, itemName: string, success: boolean): Promise<void> {
    const config = this.configRepo.get(guild.id);
    if (!config?.logChannelId) return;

    try {
      const channel = await guild.channels.fetch(config.logChannelId);
      if (!channel || channel.type !== ChannelType.GuildText) return;

      const embed = new EmbedBuilder()
        .setColor(success ? 0x00FF00 : 0xFFA500)
        .setTitle(success ? 'Recovery Successful' : 'Recovery Failed')
        .addFields(
          { name: 'Type', value: itemType, inline: true },
          { name: 'Name', value: itemName, inline: true }
        )
        .setTimestamp();

      await (channel as TextChannel).send({ embeds: [embed] });
    } catch (error) {
      this.logger.error('Failed to send recovery log', { error, guildId: guild.id });
    }
  }

  async logInfo(guild: Guild, title: string, fields: { name: string; value: string; inline?: boolean }[]): Promise<void> {
    const config = this.configRepo.get(guild.id);
    if (!config?.logChannelId) return;

    try {
      const channel = await guild.channels.fetch(config.logChannelId);
      if (!channel || channel.type !== ChannelType.GuildText) return;

      const embed = new EmbedBuilder()
        .setColor(0x3498DB)
        .setTitle(title)
        .addFields(fields)
        .setTimestamp();

      await (channel as TextChannel).send({ embeds: [embed] });
    } catch (error) {
      this.logger.error('Failed to send info log', { error, guildId: guild.id });
    }
  }

  private formatAction(action: string): string {
    return action
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  private formatPunishment(type: string): string {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
}
