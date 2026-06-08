import { SlashCommandBuilder, ChatInputCommandInteraction, PermissionFlagsBits, ChannelType, ComponentType, StringSelectMenuBuilder, StringSelectMenuOptionBuilder, ActionRowBuilder, EmbedBuilder } from 'discord.js';
import { GuildConfigRepo } from '../database/GuildConfigRepo';
import { ThresholdRepo } from '../database/ThresholdRepo';
import { RecoveryService } from '../services/RecoveryService';
import type { Command } from './index';

export const setupCommand: Command = {
  data: new SlashCommandBuilder()
    .setName('setup')
    .setDescription('Configure Repent anti-nuke protection for this server')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator) as SlashCommandBuilder,

  async execute(interaction: ChatInputCommandInteraction) {
    if (!interaction.guild) {
      await interaction.reply({ content: 'This command can only be used in a server.', ephemeral: true });
      return;
    }

    await interaction.deferReply({ ephemeral: true });

    const configRepo = new GuildConfigRepo();
    const thresholdRepo = new ThresholdRepo();
    const recovery = new RecoveryService();

    configRepo.getOrCreateDefault(interaction.guild.id);
    thresholdRepo.getOrCreateDefault(interaction.guild.id);

    const embed = new EmbedBuilder()
      .setColor(0x3498DB)
      .setTitle('Repent Setup')
      .setDescription('Welcome to Repent setup. This will take less than one minute.\n\n**Step 1: Select Log Channel**\nChoose a channel where protection logs will be sent.')
      .setTimestamp();

    const channelSelect = new StringSelectMenuBuilder()
      .setCustomId('setup_log_channel')
      .setPlaceholder('Select a log channel')
      .addOptions(
        interaction.guild.channels.cache
          .filter(ch => ch.type === ChannelType.GuildText)
          .first(25)
          .map(ch =>
            new StringSelectMenuOptionBuilder()
              .setLabel(ch.name)
              .setValue(ch.id)
          )
      );

    const row = new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(channelSelect);

    const message = await interaction.editReply({ embeds: [embed], components: [row] });

    try {
      const channelInteraction = await message.awaitMessageComponent({
        filter: i => i.user.id === interaction.user.id,
        time: 120000,
        componentType: ComponentType.StringSelect,
      });

      const logChannelId = channelInteraction.values[0];
      configRepo.update(interaction.guild.id, { logChannelId });

      await channelInteraction.deferUpdate();

      const punishmentEmbed = new EmbedBuilder()
        .setColor(0x3498DB)
        .setTitle('Repent Setup')
        .setDescription('**Step 2: Select Punishment**\nChoose the default punishment for violations.')
        .addFields(
          { name: 'Remove Roles', value: 'Removes all dangerous roles from the user' },
          { name: 'Timeout', value: 'Timeouts the user for 28 days' },
          { name: 'Kick', value: 'Kicks the user from the server' },
          { name: 'Ban', value: 'Bans the user from the server (default)' }
        )
        .setTimestamp();

      const punishmentSelect = new StringSelectMenuBuilder()
        .setCustomId('setup_punishment')
        .setPlaceholder('Select punishment (default: Ban)')
        .addOptions(
          new StringSelectMenuOptionBuilder().setLabel('Remove Roles').setValue('remove_roles'),
          new StringSelectMenuOptionBuilder().setLabel('Timeout').setValue('timeout'),
          new StringSelectMenuOptionBuilder().setLabel('Kick').setValue('kick'),
          new StringSelectMenuOptionBuilder().setLabel('Ban').setValue('ban')
        );

      const punishmentRow = new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(punishmentSelect);

      await channelInteraction.editReply({ embeds: [punishmentEmbed], components: [punishmentRow] });

      const punishmentInteraction = await message.awaitMessageComponent({
        filter: i => i.user.id === interaction.user.id,
        time: 120000,
        componentType: ComponentType.StringSelect,
      });

      const punishmentType = punishmentInteraction.values[0];
      configRepo.update(interaction.guild.id, {
        punishmentType: punishmentType as any,
        enabled: true,
      });

      await punishmentInteraction.deferUpdate();

      const confirmEmbed = new EmbedBuilder()
        .setColor(0x00FF00)
        .setTitle('Repent Setup Complete')
        .setDescription('Your server is now protected by Repent.')
        .addFields(
          { name: 'Log Channel', value: `<#${logChannelId}>`, inline: true },
          { name: 'Punishment', value: punishmentType, inline: true },
          { name: 'Status', value: 'Enabled', inline: true }
        )
        .setFooter({ text: 'Use /config to customize thresholds. Use /whitelist to manage exempt users.' })
        .setTimestamp();

      await punishmentInteraction.editReply({ embeds: [confirmEmbed], components: [] });

      await recovery.createSnapshot(interaction.guild, 'initial-setup');

    } catch (error) {
      const timeoutEmbed = new EmbedBuilder()
        .setColor(0xFF0000)
        .setTitle('Setup Timed Out')
        .setDescription('Setup has timed out. Please run /setup again.');

      await interaction.editReply({ embeds: [timeoutEmbed], components: [] });
    }
  },
};
