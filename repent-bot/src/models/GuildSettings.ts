import type { ActionType, GuildConfig, ProtectionConfig } from '../types';
import { DEFAULT_PROTECTIONS } from '../utils/config';
import { get, run } from '../utils/sqlite';

const DEFAULT_PROTECTIONS_OBJ = Object.entries(DEFAULT_PROTECTIONS).reduce(
  (acc, [k, v]) => {
    acc[k as ActionType] = v;
    return acc;
  },
  {} as Record<ActionType, ProtectionConfig>
);

function rowToConfig(row: any): GuildConfig | null {
  if (!row) return null;

  const protectionsParsed = JSON.parse(row.protections_json) as Record<ActionType, ProtectionConfig>;
  const whitelistUsersParsed = JSON.parse(row.whitelist_users_json) as string[];
  const whitelistRolesParsed = JSON.parse(row.whitelist_roles_json) as string[];
  const lockdownChannelsParsed = JSON.parse(row.lockdown_channels_json) as string[];

  return {
    guildId: row.guild_id,
    logChannelId: row.log_channel_id,
    ownerId: row.owner_id,
    protections: protectionsParsed ?? (DEFAULT_PROTECTIONS_OBJ as any),
    whitelistUsers: whitelistUsersParsed ?? [],
    whitelistRoles: whitelistRolesParsed ?? [],
    panicMode: !!row.panic_mode,
    lockdownChannels: lockdownChannelsParsed ?? [],
    setup: !!row.setup,
  };
}

export async function getGuildConfig(guildId: string): Promise<GuildConfig | null> {
  const row = await get<any>(
    `SELECT * FROM guild_settings WHERE guild_id = ?`,
    [guildId]
  );
  return rowToConfig(row);
}

export async function createGuildConfig(guildId: string, ownerId: string): Promise<GuildConfig> {
  const existing = await getGuildConfig(guildId);
  if (existing) return existing;

  await run(
    `INSERT INTO guild_settings\n` +
      `(guild_id, log_channel_id, owner_id, protections_json, whitelist_users_json, whitelist_roles_json, panic_mode, lockdown_channels_json, setup)\n` +
      `VALUES (?, NULL, ?, ?, '[]', '[]', 0, '[]', 0)`,
    [guildId, ownerId, JSON.stringify(DEFAULT_PROTECTIONS_OBJ)]
  );

  const created = await getGuildConfig(guildId);
  if (!created) throw new Error('Failed to create guild config');
  return created;
}

export async function updateGuildConfig(
  guildId: string,
  update: Partial<GuildConfig>
): Promise<GuildConfig | null> {
  const current = await getGuildConfig(guildId);
  if (!current) return null;

  const next: GuildConfig = {
    ...current,
    ...update,
    protections: update.protections ?? current.protections,
    whitelistUsers: update.whitelistUsers ?? current.whitelistUsers,
    whitelistRoles: update.whitelistRoles ?? current.whitelistRoles,
    lockdownChannels: update.lockdownChannels ?? current.lockdownChannels,
  };

  await run(
    `UPDATE guild_settings\n` +
      `SET log_channel_id = ?, owner_id = ?, protections_json = ?, whitelist_users_json = ?, whitelist_roles_json = ?, panic_mode = ?, lockdown_channels_json = ?, setup = ?\n` +
      `WHERE guild_id = ?`,
    [
      next.logChannelId,
      next.ownerId,
      JSON.stringify(next.protections),
      JSON.stringify(next.whitelistUsers),
      JSON.stringify(next.whitelistRoles),
      next.panicMode ? 1 : 0,
      JSON.stringify(next.lockdownChannels),
      next.setup ? 1 : 0,
      guildId,
    ]
  );

  return await getGuildConfig(guildId);
}

export async function getProtectionConfig(
  guildId: string,
  actionType: ActionType
): Promise<ProtectionConfig | null> {
  const cfg = await getGuildConfig(guildId);
  if (!cfg) return null;
  return cfg.protections[actionType] ?? null;
}

export async function setProtectionConfig(
  guildId: string,
  actionType: ActionType,
  protection: Partial<ProtectionConfig>
): Promise<boolean> {
  const cfg = await getGuildConfig(guildId);
  if (!cfg) return false;

  const existing = cfg.protections[actionType] ?? DEFAULT_PROTECTIONS_OBJ[actionType];
  const nextProtection = { ...existing, ...protection };

  const nextProtections = { ...cfg.protections, [actionType]: nextProtection };

  await run(
    `UPDATE guild_settings SET protections_json = ? WHERE guild_id = ?`,
    [JSON.stringify(nextProtections), guildId]
  );

  return true;
}

export async function addWhitelistUser(guildId: string, userId: string): Promise<boolean> {
  const cfg = await getGuildConfig(guildId);
  if (!cfg) return false;
  if (cfg.whitelistUsers.includes(userId)) return false;

  const next = { ...cfg, whitelistUsers: [...cfg.whitelistUsers, userId] };
  await run(
    `UPDATE guild_settings SET whitelist_users_json = ? WHERE guild_id = ?`,
    [JSON.stringify(next.whitelistUsers), guildId]
  );
  return true;
}

export async function removeWhitelistUser(guildId: string, userId: string): Promise<boolean> {
  const cfg = await getGuildConfig(guildId);
  if (!cfg) return false;
  if (!cfg.whitelistUsers.includes(userId)) return false;

  const nextUsers = cfg.whitelistUsers.filter(x => x !== userId);
  await run(
    `UPDATE guild_settings SET whitelist_users_json = ? WHERE guild_id = ?`,
    [JSON.stringify(nextUsers), guildId]
  );
  return true;
}

export async function addWhitelistRole(guildId: string, roleId: string): Promise<boolean> {
  const cfg = await getGuildConfig(guildId);
  if (!cfg) return false;
  if (cfg.whitelistRoles.includes(roleId)) return false;

  const nextRoles = [...cfg.whitelistRoles, roleId];
  await run(
    `UPDATE guild_settings SET whitelist_roles_json = ? WHERE guild_id = ?`,
    [JSON.stringify(nextRoles), guildId]
  );
  return true;
}

export async function removeWhitelistRole(guildId: string, roleId: string): Promise<boolean> {
  const cfg = await getGuildConfig(guildId);
  if (!cfg) return false;
  if (!cfg.whitelistRoles.includes(roleId)) return false;

  const nextRoles = cfg.whitelistRoles.filter(x => x !== roleId);
  await run(
    `UPDATE guild_settings SET whitelist_roles_json = ? WHERE guild_id = ?`,
    [JSON.stringify(nextRoles), guildId]
  );
  return true;
}

export async function setPanicMode(guildId: string, enabled: boolean): Promise<boolean> {
  const cfg = await getGuildConfig(guildId);
  if (!cfg) return false;

  await run(
    `UPDATE guild_settings SET panic_mode = ? WHERE guild_id = ?`,
    [enabled ? 1 : 0, guildId]
  );
  return true;
}

export async function isUserWhitelisted(
  guildId: string,
  userId: string,
  roleIds: string[]
): Promise<boolean> {
  const cfg = await getGuildConfig(guildId);
  if (!cfg) return false;
  if (cfg.whitelistUsers.includes(userId)) return true;
  return roleIds.some(rid => cfg.whitelistRoles.includes(rid));
}

