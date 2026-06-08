import { Interaction } from 'discord.js';
import { Logger } from '../utils/Logger';

export async function interactionCreateEvent(interaction: Interaction): Promise<void> {
  if (!interaction.isChatInputCommand()) return;

  const logger = Logger.getInstance();
  const command = interaction.client.commands.get(interaction.commandName);

  if (!command) {
    logger.warn(`Unknown command: ${interaction.commandName}`);
    return;
  }

  try {
    logger.debug('Executing command', {
      command: interaction.commandName,
      user: interaction.user.tag,
      guild: interaction.guild?.name,
    });

    await command.execute(interaction);
  } catch (error) {
    logger.error('Command execution error', {
      error,
      command: interaction.commandName,
      user: interaction.user.tag,
    });

    const reply = {
      content: 'An error occurred while executing this command.',
      ephemeral: true,
    };

    if (interaction.replied || interaction.deferred) {
      await interaction.followUp(reply);
    } else {
      await interaction.reply(reply);
    }
  }
}
