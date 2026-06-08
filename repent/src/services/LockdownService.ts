import {
  Guild,
  ChannelType,
} from 'discord.js';
import { Logger } from '../utils/Logger';
import { LoggingService } from './LoggingService';
import type { LockdownState, LockdownChannelPermission, ChannelPermissionState } from '../types';

export class LockdownService {
  private lockdownStates: Map<string, LockdownState>;
  private logger: Logger;
  private logging: LoggingService;

  constructor() {
    this.lockdownStates = new Map();
    this.logger = Logger.getInstance();
    this.logging = new LoggingService();
  }

  async lockdown(guild: Guild): Promise<boolean> {
    if (this.lockdownStates.has(guild.id)) {
      return false;
    }

    try {
      const channelPermissions: LockdownChannelPermission[] = [];

      const channels = guild.channels.cache.filter(channel =>
        channel.type === ChannelType.GuildText ||
        channel.type === ChannelType.GuildVoice ||
        channel.type === ChannelType.GuildAnnouncement ||
        channel.type === ChannelType.GuildStageVoice ||
        channel.type === ChannelType.GuildForum
      );

      for (const [, channel] of channels) {
        const previousPermissions: ChannelPermissionState[] = [];

        if ('permissionOverwrites' in channel && channel.permissionOverwrites) {
          for (const [, ow] of channel.permissionOverwrites.cache) {
            previousPermissions.push({
              roleOrUserId: ow.id,
              type: ow.type,
              allow: ow.allow.bitfield.toString(),
              deny: ow.deny.bitfield.toString(),
            });
          }

          try {
            await channel.permissionOverwrites.create(
              guild.roles.everyone,
              {
                SendMessages: false,
                AddReactions: false,
                CreatePublicThreads: false,
                CreatePrivateThreads: false,
                SendMessagesInThreads: false,
                UseApplicationCommands: false,
              },
              { reason: 'Repent lockdown' }
            );

            channelPermissions.push({
              channelId: channel.id,
              previousPermissions,
            });
          } catch (error) {
            this.logger.error('Failed to lock channel', { error, channelId: channel.id, guildId: guild.id });
          }
        }
      }

      const state: LockdownState = {
        guildId: guild.id,
        channelPermissions,
        createdAt: Date.now(),
      };

      this.lockdownStates.set(guild.id, state);

      await this.logging.logInfo(guild, 'Lockdown Enabled', [
        { name: 'Channels Affected', value: channelPermissions.length.toString(), inline: true },
        { name: 'Time', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: true },
      ]);

      this.logger.info('Lockdown enabled', { guildId: guild.id, channels: channelPermissions.length });
      return true;
    } catch (error) {
      this.logger.error('Lockdown failed', { error, guildId: guild.id });
      return false;
    }
  }

  async unlock(guild: Guild): Promise<boolean> {
    const state = this.lockdownStates.get(guild.id);
    if (!state) {
      return false;
    }

    try {
      for (const channelPerm of state.channelPermissions) {
        const channel = guild.channels.cache.get(channelPerm.channelId);
        if (!channel || !('permissionOverwrites' in channel)) continue;

        try {
          await channel.permissionOverwrites.delete(guild.roles.everyone, 'Repent unlock');

          for (const perm of channelPerm.previousPermissions) {
            try {
              const allowPerms = perm.allow ? BigInt(perm.allow) : BigInt(0);
              const denyPerms = perm.deny ? BigInt(perm.deny) : BigInt(0);
              const ow = channel.permissionOverwrites.cache.get(perm.roleOrUserId);
              if (ow) {
                await ow.edit({ allow: allowPerms, deny: denyPerms } as any);
              }
            } catch (permError) {
              this.logger.debug('Failed to restore permission', { channelId: channel.id, roleId: perm.roleOrUserId });
            }
          }
        } catch (error) {
          this.logger.error('Failed to unlock channel', { error, channelId: channel.id, guildId: guild.id });
        }
      }

      this.lockdownStates.delete(guild.id);

      await this.logging.logInfo(guild, 'Lockdown Disabled', [
        { name: 'Channels Restored', value: state.channelPermissions.length.toString(), inline: true },
        { name: 'Time', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: true },
      ]);

      this.logger.info('Lockdown disabled', { guildId: guild.id });
      return true;
    } catch (error) {
      this.logger.error('Unlock failed', { error, guildId: guild.id });
      return false;
    }
  }

  isLocked(guildId: string): boolean {
    return this.lockdownStates.has(guildId);
  }

  getState(guildId: string): LockdownState | undefined {
    return this.lockdownStates.get(guildId);
  }
}
