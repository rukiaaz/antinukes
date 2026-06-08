import {
  GuildMember,
  type Guild,
  type User,
} from 'discord.js';
import { CONFIG } from '../utils/config';
import type { PunishmentType, ActionType } from '../types';
import type { Repent } from './Repent';

export class PunishmentHandler {
  constructor(private readonly client: Repent) {}

  public async execute(
    guild: Guild,
    target: GuildMember | User,
    punishment: PunishmentType,
    actionType: ActionType,
    reason: string = 'Repent anti-nuke protection'
  ): Promise<boolean> {
    try {
      const member = target instanceof GuildMember
        ? target
        : await guild.members.fetch(target.id).catch(() => null);

      if (member) {
        if (guild.ownerId === member.id) return false;
        const botMember = guild.members.cache.get(this.client.user?.id ?? '');
        if (botMember && member.roles.highest.position >= botMember.roles.highest.position) {
          return false;
        }
      }

      switch (punishment) {
        case 'ban':
          return await this.ban(guild, target, reason);
        case 'kick':
          return await this.kick(guild, target, reason);
        case 'timeout':
          return await this.timeout(guild, target, actionType, reason);
        case 'removeRoles':
          return await this.removeRoles(guild, target, reason);
        default:
          return false;
      }
    } catch {
      return false;
    }
  }

  private async ban(guild: Guild, target: GuildMember | User, reason: string): Promise<boolean> {
    try {
      await guild.members.ban(target.id, { reason, deleteMessageSeconds: 0 });
      return true;
    } catch {
      return false;
    }
  }

  private async kick(guild: Guild, target: GuildMember | User, reason: string): Promise<boolean> {
    try {
      const member = target instanceof GuildMember
        ? target
        : await guild.members.fetch(target.id);
      await member.kick(reason);
      return true;
    } catch {
      return false;
    }
  }

  private async timeout(
    guild: Guild,
    target: GuildMember | User,
    actionType: ActionType,
    reason: string
  ): Promise<boolean> {
    try {
      const { getProtectionConfig } = await import('../models/GuildSettings');
      const config = await getProtectionConfig(guild.id, actionType);
      const durationMs = (config?.timeoutDuration ?? CONFIG.DEFAULT_TIMEOUT_DURATION) * 1000;

      const member = target instanceof GuildMember
        ? target
        : await guild.members.fetch(target.id);
      await member.timeout(durationMs, reason);
      return true;
    } catch {
      return false;
    }
  }

  private async removeRoles(
    guild: Guild,
    target: GuildMember | User,
    reason: string
  ): Promise<boolean> {
    try {
      const member = target instanceof GuildMember
        ? target
        : await guild.members.fetch(target.id);

      const dangerousRoles = member.roles.cache.filter(role => {
        const perms = role.permissions;
        return CONFIG.DANGEROUS_PERMISSIONS.some(dp =>
          perms.has(dp as unknown as bigint)
        );
      });

      if (dangerousRoles.size === 0) return false;

      await member.roles.remove(dangerousRoles, reason);
      return true;
    } catch {
      return false;
    }
  }

  public async removeDangerousPermissions(guild: Guild, roleId: string): Promise<boolean> {
    try {
      const role = guild.roles.cache.get(roleId);
      if (!role) return false;

      const dangerousPerms = CONFIG.DANGEROUS_PERMISSIONS.map(dp =>
        dp as unknown as bigint
      );
      const newPerms = role.permissions.bitfield;
      const filtered = dangerousPerms.reduce((acc, perm) => {
        return acc & ~perm;
      }, newPerms);

      if (filtered === newPerms) return false;

      await role.setPermissions(filtered, 'Repent: removing dangerous permissions');
      return true;
    } catch {
      return false;
    }
  }
}
