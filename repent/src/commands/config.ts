import { SlashCommandBuilder, ChatInputCommandInteraction, PermissionFlagsBits, EmbedBuilder } from 'discord.js';
import { GuildConfigRepo } from '../database/GuildConfigRepo';
import { ThresholdRepo } from '../database/ThresholdRepo';
import type { Command } from './index';

export const configCommand: Command = {
  data: new SlashCommandBuilder()
    .setName('config')
    .setDescription('Configure Repent thresholds and settings')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(sub =>
      sub
        .setName('view')
        .setDescription('View current configuration')
    )
    .addSubcommand(sub =>
      sub
        .setName('punishment')
        .setDescription('Set default punishment')
        .addStringOption(opt =>
          opt.setName('type')
            .setDescription('Punishment type')
            .setRequired(true)
            .addChoices(
              { name: 'Remove Roles', value: 'remove_roles' },
              { name: 'Timeout', value: 'timeout' },
              { name: 'Kick', value: 'kick' },
              { name: 'Ban', value: 'ban' }
            )
        )
    )
    .addSubcommand(sub =>
      sub
        .setName('threshold')
        .setDescription('Set a threshold')
        .addStringOption(opt =>
          opt.setName('action')
            .setDescription('Action type')
            .setRequired(true)
            .addChoices(
              { name: 'Channel Delete', value: 'channel_delete' },
              { name: 'Channel Create', value: 'channel_create' },
              { name: 'Channel Update', value: 'channel_update' },
              { name: 'Role Delete', value: 'role_delete' },
              { name: 'Role Create', value: 'role_create' },
              { name: 'Role Update', value: 'role_update' },
              { name: 'Webhook Create', value: 'webhook_create' },
              { name: 'Ban', value: 'ban' },
              { name: 'Kick', value: 'kick' },
              { name: 'Timeout', value: 'timeout' },
              { name: 'Bot Add', value: 'bot_add' }
            )
        )
        .addIntegerOption(opt =>
          opt.setName('limit')
            .setDescription('Number of actions allowed')
            .setRequired(true)
            .setMinValue(1)
            .setMaxValue(100)
        )
        .addIntegerOption(opt =>
          opt.setName('window')
            .setDescription('Time window in seconds')
            .setRequired(true)
            .setMinValue(1)
            .setMaxValue(300)
        )
    )
    .addSubcommand(sub =>
      sub
        .setName('toggle')
        .setDescription('Enable or disable protection')
        .addBooleanOption(opt =>
          opt.setName('enabled')
            .setDescription('Enable protection')
            .setRequired(true)
        )
    ),

  async execute(interaction: ChatInputCommandInteraction) {
    if (!interaction.guild) {
      await interaction.reply({ content: 'This command can only be used in a server.', ephemeral: true });
      return;
    }

    await interaction.deferReply({ ephemeral: true });

    const configRepo = new GuildConfigRepo();
    const thresholdRepo = new ThresholdRepo();
    const subcommand = interaction.options.getSubcommand();

    switch (subcommand) {
      case 'view': {
        const config = configRepo.getOrCreateDefault(interaction.guild.id);
        const thresholds = thresholdRepo.getOrCreateDefault(interaction.guild.id);

        const embed = new EmbedBuilder()
          .setColor(0x3498DB)
          .setTitle('Repent Configuration')
          .addFields(
            { name: 'Enabled', value: config.enabled ? 'Yes' : 'No', inline: true },
            { name: 'Punishment', value: config.punishmentType, inline: true },
            { name: 'Log Channel', value: config.logChannelId ? `<#${config.logChannelId}>` : 'Not set', inline: true },
            { name: 'Channel Delete', value: `${thresholds.channelDeleteLimit} in ${thresholds.channelDeleteWindow}s`, inline: true },
            { name: 'Channel Create', value: `${thresholds.channelCreateLimit} in ${thresholds.channelCreateWindow}s`, inline: true },
            { name: 'Channel Update', value: `${thresholds.channelUpdateLimit} in ${thresholds.channelUpdateWindow}s`, inline: true },
            { name: 'Role Delete', value: `${thresholds.roleDeleteLimit} in ${thresholds.roleDeleteWindow}s`, inline: true },
            { name: 'Role Create', value: `${thresholds.roleCreateLimit} in ${thresholds.roleCreateWindow}s`, inline: true },
            { name: 'Role Update', value: `${thresholds.roleUpdateLimit} in ${thresholds.roleUpdateWindow}s`, inline: true },
            { name: 'Ban', value: `${thresholds.banLimit} in ${thresholds.banWindow}s`, inline: true },
            { name: 'Kick', value: `${thresholds.kickLimit} in ${thresholds.kickWindow}s`, inline: true },
            { name: 'Timeout', value: `${thresholds.timeoutLimit} in ${thresholds.timeoutWindow}s`, inline: true },
            { name: 'Webhook Create', value: `${thresholds.webhookCreateLimit} in ${thresholds.webhookCreateWindow}s`, inline: true },
            { name: 'Bot Add', value: `${thresholds.botAddLimit} in ${thresholds.botAddWindow}s`, inline: true }
          )
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }

      case 'punishment': {
        const type = interaction.options.getString('type', true) as any;
        configRepo.update(interaction.guild.id, { punishmentType: type });

        const embed = new EmbedBuilder()
          .setColor(0x00FF00)
          .setTitle('Configuration Updated')
          .setDescription(`Punishment type set to: **${type}**`)
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }

      case 'threshold': {
        const action = interaction.options.getString('action', true);
        const limit = interaction.options.getInteger('limit', true);
        const window = interaction.options.getInteger('window', true);

        const fieldMap: Record<string, string> = {
          channel_delete: 'channelDelete',
          channel_create: 'channelCreate',
          channel_update: 'channelUpdate',
          role_delete: 'roleDelete',
          role_create: 'roleCreate',
          role_update: 'roleUpdate',
          webhook_create: 'webhookCreate',
          ban: 'ban',
          kick: 'kick',
          timeout: 'timeout',
          bot_add: 'botAdd',
        };

        const prefix = fieldMap[action];
        if (!prefix) {
          await interaction.editReply({ content: 'Invalid action type.' });
          return;
        }

        const updates: any = {};
        updates[`${prefix}Limit`] = limit;
        updates[`${prefix}Window`] = window;

        thresholdRepo.update(interaction.guild.id, updates);

        const embed = new EmbedBuilder()
          .setColor(0x00FF00)
          .setTitle('Threshold Updated')
          .setDescription(`**${action}** threshold set to: **${limit}** in **${window}s**`)
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }

      case 'toggle': {
        const enabled = interaction.options.getBoolean('enabled', true);
        configRepo.update(interaction.guild.id, { enabled });

        const embed = new EmbedBuilder()
          .setColor(enabled ? 0x00FF00 : 0xFF0000)
          .setTitle('Protection Status')
          .setDescription(`Protection is now **${enabled ? 'ENABLED' : 'DISABLED'}**`)
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }
    }
  },
};
