import 'dotenv/config';
import { Client, GatewayIntentBits, Partials, Collection } from 'discord.js';
import { Database } from './database/Database';
import { Logger } from './utils/Logger';
import { registerCommands } from './commands';
import { registerEvents } from './events';
import { ActionHistoryRepo } from './database/ActionHistoryRepo';

const logger = Logger.getInstance();

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildModeration,
    GatewayIntentBits.GuildEmojisAndStickers,
    GatewayIntentBits.GuildWebhooks,
    GatewayIntentBits.GuildMessages,
  ],
  partials: [Partials.GuildMember, Partials.User],
});

client.commands = new Collection();

async function initialize(): Promise<void> {
  try {
    const dbPath = process.env.DATABASE_PATH || './data/repent.db';
    Database.getInstance(dbPath);

    await registerCommands(client);
    await registerEvents(client);

    const actionHistory = new ActionHistoryRepo();
    setInterval(() => {
      const cleaned = actionHistory.cleanupOldActions(24 * 60 * 60 * 1000);
      if (cleaned > 0) {
        logger.debug(`Cleaned ${cleaned} old action records`);
      }
    }, 60 * 60 * 1000);

    await client.login(process.env.DISCORD_TOKEN);
  } catch (error) {
    logger.error('Failed to initialize bot', { error });
    process.exit(1);
  }
}

process.on('unhandledRejection', (error) => {
  logger.error('Unhandled promise rejection', { error });
});

process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception', { error });
  process.exit(1);
});

initialize();
