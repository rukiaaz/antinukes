import { SlashCommandBuilder, ChatInputCommandInteraction, PermissionFlagsBits, EmbedBuilder } from 'discord.js';
import { WhitelistRepo } from '../database/WhitelistRepo';
import type { Command } from './index';

export const whitelistCommand: Command = {
  data: new SlashCommandBuilder()
    .setName('whitelist')
    .setDescription('Manage whitelist entries')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(sub =>
      sub
        .setName('add')
        .setDescription('Add a user to the whitelist')
        .addUserOption(opt =>
          opt.setName('user')
            .setDescription('User to whitelist')
            .setRequired(true)
        )
    )
    .addSubcommand(sub =>
      sub
        .setName('remove')
        .setDescription('Remove a user from the whitelist')
        .addUserOption(opt =>
          opt.setName('user')
            .setDescription('User to remove')
            .setRequired(true)
        )
    )
    .addSubcommand(sub =>
      sub
        .setName('role_add')
        .setDescription('Add a role to the whitelist')
        .addRoleOption(opt =>
          opt.setName('role')
            .setDescription('Role to whitelist')
            .setRequired(true)
        )
    )
    .addSubcommand(sub =>
      sub
        .setName('role_remove')
        .setDescription('Remove a role from the whitelist')
        .addRoleOption(opt =>
          opt.setName('role')
            .setDescription('Role to remove')
            .setRequired(true)
        )
    )
    .addSubcommand(sub =>
      sub
        .setName('list')
        .setDescription('List all whitelist entries')
    ),

  async execute(interaction: ChatInputCommandInteraction) {
    if (!interaction.guild) {
      await interaction.reply({ content: 'This command can only be used in a server.', ephemeral: true });
      return;
    }

    await interaction.deferReply({ ephemeral: true });

    const whitelistRepo = new WhitelistRepo();
    const subcommand = interaction.options.getSubcommand();

    switch (subcommand) {
      case 'add': {
        const user = interaction.options.getUser('user', true);

        if (user.id === interaction.guild.ownerId) {
          await interaction.editReply({ content: 'The server owner is automatically whitelisted.' });
          return;
        }

        const success = whitelistRepo.add({
          guildId: interaction.guild.id,
          targetId: user.id,
          targetType: 'user',
          addedBy: interaction.user.id,
        });

        const embed = new EmbedBuilder()
          .setColor(success ? 0x00FF00 : 0xFF0000)
          .setTitle(success ? 'User Whitelisted' : 'Error')
          .setDescription(success ? `<@${user.id}> has been added to the whitelist.` : 'Failed to add user to whitelist.')
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }

      case 'remove': {
        const user = interaction.options.getUser('user', true);

        if (user.id === interaction.guild.ownerId) {
          await interaction.editReply({ content: 'The server owner cannot be removed from the whitelist.' });
          return;
        }

        const success = whitelistRepo.remove(interaction.guild.id, user.id);

        const embed = new EmbedBuilder()
          .setColor(success ? 0x00FF00 : 0xFF0000)
          .setTitle(success ? 'User Removed' : 'Not Found')
          .setDescription(success ? `<@${user.id}> has been removed from the whitelist.` : 'User was not in the whitelist.')
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }

      case 'role_add': {
        const role = interaction.options.getRole('role', true);

        const success = whitelistRepo.add({
          guildId: interaction.guild.id,
          targetId: role.id,
          targetType: 'role',
          addedBy: interaction.user.id,
        });

        const embed = new EmbedBuilder()
          .setColor(success ? 0x00FF00 : 0xFF0000)
          .setTitle(success ? 'Role Whitelisted' : 'Error')
          .setDescription(success ? `<@&${role.id}> has been added to the whitelist.` : 'Failed to add role to whitelist.')
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }

      case 'role_remove': {
        const role = interaction.options.getRole('role', true);

        const success = whitelistRepo.remove(interaction.guild.id, role.id);

        const embed = new EmbedBuilder()
          .setColor(success ? 0x00FF00 : 0xFF0000)
          .setTitle(success ? 'Role Removed' : 'Not Found')
          .setDescription(success ? `<@&${role.id}> has been removed from the whitelist.` : 'Role was not in the whitelist.')
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }

      case 'list': {
        const entries = whitelistRepo.getAllForGuild(interaction.guild.id);

        const userEntries = entries.filter(e => e.targetType === 'user');
        const roleEntries = entries.filter(e => e.targetType === 'role');

        const embed = new EmbedBuilder()
          .setColor(0x3498DB)
          .setTitle('Whitelist Entries')
          .addFields(
            {
              name: `Users (${userEntries.length})`,
              value: userEntries.length > 0
                ? userEntries.map(e => `<@${e.targetId}>`).join('\n')
                : 'None',
              inline: true
            },
            {
              name: `Roles (${roleEntries.length})`,
              value: roleEntries.length > 0
                ? roleEntries.map(e => `<@&${e.targetId}>`).join('\n')
                : 'None',
              inline: true
            }
          )
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }
    }
  },
};
