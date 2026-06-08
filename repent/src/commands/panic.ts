import { SlashCommandBuilder, ChatInputCommandInteraction, PermissionFlagsBits, EmbedBuilder } from 'discord.js';
import { LockdownService } from '../services/LockdownService';
import { PanicModeService } from '../services/PanicModeService';
import type { Command } from './index';

export const panicCommand: Command = {
  data: new SlashCommandBuilder()
    .setName('panic')
    .setDescription('Emergency panic mode - strips all dangerous permissions and locks server')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(sub =>
      sub
        .setName('on')
        .setDescription('Enable panic mode')
    )
    .addSubcommand(sub =>
      sub
        .setName('off')
        .setDescription('Disable panic mode and restore previous state')
    ),

  async execute(interaction: ChatInputCommandInteraction) {
    if (!interaction.guild) {
      await interaction.reply({ content: 'This command can only be used in a server.', ephemeral: true });
      return;
    }

    await interaction.deferReply();

    const lockdown = new LockdownService();
    const panic = new PanicModeService(lockdown);
    const subcommand = interaction.options.getSubcommand();

    if (subcommand === 'on') {
      if (panic.isActive(interaction.guild.id)) {
        const embed = new EmbedBuilder()
          .setColor(0xFFA500)
          .setTitle('Panic Mode Already Active')
          .setDescription('Panic mode is already enabled.')
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        return;
      }

      const success = await panic.enable(interaction.guild);

      const embed = new EmbedBuilder()
        .setColor(success ? 0xFF0000 : 0xFFA500)
        .setTitle(success ? 'PANIC MODE ENABLED' : 'Panic Mode Failed')
        .setDescription(success
          ? 'All dangerous permissions have been stripped. Server is in lockdown. The server owner has been notified.'
          : 'Failed to enable panic mode. Check bot permissions.'
        )
        .setTimestamp();

      await interaction.editReply({ embeds: [embed] });
    } else {
      if (!panic.isActive(interaction.guild.id)) {
        const embed = new EmbedBuilder()
          .setColor(0xFFA500)
          .setTitle('Panic Mode Not Active')
          .setDescription('Panic mode is not currently enabled.')
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        return;
      }

      const success = await panic.disable(interaction.guild);

      const embed = new EmbedBuilder()
        .setColor(success ? 0x00FF00 : 0xFFA500)
        .setTitle(success ? 'Panic Mode Disabled' : 'Disable Failed')
        .setDescription(success
          ? 'All permissions and channel states have been restored.'
          : 'Failed to fully disable panic mode. Some roles may need manual restoration.'
        )
        .setTimestamp();

      await interaction.editReply({ embeds: [embed] });
    }
  },
};
