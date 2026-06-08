import { Client, ActivityType } from 'discord.js';
import { Logger } from '../utils/Logger';

export function readyEvent(client: Client): void {
  const logger = Logger.getInstance();

  logger.info('Repent is online', {
    username: client.user?.tag,
    guilds: client.guilds.cache.size,
  });

  client.user?.setActivity({
    name: '/setup to configure',
    type: ActivityType.Watching,
  });
}
