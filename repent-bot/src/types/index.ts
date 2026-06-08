import type { GuildMember, User, Role, GuildChannel, CategoryChannel, Webhook, Emoji, Sticker } from 'discord.js';

export type PunishmentType = 'ban' | 'kick' | 'timeout' | 'removeRoles';

export type ActionType =
  | 'channelDelete'
  | 'channelCreate'
  | 'channelUpdate'
  | 'categoryDelete'
  | 'categoryUpdate'
  | 'roleDelete'
  | 'roleCreate'
  | 'roleUpdate'
  | 'permissionEscalation'
  | 'webhookCreate'
  | 'webhookDelete'
  | 'webhookUpdate'
  | 'massBan'
  | 'massKick'
  | 'massTimeout'
  | 'botAdd'
  | 'emojiDelete'
  | 'emojiCreate'
  | 'stickerDelete'
  | 'stickerCreate'
  | 'serverUpdate';

export interface ProtectionConfig {
  enabled: boolean;
  threshold: number;
  windowSeconds: number;
  punishment: PunishmentType;
  timeoutDuration?: number;
}

export interface GuildConfig {
  guildId: string;
  logChannelId: string | null;
  ownerId: string;
  protections: Record<ActionType, ProtectionConfig>;
  whitelistUsers: string[];
  whitelistRoles: string[];
  panicMode: boolean;
  lockdownChannels: string[];
  setup: boolean;
}

export interface BackupData {
  channels: ChannelBackup[];
  categories: CategoryBackup[];
  roles: RoleBackup[];
  webhooks: WebhookBackup[];
  emojis: EmojiBackup[];
  stickers: StickerBackup[];
  serverSettings: ServerSettingsBackup | null;
  timestamp: Date;
}

export interface ChannelBackup {
  id: string;
  name: string;
  type: number;
  parentId: string | null;
  position: number;
  permissionOverwrites: {
    id: string;
    type: number;
    allow: string;
    deny: string;
  }[];
  topic: string | null;
  nsfw: boolean;
  rateLimitPerUser: number;
  bitrate?: number;
  userLimit?: number;
}

export interface CategoryBackup {
  id: string;
  name: string;
  position: number;
  permissionOverwrites: {
    id: string;
    type: number;
    allow: string;
    deny: string;
  }[];
}

export interface RoleBackup {
  id: string;
  name: string;
  color: number;
  hoist: boolean;
  icon: string | null;
  unicodeEmoji: string | null;
  position: number;
  permissions: string;
  mentionable: boolean;
}

export interface WebhookBackup {
  id: string;
  channelId: string;
  name: string;
  avatar: string | null;
  token: string;
}

export interface EmojiBackup {
  id: string;
  name: string;
  animated: boolean;
  url: string;
}

export interface StickerBackup {
  id: string;
  name: string;
  description: string | null;
  tags: string;
  type: number;
  formatType: number;
  url: string;
}

export interface ServerSettingsBackup {
  name: string;
  icon: string | null;
  banner: string | null;
  description: string | null;
  verificationLevel: number | null;
  defaultMessageNotifications: number | null;
  explicitContentFilter: number | null;
  systemChannelId: string | null;
  systemChannelFlags: number;
  rulesChannelId: string | null;
  publicUpdatesChannelId: string | null;
  preferredLocale: string;
  afkChannelId: string | null;
  afkTimeout: number;
}

export interface ActionRecord {
  userId: string;
  actionType: ActionType;
  targetId: string;
  timestamp: number;
}

export interface DetectionResult {
  triggered: boolean;
  executor: User | null;
  actionType: ActionType;
  count: number;
  threshold: number;
  punishment: PunishmentType;
  targets?: string[];
}

export interface ProtectionTriggeredEvent {
  guildId: string;
  executor: User | GuildMember;
  actionType: ActionType;
  count: number;
  threshold: number;
  punishment: PunishmentType;
  targets: string[];
  timestamp: Date;
}

export interface LogEntry {
  action: string;
  executor: User | GuildMember;
  target: string;
  punishment: string;
  count?: string;
  threshold?: string;
  timestamp: Date;
}
