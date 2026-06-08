import { Guild } from 'discord.js';
import { GuildProtection } from '../modules/GuildProtection';
import { Logger } from '../utils/Logger';

const protection = new GuildProtection();
const logger = Logger.getInstance();

export const guildEvents = {
  async handleGuildUpdate(oldGuild: Guild, newGuild: Guild): Promise<void> {
    try {
      await protection.handleGuildUpdate(oldGuild, newGuild);
    } catch (error) {
      logger.error('Guild update protection error', { error, guildId: newGuild.id });
    }
  },
};
