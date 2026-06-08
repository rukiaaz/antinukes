import {
  EmbedBuilder,
  PermissionFlagsBits,
  ChannelType,
  ActionRowBuilder,
  StringSelectMenuBuilder,
  StringSelectMenuOptionBuilder,
  ComponentType,
  type ChatInputCommandInteraction,
  type GuildBasedChannel,
} from 'discord.js';
import type { Repent } from '../structures/Repent';
import { getGuildConfig, updateGuildConfig, setProtectionConfig } from '../models/GuildSettings';
import { setPanicMode, addWhitelistUser, removeWhitelistUser, addWhitelistRole, removeWhitelistRole } from '../models/GuildSettings';
import { CONFIG } from '../utils/config';
import type { ActionType } from '../types';

class CommandHandlerClass {
  public async handle(interaction: ChatInputCommandInteraction, client: Repent): Promise<void> {
    const { commandName } = interaction;

    switch (commandName) {
      case 'setup':
        await this.handleSetup(interaction);
        break;
      case 'whitelist-add':
        await this.handleWhitelistAdd(interaction);
        break;
      case 'whitelist-remove':
        await this.handleWhitelistRemove(interaction);
        break;
      case 'config':
        await this.handleConfig(interaction);
        break;
      case 'status':
        await this.handleStatus(interaction, client);
        break;
      case 'lockdown':
        await this.handleLockdown(interaction, client);
        break;
      case 'unlockdown':
        await this.handleUnlockdown(interaction, client);
        break;
      case 'panic':
        await this.handlePanic(interaction, client);
        break;
    }
  }

  private async handleSetup(interaction: ChatInputCommandInteraction): Promise<void> {
    if (!interaction.guild) return;

    const config = await getGuildConfig(interaction.guild.id);
    if (!config) return;

    // Tight security: only stored owner can run setup.
    if (interaction.user.id !== config.ownerId) {
      await interaction.reply({ content: 'Only the server owner can run setup.', ephemeral: true });
      return;
    }

    const logChannel = interaction.options.getChannel('log_channel', true);
    const punishment = interaction.options.getString('punishment', true) as 'ban' | 'kick' | 'timeout' | 'removeRoles';

    await updateGuildConfig(interaction.guild.id, { logChannelId: logChannel.id });

    // Apply chosen punishment across all enabled modules defaults.
    const cfgAfter = await getGuildConfig(interaction.guild.id);
    if (cfgAfter) {
      for (const key of Object.keys(cfgAfter.protections)) {
        await setProtectionConfig(interaction.guild.id, key as ActionType, { punishment });
      }
    }

    await updateGuildConfig(interaction.guild.id, { setup: true });

    const doneEmbed = new EmbedBuilder()
      .setColor(CONFIG.SUCCESS_COLOR)
      .setTitle('Setup Complete')
      .setDescription('Repent is now protecting this server.')
      .addFields(
        { name: 'Log Channel', value: `<#${logChannel.id}>`, inline: false },
        { name: 'Punishment', value: punishment, inline: false }
      );

    await interaction.reply({ embeds: [doneEmbed], ephemeral: true });
  }

  private async handleWhitelistAdd(interaction: ChatInputCommandInteraction): Promise<void> {
    if (!interaction.guild) return;

    const guild = interaction.guild;
    const config = await getGuildConfig(guild.id);

    if (interaction.user.id !== config?.ownerId) {
      await interaction.reply({ content: 'Only the server owner can manage the whitelist.', ephemeral: true });
      return;
    }

    const user = interaction.options.getUser('user');
    const role = interaction.options.getRole('role');

    if (!user && !role) {
      await interaction.reply({ content: 'Provide a user or role.', ephemeral: true });
      return;
    }

    if (user) {
      const success = await addWhitelistUser(guild.id, user.id);
      await interaction.reply({
        content: success ? `Added ${user.tag} to whitelist.` : 'User is already whitelisted.',
        ephemeral: true,
      });
    }

    if (role) {
      const success = await addWhitelistRole(guild.id, role.id);
      await interaction.reply({
        content: success ? `Added ${role.name} to whitelist.` : 'Role is already whitelisted.',
        ephemeral: true,
      });
    }
  }

  private async handleWhitelistRemove(interaction: ChatInputCommandInteraction): Promise<void> {
    if (!interaction.guild) return;

    const guild = interaction.guild;
    const config = await getGuildConfig(guild.id);

    if (interaction.user.id !== config?.ownerId) {
      await interaction.reply({ content: 'Only the server owner can manage the whitelist.', ephemeral: true });
      return;
    }

    const user = interaction.options.getUser('user');
    const role = interaction.options.getRole('role');

    if (!user && !role) {
      await interaction.reply({ content: 'Provide a user or role.', ephemeral: true });
      return;
    }

    if (user) {
      const success = await removeWhitelistUser(guild.id, user.id);
      await interaction.reply({
        content: success ? `Removed ${user.tag} from whitelist.` : 'User was not whitelisted.',
        ephemeral: true,
      });
    }

    if (role) {
      const success = await removeWhitelistRole(guild.id, role.id);
      await interaction.reply({
        content: success ? `Removed ${role.name} from whitelist.` : 'Role was not whitelisted.',
        ephemeral: true,
      });
    }
  }

  private async handleConfig(interaction: ChatInputCommandInteraction): Promise<void> {
    if (!interaction.guild) return;

    const module = interaction.options.getString('module') as ActionType | null;
    const config = await getGuildConfig(interaction.guild.id);

    if (!config) {
      await interaction.reply({ content: 'Run /setup first.', ephemeral: true });
      return;
    }

    // Tight security: only stored owner can modify configuration.
    if (interaction.user.id !== config.ownerId) {
      await interaction.reply({ content: 'Only the server owner can manage this configuration.', ephemeral: true });
      return;
    }

    if (!module) {
      // Show all modules status
      const protections = Object.entries(config.protections);
      const enabled = protections.filter(([, p]) => p.enabled).length;
      const total = protections.length;

      const embed = new EmbedBuilder()
        .setColor(CONFIG.EMBED_COLOR)
        .setTitle('Protection Configuration')
        .setDescription(`${enabled}/${total} modules enabled.`)
        .addFields(
          protections.slice(0, 24).map(([key, p]) => ({
            name: key.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase()),
            value: `${p.enabled ? 'On' : 'Off'} | ${p.threshold}/${p.windowSeconds}s | ${p.punishment}`,
            inline: true,
          }))
        );

      await interaction.reply({ embeds: [embed], ephemeral: true });
      return;
    }

    // Show specific module config with toggle
    const prot = config.protections[module];
    if (!prot) {
      await interaction.reply({ content: 'Invalid module.', ephemeral: true });
      return;
    }

    const embed = new EmbedBuilder()
      .setColor(CONFIG.EMBED_COLOR)
      .setTitle(module.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase()))
      .addFields(
        { name: 'Enabled', value: prot.enabled ? 'Yes' : 'No', inline: true },
        { name: 'Threshold', value: prot.threshold.toString(), inline: true },
        { name: 'Window', value: `${prot.windowSeconds}s`, inline: true },
        { name: 'Punishment', value: prot.punishment, inline: true }
      );

    const row = new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(
      new StringSelectMenuBuilder()
        .setCustomId(`config_${module}`)
        .setPlaceholder('Modify')
        .addOptions(
          new StringSelectMenuOptionBuilder().setLabel('Toggle Enabled').setValue('toggle'),
          new StringSelectMenuOptionBuilder().setLabel('Set Punishment: Ban').setValue('punish_ban'),
          new StringSelectMenuOptionBuilder().setLabel('Set Punishment: Kick').setValue('punish_kick'),
          new StringSelectMenuOptionBuilder().setLabel('Set Punishment: Timeout').setValue('punish_timeout'),
          new StringSelectMenuOptionBuilder().setLabel('Set Punishment: Remove Roles').setValue('punish_removeRoles'),
        )
    );

    const msg = await interaction.reply({ embeds: [embed], components: [row], ephemeral: true, fetchReply: true });

    const collector = msg.createMessageComponentCollector({
      componentType: ComponentType.StringSelect,
      time: 60000,
    });

    collector.on('collect', async i => {
      if (i.user.id !== interaction.user.id) {
        await i.reply({ content: 'Not your config.', ephemeral: true });
        return;
      }

      const value = i.values[0];

      if (value === 'toggle') {
        await setProtectionConfig(interaction.guild!.id, module, { enabled: !prot.enabled });
        await i.reply({ content: `${module} is now ${!prot.enabled ? 'enabled' : 'disabled'}.`, ephemeral: true });
      } else if (value.startsWith('punish_')) {
        const punishment = value.replace('punish_', '') as 'ban' | 'kick' | 'timeout' | 'removeRoles';
        await setProtectionConfig(interaction.guild!.id, module, { punishment });
        await i.reply({ content: `Punishment set to ${punishment}.`, ephemeral: true });
      }

      collector.stop();
    });
  }

  private async handleStatus(interaction: ChatInputCommandInteraction, client: Repent): Promise<void> {
    if (!interaction.guild) return;

    const config = await getGuildConfig(interaction.guild.id);
    if (!config) {
      await interaction.reply({ content: 'Run /setup first.', ephemeral: true });
      return;
    }

    const guild = interaction.guild;
    const protections = Object.entries(config.protections);
    const enabled = protections.filter(([, p]) => p.enabled).length;

    const embed = new EmbedBuilder()
      .setColor(CONFIG.EMBED_COLOR)
      .setTitle('Protection Status')
      .addFields(
        { name: 'Setup', value: config.setup ? 'Complete' : 'Incomplete', inline: true },
        { name: 'Panic Mode', value: config.panicMode ? 'Active' : 'Inactive', inline: true },
        { name: 'Modules', value: `${enabled}/${protections.length} enabled`, inline: true },
        { name: 'Log Channel', value: config.logChannelId ? `<#${config.logChannelId}>` : 'Not set', inline: true },
        { name: 'Whitelisted Users', value: config.whitelistUsers.length.toString(), inline: true },
        { name: 'Whitelisted Roles', value: config.whitelistRoles.length.toString(), inline: true }
      )
      .setTimestamp();

    await interaction.reply({ embeds: [embed], ephemeral: true });
  }

  private isNonThreadChannel(channel: GuildBasedChannel): boolean {
    const type = channel.type;
    return (
      type === ChannelType.GuildText ||
      type === ChannelType.GuildVoice ||
      type === ChannelType.GuildAnnouncement ||
      type === ChannelType.GuildStageVoice
    );
  }

  private async lockChannelForLockdown(channel: GuildBasedChannel, guildId: string): Promise<boolean> {
    try {
      if (channel.isTextBased() && this.isNonThreadChannel(channel)) {
        const ch = channel as unknown as { permissionOverwrites: { edit: (id: string, o: Record<string, boolean | null>) => Promise<unknown> } };
        await ch.permissionOverwrites.edit(guildId, {
          SendMessages: false,
          AddReactions: false,
        });
        return true;
      }
      if ('isVoiceBased' in channel && typeof channel.isVoiceBased === 'function' && channel.isVoiceBased()) {
        const ch = channel as unknown as { permissionOverwrites: { edit: (id: string, o: Record<string, boolean | null>) => Promise<unknown> } };
        await ch.permissionOverwrites.edit(guildId, {
          Connect: false,
        });
        return true;
      }
    } catch {
      // Skip
    }
    return false;
  }

  private async unlockChannelForLockdown(channel: GuildBasedChannel, guildId: string): Promise<boolean> {
    try {
      if (channel.isTextBased() && this.isNonThreadChannel(channel)) {
        const ch = channel as unknown as { permissionOverwrites: { edit: (id: string, o: Record<string, boolean | null>) => Promise<unknown> } };
        await ch.permissionOverwrites.edit(guildId, {
          SendMessages: null,
          AddReactions: null,
        });
        return true;
      }
      if ('isVoiceBased' in channel && typeof channel.isVoiceBased === 'function' && channel.isVoiceBased()) {
        const ch = channel as unknown as { permissionOverwrites: { edit: (id: string, o: Record<string, boolean | null>) => Promise<unknown> } };
        await ch.permissionOverwrites.edit(guildId, {
          Connect: null,
        });
        return true;
      }
    } catch {
      // Skip
    }
    return false;
  }

  private async handleLockdown(interaction: ChatInputCommandInteraction, client: Repent): Promise<void> {
    if (!interaction.guild) return;

    await interaction.deferReply({ ephemeral: true });

    const guild = interaction.guild;
    const config = await getGuildConfig(guild.id);

    if (!config) {
      await interaction.editReply({ content: 'Run /setup first.' });
      return;
    }

    // Tight security: only stored owner can activate lockdown.
    if (interaction.user.id !== config.ownerId) {
      await interaction.editReply({ content: 'Only the server owner can run lockdown.' });
      return;
    }

    const locked: string[] = [];

    for (const channel of guild.channels.cache.values()) {
      if (!('permissionOverwrites' in channel)) continue;
      const success = await this.lockChannelForLockdown(channel, guild.id);
      if (success) locked.push(channel.id);
    }

    await updateGuildConfig(guild.id, { lockdownChannels: locked });
    await client.logHandler.logEmergency(guild, { type: 'lockdown', triggeredBy: interaction.user });

    const embed = new EmbedBuilder()
      .setColor(CONFIG.PANIC_COLOR)
      .setTitle('Lockdown')
      .setDescription(`Locked ${locked.length} channels.`);

    await interaction.editReply({ embeds: [embed] });
  }

  private async handleUnlockdown(interaction: ChatInputCommandInteraction, client: Repent): Promise<void> {
    if (!interaction.guild) return;

    await interaction.deferReply({ ephemeral: true });

    const guild = interaction.guild;
    const config = await getGuildConfig(guild.id);

    if (!config) {
      await interaction.editReply({ content: 'Run /setup first.' });
      return;
    }

    // Tight security: only stored owner can deactivate lockdown.
    if (interaction.user.id !== config.ownerId) {
      await interaction.editReply({ content: 'Only the server owner can run unlockdown.' });
      return;
    }

    const locked = config.lockdownChannels ?? [];

    let unlocked = 0;
    for (const channelId of locked) {
      const channel = guild.channels.cache.get(channelId);
      if (!channel || !('permissionOverwrites' in channel)) continue;
      const success = await this.unlockChannelForLockdown(channel, guild.id);
      if (success) unlocked++;
    }

    await updateGuildConfig(guild.id, { lockdownChannels: [] });
    await client.logHandler.logEmergency(guild, { type: 'unlockdown', triggeredBy: interaction.user });

    const embed = new EmbedBuilder()
      .setColor(CONFIG.SUCCESS_COLOR)
      .setTitle('Unlockdown')
      .setDescription(`Unlocked ${unlocked} channels.`);

    await interaction.editReply({ embeds: [embed] });
  }

  private async handlePanic(interaction: ChatInputCommandInteraction, client: Repent): Promise<void> {
    if (!interaction.guild) return;

    const guild = interaction.guild;
    const config = await getGuildConfig(guild.id);

    if (!config) {
      await interaction.reply({ content: 'Run /setup first.', ephemeral: true });
      return;
    }

    // Tight security: only stored owner can toggle panic mode.
    if (interaction.user.id !== config.ownerId) {
      await interaction.reply({ content: 'Only the server owner can toggle panic mode.', ephemeral: true });
      return;
    }

    const newPanic = !config.panicMode;

    await setPanicMode(guild.id, newPanic);

    if (newPanic) {
      // Lock all channels
      const locked: string[] = [];
      for (const channel of guild.channels.cache.values()) {
        if (!('permissionOverwrites' in channel)) continue;
        const success = await this.lockChannelForLockdown(channel, guild.id);
        if (success) locked.push(channel.id);
      }
      await updateGuildConfig(guild.id, { lockdownChannels: locked });

      // Delete webhooks
      try {
        const webhooks = await guild.fetchWebhooks();
        for (const webhook of webhooks.values()) {
          await webhook.delete('Repent panic mode').catch(() => null);
        }
      } catch {
        // Skip
      }
    } else {
      // Restore lockdown channels
      const locked = config?.lockdownChannels ?? [];
      for (const channelId of locked) {
        const channel = guild.channels.cache.get(channelId);
        if (!channel || !('permissionOverwrites' in channel)) continue;
        await this.unlockChannelForLockdown(channel, guild.id);
      }
      await updateGuildConfig(guild.id, { lockdownChannels: [] });
    }

    await client.logHandler.logEmergency(guild, {
      type: newPanic ? 'panic' : 'panic_off',
      triggeredBy: interaction.user,
    });

    const embed = new EmbedBuilder()
      .setColor(newPanic ? CONFIG.PANIC_COLOR : CONFIG.SUCCESS_COLOR)
      .setTitle(newPanic ? 'Panic Mode Activated' : 'Panic Mode Deactivated')
      .setDescription(newPanic
        ? 'All channels locked. Webhooks deleted. Dangerous actions frozen.'
        : 'Server returned to normal operation.'
      );

    await interaction.reply({ embeds: [embed], ephemeral: true });

    // Alert owner
    if (newPanic) {
      try {
        const owner = await guild.fetchOwner();
        await owner.send(`Panic mode activated in **${guild.name}** by ${interaction.user.tag}.`).catch(() => null);
      } catch {
        // Skip
      }
    }
  }
}

export const commandHandler = new CommandHandlerClass();
