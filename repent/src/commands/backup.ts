import { SlashCommandBuilder, ChatInputCommandInteraction, PermissionFlagsBits, EmbedBuilder } from 'discord.js';
import { RecoveryService } from '../services/RecoveryService';
import { SnapshotRepo } from '../database/SnapshotRepo';
import type { Command } from './index';

export const backupCommand: Command = {
  data: new SlashCommandBuilder()
    .setName('backup')
    .setDescription('Create or restore server backups')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(sub =>
      sub
        .setName('create')
        .setDescription('Create a manual backup')
        .addStringOption(opt =>
          opt.setName('name')
            .setDescription('Backup name')
            .setRequired(false)
        )
    )
    .addSubcommand(sub =>
      sub
        .setName('restore')
        .setDescription('Restore from the latest backup')
    )
    .addSubcommand(sub =>
      sub
        .setName('list')
        .setDescription('List recent backups')
    ),

  async execute(interaction: ChatInputCommandInteraction) {
    if (!interaction.guild) {
      await interaction.reply({ content: 'This command can only be used in a server.', ephemeral: true });
      return;
    }

    await interaction.deferReply({ ephemeral: true });

    const recovery = new RecoveryService();
    const snapshotRepo = new SnapshotRepo();
    const subcommand = interaction.options.getSubcommand();

    switch (subcommand) {
      case 'create': {
        const name = interaction.options.getString('name') || `manual-${Date.now()}`;
        const success = await recovery.createSnapshot(interaction.guild, name);

        const embed = new EmbedBuilder()
          .setColor(success ? 0x00FF00 : 0xFF0000)
          .setTitle(success ? 'Backup Created' : 'Backup Failed')
          .setDescription(success
            ? `Backup **${name}** has been created successfully.`
            : 'Failed to create backup. Check bot permissions.'
          )
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }

      case 'restore': {
        const snapshots = snapshotRepo.getAllForGuild(interaction.guild.id);
        if (snapshots.length === 0) {
          const embed = new EmbedBuilder()
            .setColor(0xFF0000)
            .setTitle('No Backups')
            .setDescription('No backups found for this server.')
            .setTimestamp();

          await interaction.editReply({ embeds: [embed] });
          return;
        }

        const confirmEmbed = new EmbedBuilder()
          .setColor(0xFFA500)
          .setTitle('Restore Backup')
          .setDescription(`Are you sure you want to restore from backup **${snapshots[0].name}**?\nThis will recreate channels, roles, and other server elements.\n\nType \`/backup restore\` again to confirm.`)
          .setTimestamp();

        await interaction.editReply({ embeds: [confirmEmbed] });
        break;
      }

      case 'list': {
        const snapshots = snapshotRepo.getAllForGuild(interaction.guild.id);

        const embed = new EmbedBuilder()
          .setColor(0x3498DB)
          .setTitle('Recent Backups')
          .setDescription(snapshots.length > 0
            ? snapshots.slice(0, 10).map((s, i) =>
              `${i + 1}. **${s.name}** - <t:${Math.floor(s.createdAt / 1000)}:R>`
            ).join('\n')
            : 'No backups found.'
          )
          .setTimestamp();

        await interaction.editReply({ embeds: [embed] });
        break;
      }
    }
  },
};
