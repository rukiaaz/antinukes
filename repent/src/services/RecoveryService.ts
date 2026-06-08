import {
  Guild,
  ChannelType,
  TextChannel,
  ForumChannel,
  NewsChannel,
} from 'discord.js';
import { SnapshotRepo } from '../database/SnapshotRepo';
import { LoggingService } from './LoggingService';
import { Logger } from '../utils/Logger';
import type {
  SnapshotData,
  ChannelSnapshot,
  RoleSnapshot,
} from '../types';

export class RecoveryService {
  private snapshotRepo: SnapshotRepo;
  private logging: LoggingService;
  private logger: Logger;

  constructor() {
    this.snapshotRepo = new SnapshotRepo();
    this.logging = new LoggingService();
    this.logger = Logger.getInstance();
  }

  async createSnapshot(guild: Guild, name?: string): Promise<boolean> {
    try {
      const data = await this.captureGuildState(guild);
      const snapshotName = name || `auto-${Date.now()}`;
      return this.snapshotRepo.create(guild.id, snapshotName, data);
    } catch (error) {
      this.logger.error('Failed to create snapshot', { error, guildId: guild.id });
      return false;
    }
  }

  async restoreFromSnapshot(guild: Guild): Promise<boolean> {
    const snapshot = this.snapshotRepo.getLatest(guild.id);
    if (!snapshot) {
      this.logger.warn('No snapshot found for guild', { guildId: guild.id });
      return false;
    }

    try {
      await this.restoreRoles(guild, snapshot.data.roles);
      await this.restoreCategories(guild, snapshot.data.categories);
      await this.restoreChannels(guild, snapshot.data.channels);
      await this.restoreEmojis(guild, snapshot.data.emojis);
      await this.restoreStickers(guild, snapshot.data.stickers);
      await this.restoreGuildSettings(guild, snapshot.data.guildSettings);

      this.logger.info('Snapshot restored', { guildId: guild.id, snapshotId: snapshot.id });
      return true;
    } catch (error) {
      this.logger.error('Failed to restore snapshot', { error, guildId: guild.id });
      return false;
    }
  }

  async restoreChannel(guild: Guild, channelSnapshot: ChannelSnapshot): Promise<boolean> {
    try {
      await guild.channels.create({
        name: channelSnapshot.name,
        type: channelSnapshot.type,
        parent: channelSnapshot.parentId || undefined,
        position: channelSnapshot.position,
        topic: channelSnapshot.topic || undefined,
        nsfw: channelSnapshot.nsfw,
        rateLimitPerUser: channelSnapshot.slowmode,
        permissionOverwrites: channelSnapshot.permissionOverwrites.map(ow => ({
          id: ow.id,
          type: ow.type as 0 | 1,
          allow: BigInt(ow.allow),
          deny: BigInt(ow.deny),
        })),
      });

      await this.logging.logRecovery(guild, 'Channel', channelSnapshot.name, true);
      return true;
    } catch (error) {
      this.logger.error('Failed to restore channel', { error, guildId: guild.id, name: channelSnapshot.name });
      await this.logging.logRecovery(guild, 'Channel', channelSnapshot.name, false);
      return false;
    }
  }

  async restoreRole(guild: Guild, roleSnapshot: RoleSnapshot): Promise<boolean> {
    try {
      await guild.roles.create({
        name: roleSnapshot.name,
        color: roleSnapshot.color,
        hoist: roleSnapshot.hoist,
        position: roleSnapshot.position,
        permissions: BigInt(roleSnapshot.permissions),
        mentionable: roleSnapshot.mentionable,
        reason: 'Repent auto-recovery',
      });

      await this.logging.logRecovery(guild, 'Role', roleSnapshot.name, true);
      return true;
    } catch (error) {
      this.logger.error('Failed to restore role', { error, guildId: guild.id, name: roleSnapshot.name });
      await this.logging.logRecovery(guild, 'Role', roleSnapshot.name, false);
      return false;
    }
  }

  private async captureGuildState(guild: Guild): Promise<SnapshotData> {
    const channels: ChannelSnapshot[] = [];
    const categories: any[] = [];

    for (const [, channel] of guild.channels.cache) {
      if (channel.type === ChannelType.GuildCategory) {
        categories.push({
          id: channel.id,
          name: channel.name,
          position: channel.position,
          permissionOverwrites: channel.permissionOverwrites.cache.map(ow => ({
            id: ow.id,
            type: ow.type,
            allow: ow.allow.bitfield.toString(),
            deny: ow.deny.bitfield.toString(),
          })),
        });
      } else if ('permissionOverwrites' in channel) {
        const textChannel = channel as TextChannel | NewsChannel | ForumChannel;
        channels.push({
          id: channel.id,
          name: channel.name,
          type: channel.type,
          parentId: channel.parentId,
          position: (channel as any).position || 0,
          topic: 'topic' in textChannel ? textChannel.topic : null,
          nsfw: 'nsfw' in textChannel ? textChannel.nsfw : false,
          slowmode: 'rateLimitPerUser' in textChannel ? (textChannel.rateLimitPerUser ?? 0) : 0,
          permissionOverwrites: channel.permissionOverwrites.cache.map((ow: any) => ({
            id: ow.id,
            type: ow.type,
            allow: ow.allow.bitfield.toString(),
            deny: ow.deny.bitfield.toString(),
          })),
        });
      }
    }

    const roles: RoleSnapshot[] = guild.roles.cache
      .filter(r => !r.managed && r.id !== guild.id)
      .map(role => ({
        id: role.id,
        name: role.name,
        color: role.color,
        hoist: role.hoist,
        position: role.position,
        permissions: role.permissions.bitfield.toString(),
        mentionable: role.mentionable,
        icon: role.icon,
        unicodeEmoji: role.unicodeEmoji,
      }));

    const emojis = guild.emojis.cache.map(e => ({
      id: e.id,
      name: e.name || 'unknown',
      animated: e.animated,
      url: e.imageURL(),
    }));

    const stickers = guild.stickers.cache.map(s => ({
      id: s.id,
      name: s.name,
      description: s.description,
      tags: s.tags || '',
      type: s.type ?? 0,
      formatType: s.format,
      url: s.url,
    }));

    return {
      channels,
      categories,
      roles,
      emojis,
      stickers,
      guildSettings: {
        name: guild.name,
        icon: guild.iconURL(),
        banner: guild.bannerURL(),
        splash: guild.splashURL(),
        description: guild.description,
        verificationLevel: guild.verificationLevel,
        defaultMessageNotifications: guild.defaultMessageNotifications,
        explicitContentFilter: guild.explicitContentFilter,
        vanityUrlCode: guild.vanityURLCode,
      },
    };
  }

  private async restoreRoles(guild: Guild, roles: RoleSnapshot[]): Promise<void> {
    const existingRoleNames = new Set(guild.roles.cache.map(r => r.name));

    for (const roleData of roles) {
      if (existingRoleNames.has(roleData.name)) continue;
      await this.restoreRole(guild, roleData);
    }
  }

  private async restoreCategories(guild: Guild, categories: any[]): Promise<void> {
    for (const catData of categories) {
      const existing = guild.channels.cache.find(
        c => c.type === ChannelType.GuildCategory && c.name === catData.name
      );
      if (existing) continue;

      try {
        await guild.channels.create({
          name: catData.name,
          type: ChannelType.GuildCategory,
          position: catData.position,
          permissionOverwrites: catData.permissionOverwrites.map((ow: any) => ({
            id: ow.id,
            type: ow.type as 0 | 1,
            allow: BigInt(ow.allow),
            deny: BigInt(ow.deny),
          })),
          reason: 'Repent auto-recovery',
        });
      } catch (error) {
        this.logger.error('Failed to restore category', { error, guildId: guild.id, name: catData.name });
      }
    }
  }

  private async restoreChannels(guild: Guild, channels: ChannelSnapshot[]): Promise<void> {
    const existingChannelNames = new Set(guild.channels.cache.map(c => c.name));

    for (const chData of channels) {
      if (existingChannelNames.has(chData.name)) continue;
      await this.restoreChannel(guild, chData);
    }
  }

  private async restoreEmojis(guild: Guild, emojis: any[]): Promise<void> {
    for (const emoji of emojis) {
      const existing = guild.emojis.cache.find(e => e.name === emoji.name);
      if (existing) continue;

      try {
        await guild.emojis.create({
          attachment: emoji.url,
          name: emoji.name,
          reason: 'Repent auto-recovery',
        });
      } catch (error) {
        this.logger.error('Failed to restore emoji', { error, guildId: guild.id, name: emoji.name });
      }
    }
  }

  private async restoreStickers(guild: Guild, stickers: any[]): Promise<void> {
    for (const sticker of stickers) {
      const existing = guild.stickers.cache.find(s => s.name === sticker.name);
      if (existing) continue;

      try {
        await guild.stickers.create({
          file: sticker.url,
          name: sticker.name,
          tags: sticker.tags,
          description: sticker.description || undefined,
          reason: 'Repent auto-recovery',
        });
      } catch (error) {
        this.logger.error('Failed to restore sticker', { error, guildId: guild.id, name: sticker.name });
      }
    }
  }

  private async restoreGuildSettings(guild: Guild, settings: any): Promise<void> {
    try {
      const updateData: any = {};
      if (settings.name && settings.name !== guild.name) updateData.name = settings.name;
      if (settings.verificationLevel !== null && settings.verificationLevel !== guild.verificationLevel) {
        updateData.verificationLevel = settings.verificationLevel;
      }

      if (Object.keys(updateData).length > 0) {
        await guild.edit(updateData);
      }
    } catch (error) {
      this.logger.error('Failed to restore guild settings', { error, guildId: guild.id });
    }
  }
}
