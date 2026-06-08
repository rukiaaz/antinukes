import { Client, REST, Routes, SlashCommandBuilder, SlashCommandSubcommandsOnlyBuilder } from 'discord.js';
import { Logger } from '../utils/Logger';
import { setupCommand } from './setup';
import { statusCommand } from './status';
import { configCommand } from './config';
import { whitelistCommand } from './whitelist';
import { lockdownCommand } from './lockdown';
import { panicCommand } from './panic';
import { backupCommand } from './backup';

export interface Command {
  data: SlashCommandBuilder | SlashCommandSubcommandsOnlyBuilder;
  execute: (interaction: any) => Promise<void>;
}

const commands: Command[] = [
  setupCommand,
  statusCommand,
  configCommand,
  whitelistCommand,
  lockdownCommand,
  panicCommand,
  backupCommand,
];

export async function registerCommands(client: Client): Promise<void> {
  const logger = Logger.getInstance();

  for (const command of commands) {
    client.commands.set(command.data.name, command);
  }

  try {
    const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN!);

    const commandData = commands.map(cmd => cmd.data.toJSON());

    await rest.put(
      Routes.applicationCommands(process.env.CLIENT_ID!),
      { body: commandData }
    );

    logger.info('Slash commands registered', { count: commands.length });
  } catch (error) {
    logger.error('Failed to register slash commands', { error });
  }
}
