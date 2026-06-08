import {
  Guild,
  GuildMember,
  User,
  PermissionFlagsBits,
  RESTJSONErrorCodes,
} from 'discord.js';
import { Logger } from '../utils/Logger';
import { GuildConfigRepo } from '../database/GuildConfigRepo';
import type { PunishmentType, PunishmentResult } from '../types';

export class PunishmentService {
  private logger: Logger;
  private configRepo: GuildConfigRepo;

  constructor() {
    this.logger = Logger.getInstance();
    this.configRepo = new GuildConfigRepo();
  }

  async punish(
    guild: Guild,
    target: GuildMember | User,
    reason: string
  ): Promise<PunishmentResult> {
    const config = this.configRepo.get(guild.id);
    const punishmentType = config?.punishmentType || 'ban';

    try {
      switch (punishmentType) {
        case 'remove_roles':
          return await this.removeDangerousRoles(guild, target, reason);
        case 'timeout':
          return await this.timeout(guild, target, reason);
        case 'kick':
          return await this.kick(guild, target, reason);
        case 'ban':
          return await this.ban(guild, target, reason);
        default:
          return await this.ban(guild, target, reason);
      }
    } catch (error: any) {
      this.logger.error('Punishment failed', {
        error,
        guildId: guild.id,
        targetId: target.id,
        punishmentType,
      });
      return {
        success: false,
        action: punishmentType,
        error: error.message || 'Unknown error',
      };
    }
  }

  private async removeDangerousRoles(
    guild: Guild,
    target: GuildMember | User,
    reason: string
  ): Promise<PunishmentResult> {
    try {
      let member: GuildMember | undefined;

      if (target instanceof GuildMember) {
        member = target;
      } else {
        member = await guild.members.fetch(target.id).catch(() => undefined);
      }

      if (!member) {
        return { success: false, action: 'remove_roles', error: 'Member not found' };
      }

      const dangerousPermissions = [
        PermissionFlagsBits.Administrator,
        PermissionFlagsBits.ManageGuild,
        PermissionFlagsBits.ManageRoles,
        PermissionFlagsBits.ManageChannels,
        PermissionFlagsBits.BanMembers,
        PermissionFlagsBits.KickMembers,
        PermissionFlagsBits.ManageWebhooks,
        PermissionFlagsBits.ManageEmojisAndStickers,
        PermissionFlagsBits.ManageEvents,
        PermissionFlagsBits.ModerateMembers,
      ];

      const rolesToRemove = member.roles.cache.filter(role => {
        return dangerousPermissions.some(perm => role.permissions.has(perm));
      });

      if (rolesToRemove.size === 0) {
        return { success: true, action: 'remove_roles', error: 'No dangerous roles found' };
      }

      for (const [, role] of rolesToRemove) {
        await member.roles.remove(role, reason);
      }

      this.logger.info('Removed dangerous roles', {
        guildId: guild.id,
        targetId: target.id,
        roleCount: rolesToRemove.size,
      });

      return { success: true, action: 'remove_roles' };
    } catch (error: any) {
      return { success: false, action: 'remove_roles', error: error.message };
    }
  }

  private async timeout(
    guild: Guild,
    target: GuildMember | User,
    reason: string
  ): Promise<PunishmentResult> {
    try {
      let member: GuildMember | undefined;

      if (target instanceof GuildMember) {
        member = target;
      } else {
        member = await guild.members.fetch(target.id).catch(() => undefined);
      }

      if (!member) {
        return { success: false, action: 'timeout', error: 'Member not found' };
      }

      await member.timeout(2419200000, reason);
      this.logger.info('Timed out user', { guildId: guild.id, targetId: target.id });
      return { success: true, action: 'timeout' };
    } catch (error: any) {
      return { success: false, action: 'timeout', error: error.message };
    }
  }

  private async kick(
    guild: Guild,
    target: GuildMember | User,
    reason: string
  ): Promise<PunishmentResult> {
    try {
      if (target instanceof GuildMember) {
        await target.kick(reason);
      } else {
        const member = await guild.members.fetch(target.id);
        await member.kick(reason);
      }
      this.logger.info('Kicked user', { guildId: guild.id, targetId: target.id });
      return { success: true, action: 'kick' };
    } catch (error: any) {
      if (error.code === RESTJSONErrorCodes.UnknownMember) {
        return { success: false, action: 'kick', error: 'Member not found' };
      }
      return { success: false, action: 'kick', error: error.message };
    }
  }

  private async ban(
    guild: Guild,
    target: GuildMember | User,
    reason: string
  ): Promise<PunishmentResult> {
    try {
      await guild.members.ban(target.id, { reason, deleteMessageSeconds: 0 });
      this.logger.info('Banned user', { guildId: guild.id, targetId: target.id });
      return { success: true, action: 'ban' };
    } catch (error: any) {
      return { success: false, action: 'ban', error: error.message };
    }
  }

  async canPunish(guild: Guild, targetId: string): Promise<boolean> {
    try {
      const me = await guild.members.fetchMe();
      if (!me) return false;

      const target = await guild.members.fetch(targetId).catch(() => null);
      if (!target) return true;

      if (target.id === guild.ownerId) return false;
      if (target.permissions.has(PermissionFlagsBits.Administrator)) {
        return me.permissions.has(PermissionFlagsBits.Administrator);
      }

      return me.roles.highest.position > target.roles.highest.position;
    } catch {
      return false;
    }
  }

  getPunishmentType(guildId: string): PunishmentType {
    const config = this.configRepo.get(guildId);
    return config?.punishmentType || 'ban';
  }
}
