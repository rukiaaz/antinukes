import { Guild, PermissionFlagsBits } from 'discord.js';
import { LockdownService } from './LockdownService';
import { LoggingService } from './LoggingService';
import { Logger } from '../utils/Logger';
import type { PanicState, DisabledPermission } from '../types';

export class PanicModeService {
  private panicStates: Map<string, PanicState>;
  private lockdown: LockdownService;
  private logging: LoggingService;
  private logger: Logger;

  constructor(lockdown: LockdownService) {
    this.panicStates = new Map();
    this.lockdown = lockdown;
    this.logging = new LoggingService();
    this.logger = Logger.getInstance();
  }

  async enable(guild: Guild): Promise<boolean> {
    if (this.panicStates.has(guild.id)) {
      return false;
    }

    try {
      const disabledPermissions: DisabledPermission[] = [];
      const dangerousPerms = [
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

      const roles = guild.roles.cache.filter(r => !r.managed && r.id !== guild.id);

      for (const [, role] of roles) {
        const hasDangerous = dangerousPerms.some(perm => role.permissions.has(perm));
        if (hasDangerous) {
          const originalPerms = role.permissions.bitfield.toString();
          try {
            await role.setPermissions([], 'Repent panic mode');
            disabledPermissions.push({
              roleId: role.id,
              permissions: originalPerms,
            });
          } catch (error) {
            this.logger.error('Failed to strip role permissions', { error, roleId: role.id });
          }
        }
      }

      await this.lockdown.lockdown(guild);

      const state: PanicState = {
        guildId: guild.id,
        enabled: true,
        lockdownState: null,
        disabledPermissions,
      };

      this.panicStates.set(guild.id, state);

      await this.logging.logInfo(guild, 'PANIC MODE ENABLED', [
        { name: 'Roles Stripped', value: disabledPermissions.length.toString(), inline: true },
        { name: 'Time', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: true },
        { name: 'Status', value: 'All dangerous permissions disabled. Lockdown active.', inline: false },
      ]);

      const owner = await guild.fetchOwner().catch(() => null);
      if (owner) {
        try {
          await owner.send(`**PANIC MODE** has been enabled in **${guild.name}**. All dangerous permissions have been stripped and the server is in lockdown. Use \`/panic off\` in the server to disable.`);
        } catch {
          this.logger.debug('Could not DM owner', { guildId: guild.id });
        }
      }

      this.logger.info('Panic mode enabled', { guildId: guild.id, rolesStripped: disabledPermissions.length });
      return true;
    } catch (error) {
      this.logger.error('Panic mode enable failed', { error, guildId: guild.id });
      return false;
    }
  }

  async disable(guild: Guild): Promise<boolean> {
    const state = this.panicStates.get(guild.id);
    if (!state) {
      return false;
    }

    try {
      for (const perm of state.disabledPermissions) {
        const role = guild.roles.cache.get(perm.roleId);
        if (!role) continue;

        try {
          await role.setPermissions(BigInt(perm.permissions), 'Repent panic mode off');
        } catch (error) {
          this.logger.error('Failed to restore role permissions', { error, roleId: perm.roleId });
        }
      }

      await this.lockdown.unlock(guild);

      this.panicStates.delete(guild.id);

      await this.logging.logInfo(guild, 'Panic Mode Disabled', [
        { name: 'Roles Restored', value: state.disabledPermissions.length.toString(), inline: true },
        { name: 'Time', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: true },
      ]);

      this.logger.info('Panic mode disabled', { guildId: guild.id });
      return true;
    } catch (error) {
      this.logger.error('Panic mode disable failed', { error, guildId: guild.id });
      return false;
    }
  }

  isActive(guildId: string): boolean {
    return this.panicStates.has(guildId);
  }

  getState(guildId: string): PanicState | undefined {
    return this.panicStates.get(guildId);
  }
}
