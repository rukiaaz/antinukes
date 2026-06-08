import { GuildBasedChannel } from 'discord.js';
import { ChannelProtection } from '../modules/ChannelProtection';
import { Logger } from '../utils/Logger';

const protection = new ChannelProtection();
const logger = Logger.getInstance();

export const channelEvents = {
  async handleCreate(channel: GuildBasedChannel): Promise<void> {
    if (!channel.guild) return;

    try {
      await protection.handleChannelCreate(channel as any);
    } catch (error) {
      logger.error('Channel create protection error', { error, channelId: channel.id });
    }
  },

  async handleDelete(channel: GuildBasedChannel): Promise<void> {
    if (!channel.guild) return;

    try {
      await protection.handleChannelDelete(channel as any);
    } catch (error) {
      logger.error('Channel delete protection error', { error, channelId: channel.id });
    }
  },

  async handleUpdate(oldChannel: GuildBasedChannel, newChannel: GuildBasedChannel): Promise<void> {
    if (!newChannel.guild) return;

    try {
      await protection.handleChannelUpdate(oldChannel as any, newChannel as any);
    } catch (error) {
      logger.error('Channel update protection error', { error, channelId: newChannel.id });
    }
  },
};
