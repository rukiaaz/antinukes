import { Guild, Role, User } from 'discord.js';

export type PunishmentType = 'remove_roles' | 'timeout' | 'kick' | 'ban';

export interface GuildConfig {
  guildId: string;
  logChannelId: string | null;
  punishmentType: PunishmentType;
  enabled: boolean;
  createdAt: number;
  updatedAt: number;
}

export interface ThresholdConfig {
  guildId: string;
  channelDeleteLimit: number;
  channelDeleteWindow: number;
  channelCreateLimit: number;
  channelCreateWindow: number;
  channelUpdateLimit: number;
  channelUpdateWindow: number;
  roleDeleteLimit: number;
  roleDeleteWindow: number;
  roleCreateLimit: number;
  roleCreateWindow: number;
  roleUpdateLimit: number;
  roleUpdateWindow: number;
  webhookCreateLimit: number;
  webhookCreateWindow: number;
  webhookDeleteLimit: number;
  webhookDeleteWindow: number;
  webhookUpdateLimit: number;
  webhookUpdateWindow: number;
  banLimit: number;
  banWindow: number;
  kickLimit: number;
  kickWindow: number;
  timeoutLimit: number;
  timeoutWindow: number;
  botAddLimit: number;
  botAddWindow: number;
}

export interface ThresholdValues {
  limit: number;
  window: number;
}

export interface ActionRecord {
  id?: number;
  guildId: string;
  userId: string;
  action: TrackedAction;
  targetId: string | null;
  timestamp: number;
}

export type TrackedAction =
  | 'channel_delete'
  | 'channel_create'
  | 'channel_update'
  | 'role_delete'
  | 'role_create'
  | 'role_update'
  | 'webhook_create'
  | 'webhook_delete'
  | 'webhook_update'
  | 'ban'
  | 'kick'
  | 'timeout'
  | 'bot_add'
  | 'emoji_delete'
  | 'emoji_create'
  | 'emoji_update'
  | 'sticker_delete'
  | 'sticker_create'
  | 'sticker_update'
  | 'guild_update'
  | 'member_role_update'
  | 'member_nickname_update'
  | 'permission_escalation';

export interface WhitelistEntry {
  id?: number;
  guildId: string;
  targetId: string;
  targetType: 'user' | 'role';
  addedBy: string;
  addedAt: number;
}

export interface Snapshot {
  id?: number;
  guildId: string;
  name: string;
  data: SnapshotData;
  createdAt: number;
}

export interface SnapshotData {
  channels: ChannelSnapshot[];
  categories: CategorySnapshot[];
  roles: RoleSnapshot[];
  emojis: EmojiSnapshot[];
  stickers: StickerSnapshot[];
  guildSettings: GuildSettingsSnapshot;
}

export interface ChannelSnapshot {
  id: string;
  name: string;
  type: number;
  parentId: string | null;
  position: number;
  topic: string | null;
  nsfw: boolean;
  slowmode: number;
  permissionOverwrites: PermissionOverwriteSnapshot[];
}

export interface CategorySnapshot {
  id: string;
  name: string;
  position: number;
  permissionOverwrites: PermissionOverwriteSnapshot[];
}

export interface PermissionOverwriteSnapshot {
  id: string;
  type: number;
  allow: string;
  deny: string;
}

export interface RoleSnapshot {
  id: string;
  name: string;
  color: number;
  hoist: boolean;
  position: number;
  permissions: string;
  mentionable: boolean;
  icon: string | null;
  unicodeEmoji: string | null;
}

export interface EmojiSnapshot {
  id: string;
  name: string;
  animated: boolean;
  url: string;
}

export interface StickerSnapshot {
  id: string;
  name: string;
  description: string | null;
  tags: string;
  type: number;
  formatType: number;
  url: string;
}

export interface GuildSettingsSnapshot {
  name: string;
  icon: string | null;
  banner: string | null;
  splash: string | null;
  description: string | null;
  verificationLevel: number | null;
  defaultMessageNotifications: number | null;
  explicitContentFilter: number | null;
  vanityUrlCode: string | null;
}

export interface LockdownState {
  id?: number;
  guildId: string;
  channelPermissions: LockdownChannelPermission[];
  createdAt: number;
}

export interface LockdownChannelPermission {
  channelId: string;
  previousPermissions: ChannelPermissionState[];
}

export interface ChannelPermissionState {
  roleOrUserId: string;
  type: number;
  allow: string | null;
  deny: string | null;
}

export interface PanicState {
  guildId: string;
  enabled: boolean;
  lockdownState: LockdownState | null;
  disabledPermissions: DisabledPermission[];
}

export interface DisabledPermission {
  roleId: string;
  permissions: string;
}

export interface DetectionResult {
  triggered: boolean;
  userId: string;
  action: TrackedAction;
  count: number;
  threshold: number;
  window: number;
}

export interface ProtectionEvent {
  guild: Guild;
  executor: User;
  action: TrackedAction;
  targetId: string | null;
  targetType: string;
  detectionResult: DetectionResult;
}

export interface PunishmentResult {
  success: boolean;
  action: string;
  error?: string;
}

export interface LogEntry {
  title: string;
  user: User;
  action: string;
  target: string;
  count: number;
  threshold: number;
  punishment: string;
  time: string;
  guild: Guild;
}

export const DANGEROUS_PERMISSIONS = [
  'Administrator',
  'ManageGuild',
  'ManageRoles',
  'ManageChannels',
  'BanMembers',
  'KickMembers',
  'ManageWebhooks',
  'ManageEmojisAndStickers',
  'ManageEvents',
  'ModerateMembers',
] as const;

export type DangerousPermission = (typeof DANGEROUS_PERMISSIONS)[number];

export interface PermissionEscalationEvent {
  guild: Guild;
  executor: User;
  targetRole: Role;
  grantedPermissions: DangerousPermission[];
}
