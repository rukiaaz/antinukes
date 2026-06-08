import { SlashCommandBuilder, ChatInputCommandInteraction, PermissionFlagsBits, EmbedBuilder } from 'discord.js';
import { GuildConfigRepo } from '../database/GuildConfigRepo';
import { ThresholdRepo } from '../database/ThresholdRepo';
import { WhitelistRepo } from '../database/WhitelistRepo';
import { LockdownService } from '../services/LockdownService';
import type { Command } from './index';

export const statusCommand: Command = {
  data: new SlashCommandBuilder()
    .setName('status')
    .setDescription('View Repent protection status for this server')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

  async execute(interaction: ChatInputCommandInteraction) {
    if (!interaction.guild) {
      await interaction.reply({ content: 'This command can only be used in a server.', ephemeral: true });
      return;
    }

    await interaction.deferReply({ ephemeral: true });

    const configRepo = new GuildConfigRepo();
    const thresholdRepo = new ThresholdRepo();
    const whitelistRepo = new WhitelistRepo();
    const lockdown = new LockdownService();

    const config = configRepo.get(interaction.guild.id);
    const thresholds = thresholdRepo.get(interaction.guild.id);
    const whitelist = whitelistRepo.getAllForGuild(interaction.guild.id);

    const embed = new EmbedBuilder()
      .setColor(config?.enabled ? 0x00FF00 : 0xFF0000)
      .setTitle('Repent Status')
      .addFields(
        {
          name: 'Protection',
          value: config?.enabled ? 'Enabled' : 'Disabled',
          inline: true
        },
        {
          name: 'Log Channel',
          value: config?.logChannelId ? `<#${config.logChannelId}>` : 'Not set',
          inline: true
        },
        {
          name: 'Punishment',
          value: config?.punishmentType || 'Ban',
          inline: true
        },
        {
          name: 'Lockdown',
          value: lockdown.isLocked(interaction.guild.id) ? 'Active' : 'Inactive',
          inline: true
        },
        {
          name: 'Whitelist Entries',
          value: whitelist.length.toString(),
          inline: true
        },
        {
          name: 'Channel Delete Threshold',
          value: thresholds ? `${thresholds.channelDeleteLimit} in ${thresholds.channelDeleteWindow}s` : 'Default',
          inline: true
        },
        {
          name: 'Role Delete Threshold',
          value: thresholds ? `${thresholds.roleDeleteLimit} in ${thresholds.roleDeleteWindow}s` : 'Default',
          inline: true
        },
        {
          name: 'Ban Threshold',
          value: thresholds ? `${thresholds.banLimit} in ${thresholds.banWindow}s` : 'Default',
          inline: true
        }
      )
      .setTimestamp();

    await interaction.editReply({ embeds: [embed] });
  },
};
