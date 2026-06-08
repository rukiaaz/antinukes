import { EmbedBuilder, type Guild, type GuildMember, type User, type TextChannel } from 'discord.js';
import { CONFIG } from '../utils/config';
import { getGuildConfig } from '../models/GuildSettings';
import type { ActionType, PunishmentType } from '../types';
import type { Repent } from './Repent';

export class LogHandler {
  constructor(private readonly client: Repent) {}

  public async logProtectionTriggered(
    guild: Guild,
    data: {
      executor: User | GuildMember;
      actionType: ActionType;
      count: number;
      threshold: number;
      punishment: PunishmentType;
      targets: string[];
    }
  ): Promise<void> {
    const config = await getGuildConfig(guild.id);
    if (!config?.logChannelId) return;

    const channel = guild.channels.cache.get(config.logChannelId) as TextChannel | undefined;
    if (!channel?.isTextBased()) return;

    const executorTag = 'user' in data.executor
      ? data.executor.user.tag
      : data.executor.tag;
    const executorId = 'user' in data.executor
      ? data.executor.user.id
      : data.executor.id;

    const embed = new EmbedBuilder()
      .setColor(CONFIG.EMBED_COLOR)
      .setTitle('Protection Triggered')
      .addFields(
        { name: 'User', value: `${executorTag} (${executorId})`, inline: false },
        { name: 'Action', value: this.formatActionType(data.actionType), inline: true },
        { name: 'Count', value: `${data.count}/${data.threshold}`, inline: true },
        { name: 'Punishment', value: this.formatPunishment(data.punishment), inline: true },
        {
          name: 'Targets',
          value: data.targets.length > 0
            ? data.targets.slice(0, 5).join(', ') + (data.targets.length > 5 ? ` +${data.targets.length - 5} more` : '')
            : 'N/A',
          inline: false,
        },
        { name: 'Timestamp', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: false }
      )
      .setTimestamp();

    try {
      await channel.send({ embeds: [embed] });
    } catch {
      // Silently fail if cannot send log
    }
  }

  public async logPunishmentExecuted(
    guild: Guild,
    data: {
      target: User | GuildMember;
      punishment: PunishmentType;
      success: boolean;
      reason: string;
    }
  ): Promise<void> {
    const config = await getGuildConfig(guild.id);
    if (!config?.logChannelId) return;

    const channel = guild.channels.cache.get(config.logChannelId) as TextChannel | undefined;
    if (!channel?.isTextBased()) return;

    const targetTag = 'user' in data.target ? data.target.user.tag : data.target.tag;
    const targetId = 'user' in data.target ? data.target.user.id : data.target.id;

    const embed = new EmbedBuilder()
      .setColor(data.success ? CONFIG.SUCCESS_COLOR : CONFIG.WARNING_COLOR)
      .setTitle(data.success ? 'Punishment Executed' : 'Punishment Failed')
      .addFields(
        { name: 'Target', value: `${targetTag} (${targetId})`, inline: false },
        { name: 'Punishment', value: this.formatPunishment(data.punishment), inline: true },
        { name: 'Reason', value: data.reason, inline: false },
        { name: 'Timestamp', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: false }
      )
      .setTimestamp();

    try {
      await channel.send({ embeds: [embed] });
    } catch {
      // Silently fail
    }
  }

  public async logEmergency(
    guild: Guild,
    data: {
      type: 'lockdown' | 'unlockdown' | 'panic' | 'panic_off';
      triggeredBy: User | GuildMember;
    }
  ): Promise<void> {
    const config = await getGuildConfig(guild.id);
    if (!config?.logChannelId) return;

    const channel = guild.channels.cache.get(config.logChannelId) as TextChannel | undefined;
    if (!channel?.isTextBased()) return;

    const triggeredByTag = 'user' in data.triggeredBy
      ? data.triggeredBy.user.tag
      : data.triggeredBy.tag;

    const titles: Record<string, string> = {
      lockdown: 'Lockdown Activated',
      unlockdown: 'Lockdown Deactivated',
      panic: 'Panic Mode Activated',
      panic_off: 'Panic Mode Deactivated',
    };

    const embed = new EmbedBuilder()
      .setColor(data.type === 'panic' || data.type === 'lockdown' ? CONFIG.PANIC_COLOR : CONFIG.SUCCESS_COLOR)
      .setTitle(titles[data.type] ?? 'Emergency Action')
      .addFields(
        { name: 'Triggered By', value: triggeredByTag, inline: false },
        { name: 'Timestamp', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: false }
      )
      .setTimestamp();

    try {
      await channel.send({ embeds: [embed] });
    } catch {
      // Silently fail
    }
  }

  public async logRecovery(
    guild: Guild,
    data: {
      type: string;
      restoredCount: number;
    }
  ): Promise<void> {
    const config = await getGuildConfig(guild.id);
    if (!config?.logChannelId) return;

    const channel = guild.channels.cache.get(config.logChannelId) as TextChannel | undefined;
    if (!channel?.isTextBased()) return;

    const embed = new EmbedBuilder()
      .setColor(CONFIG.SUCCESS_COLOR)
      .setTitle('Auto Recovery')
      .addFields(
        { name: 'Type', value: data.type, inline: true },
        { name: 'Restored', value: `${data.restoredCount} items`, inline: true },
        { name: 'Timestamp', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: false }
      )
      .setTimestamp();

    try {
      await channel.send({ embeds: [embed] });
    } catch {
      // Silently fail
    }
  }

  private formatActionType(actionType: ActionType): string {
    return actionType
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, str => str.toUpperCase());
  }

  private formatPunishment(punishment: PunishmentType): string {
    const map: Record<PunishmentType, string> = {
      ban: 'Ban',
      kick: 'Kick',
      timeout: 'Timeout',
      removeRoles: 'Remove Dangerous Roles',
    };
    return map[punishment] ?? punishment;
  }
}
