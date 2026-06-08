import {
  ChannelType,
  type Guild,
  type GuildBasedChannel,
  type Role,
  type Webhook,
  type Emoji,
  type Sticker,
  type CategoryChannel,
  type TextChannel,
  type VoiceChannel,
  type NewsChannel,
  type StageChannel,
  type ForumChannel,
  type MediaChannel,
} from 'discord.js';
import type {
  BackupData,
  ChannelBackup,
  CategoryBackup,
  RoleBackup,
  WebhookBackup,
  EmojiBackup,
  StickerBackup,
  ServerSettingsBackup,
} from '../types';

type BackupableChannel = TextChannel | VoiceChannel | NewsChannel | StageChannel | ForumChannel | MediaChannel;

export class BackupManager {
  public async createBackup(guild: Guild): Promise<BackupData> {
    const channels: ChannelBackup[] = [];
    const categories: CategoryBackup[] = [];

    for (const channel of guild.channels.cache.values()) {
      if (channel.type === ChannelType.GuildCategory) {
        categories.push(this.backupCategory(channel as CategoryChannel));
      } else if (this.isBackupableChannel(channel)) {
        channels.push(this.backupChannel(channel));
      }
    }

    const roles: RoleBackup[] = guild.roles.cache
      .filter(r => !r.managed && r.id !== guild.id)
      .map(r => this.backupRole(r))
      .slice();

    let webhooks: WebhookBackup[] = [];
    try {
      const fetched = await guild.fetchWebhooks();
      webhooks = Array.from(fetched.values()).map(w => this.backupWebhook(w));
    } catch {
      // Skip webhooks if no permission
    }

    const emojis: EmojiBackup[] = Array.from(guild.emojis.cache.values())
      .map(e => this.backupEmoji(e));

    const stickers: StickerBackup[] = Array.from(guild.stickers.cache.values())
      .map(s => this.backupSticker(s));

    const serverSettings = this.backupServerSettings(guild);

    return {
      channels,
      categories,
      roles,
      webhooks,
      emojis,
      stickers,
      serverSettings,
      timestamp: new Date(),
    };
  }

  public async restoreBackup(guild: Guild, backup: BackupData): Promise<void> {
    await this.restoreServerSettings(guild, backup.serverSettings);
    await this.restoreRoles(guild, backup.roles);
    await this.restoreCategories(guild, backup.categories);
    await this.restoreChannels(guild, backup.channels);
  }

  private isBackupableChannel(channel: GuildBasedChannel): channel is BackupableChannel {
    return (
      channel.type === ChannelType.GuildText ||
      channel.type === ChannelType.GuildVoice ||
      channel.type === ChannelType.GuildAnnouncement ||
      channel.type === ChannelType.GuildStageVoice ||
      channel.type === ChannelType.GuildForum ||
      channel.type === ChannelType.GuildMedia
    );
  }

  private backupChannel(channel: BackupableChannel): ChannelBackup {
    const base = {
      id: channel.id,
      name: channel.name,
      type: channel.type,
      parentId: channel.parentId,
      position: channel.position,
      permissionOverwrites: channel.permissionOverwrites.cache.map(o => ({
        id: o.id,
        type: o.type,
        allow: o.allow.bitfield.toString(),
        deny: o.deny.bitfield.toString(),
      })),
    };

    let topic: string | null = null;
    let nsfw = false;
    let rateLimitPerUser = 0;
    let bitrate: number | undefined = undefined;
    let userLimit: number | undefined = undefined;

    if ('topic' in channel && channel.topic !== null) topic = channel.topic;
    if ('nsfw' in channel && typeof channel.nsfw === 'boolean') nsfw = channel.nsfw;
    if ('rateLimitPerUser' in channel && typeof channel.rateLimitPerUser === 'number') {
      rateLimitPerUser = channel.rateLimitPerUser;
    }
    if ('bitrate' in channel && typeof channel.bitrate === 'number') bitrate = channel.bitrate;
    if ('userLimit' in channel && typeof channel.userLimit === 'number') userLimit = channel.userLimit;

    return {
      ...base,
      topic,
      nsfw,
      rateLimitPerUser,
      bitrate,
      userLimit,
    };
  }

  private backupCategory(category: CategoryChannel): CategoryBackup {
    return {
      id: category.id,
      name: category.name,
      position: category.position,
      permissionOverwrites: category.permissionOverwrites.cache.map(o => ({
        id: o.id,
        type: o.type,
        allow: o.allow.bitfield.toString(),
        deny: o.deny.bitfield.toString(),
      })),
    };
  }

  private backupRole(role: Role): RoleBackup {
    return {
      id: role.id,
      name: role.name,
      color: role.color,
      hoist: role.hoist,
      icon: role.iconURL(),
      unicodeEmoji: role.unicodeEmoji,
      position: role.position,
      permissions: role.permissions.bitfield.toString(),
      mentionable: role.mentionable,
    };
  }

  private backupWebhook(webhook: Webhook): WebhookBackup {
    return {
      id: webhook.id,
      channelId: webhook.channelId ?? '',
      name: webhook.name ?? 'Webhook',
      avatar: webhook.avatarURL(),
      token: webhook.token ?? '',
    };
  }

  private backupEmoji(emoji: Emoji): EmojiBackup {
    return {
      id: emoji.id ?? (emoji.name || 'unknown'),
      name: emoji.name ?? 'emoji',
      animated: emoji.animated ?? false,
      url: emoji.imageURL() ?? '',
    };
  }

  private backupSticker(sticker: Sticker): StickerBackup {
    return {
      id: sticker.id,
      name: sticker.name,
      description: sticker.description,
      tags: sticker.tags ?? '',
      type: sticker.type ?? 1,
      formatType: sticker.format,
      url: sticker.url,
    };
  }

  private backupServerSettings(guild: Guild): ServerSettingsBackup {
    return {
      name: guild.name,
      icon: guild.iconURL(),
      banner: guild.bannerURL(),
      description: guild.description,
      verificationLevel: guild.verificationLevel,
      defaultMessageNotifications: guild.defaultMessageNotifications,
      explicitContentFilter: guild.explicitContentFilter,
      systemChannelId: guild.systemChannelId,
      systemChannelFlags: guild.systemChannelFlags.bitfield,
      rulesChannelId: guild.rulesChannelId,
      publicUpdatesChannelId: guild.publicUpdatesChannelId,
      preferredLocale: guild.preferredLocale,
      afkChannelId: guild.afkChannelId,
      afkTimeout: guild.afkTimeout,
    };
  }

  private async restoreServerSettings(
    guild: Guild,
    settings: ServerSettingsBackup | null
  ): Promise<void> {
    if (!settings) return;
    try {
      await guild.edit({
        name: settings.name,
        verificationLevel: settings.verificationLevel ?? undefined,
        defaultMessageNotifications: settings.defaultMessageNotifications ?? undefined,
        explicitContentFilter: settings.explicitContentFilter ?? undefined,
        systemChannel: settings.systemChannelId ?? undefined,
        systemChannelFlags: settings.systemChannelFlags,
        rulesChannel: settings.rulesChannelId ?? undefined,
        publicUpdatesChannel: settings.publicUpdatesChannelId ?? undefined,
        preferredLocale: settings.preferredLocale as never,
        afkChannel: settings.afkChannelId ?? undefined,
        afkTimeout: settings.afkTimeout,
      });
    } catch {
      // Silently fail restoration
    }
  }

  private async restoreRoles(guild: Guild, roles: RoleBackup[]): Promise<void> {
    for (const roleData of roles) {
      const existing = guild.roles.cache.get(roleData.id);
      if (existing) {
        try {
          await existing.edit({
            name: roleData.name,
            color: roleData.color,
            hoist: roleData.hoist,
            permissions: BigInt(roleData.permissions),
            mentionable: roleData.mentionable,
          });
        } catch {
          // Skip uneditable roles
        }
      } else {
        try {
          await guild.roles.create({
            name: roleData.name,
            color: roleData.color,
            hoist: roleData.hoist,
            permissions: BigInt(roleData.permissions),
            mentionable: roleData.mentionable,
            reason: 'Repent auto-recovery',
          });
        } catch {
          // Skip uncreateable roles
        }
      }
    }
  }

  private async restoreCategories(guild: Guild, categories: CategoryBackup[]): Promise<void> {
    for (const catData of categories.sort((a, b) => a.position - b.position)) {
      const existing = guild.channels.cache.get(catData.id);
      if (existing) {
        try {
          await existing.edit({
            name: catData.name,
            position: catData.position,
          });
        } catch {
          // Skip
        }
      } else {
        try {
          await guild.channels.create({
            name: catData.name,
            type: ChannelType.GuildCategory,
            position: catData.position,
            reason: 'Repent auto-recovery',
          });
        } catch {
          // Skip
        }
      }
    }
  }

  private async restoreChannels(guild: Guild, channels: ChannelBackup[]): Promise<void> {
    for (const chData of channels.sort((a, b) => a.position - b.position)) {
      const existing = guild.channels.cache.get(chData.id);
      if (existing) {
        try {
          await existing.edit({
            name: chData.name,
            position: chData.position,
          });
        } catch {
          // Skip
        }
      } else {
        try {
          await guild.channels.create({
            name: chData.name,
            type: chData.type,
            parent: chData.parentId ?? undefined,
            position: chData.position,
            topic: chData.topic ?? undefined,
            nsfw: chData.nsfw,
            rateLimitPerUser: chData.rateLimitPerUser,
            bitrate: chData.bitrate,
            userLimit: chData.userLimit,
            reason: 'Repent auto-recovery',
          });
        } catch {
          // Skip
        }
      }
    }
  }
}
