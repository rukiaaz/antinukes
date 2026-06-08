import { SlashCommandBuilder, ChatInputCommandInteraction, PermissionFlagsBits, EmbedBuilder } from 'discord.js';
import { LockdownService } from '../services/LockdownService';
import type { Command } from './index';

export const lockdownCommand: Command = {
  data: new SlashCommandBuilder()
    .setName('lockdown')
    .setDescription('Lock or unlock the server')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(sub =>
      sub
        .setName('enable')
        .setDescription('Enable lockdown - disables messaging in all channels')
    )
    .addSubcommand(sub =>
      sub
        .setName('disable')
        .setDescription('Disable lockdown - restores previous permissions')
    ),

  async execute(interaction: ChatInputCommandInteraction) {
    if (!interaction.guild) {
      await interaction.reply({ content: 'This command can only be used in a server.', ephemeral: true });
      return;
    }

    await interaction.deferReply();

    const lockdown = new LockdownService();
    const subcommand = interaction.options.getSubcommand();

    if (subcommand === 'enable') {
      if (lockdown.isLocked(interaction.guild.id)) {
        const embed = new EmbedBuilder()
          .setColor(0xFFA500)
          .setTitle('Lockdown Already Active')
          .setDescription('The server is already in lockdown.')
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        return;
      }

      const success = await lockdown.lockdown(interaction.guild);

      const embed = new EmbedBuilder()
        .setColor(success ? 0xFF0000 : 0xFFA500)
        .setTitle(success ? 'Lockdown Enabled' : 'Lockdown Failed')
        .setDescription(success
          ? 'All channels have been locked. Members cannot send messages or create threads.'
          : 'Failed to enable lockdown. Check bot permissions.'
        )
        .setTimestamp();

      await interaction.editReply({ embeds: [embed] });
    } else {
      if (!lockdown.isLocked(interaction.guild.id)) {
        const embed = new EmbedBuilder()
          .setColor(0xFFA500)
          .setTitle('Not in Lockdown')
          .setDescription('The server is not currently in lockdown.')
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        return;
      }

      const success = await lockdown.unlock(interaction.guild);

      const embed = new EmbedBuilder()
        .setColor(success ? 0x00FF00 : 0xFFA500)
        .setTitle(success ? 'Lockdown Disabled' : 'Unlock Failed')
        .setDescription(success
          ? 'All channels have been restored to their previous state.'
          : 'Failed to disable lockdown. Some channels may need manual restoration.'
        )
        .setTimestamp();

      await interaction.editReply({ embeds: [embed] });
    }
  },
};
