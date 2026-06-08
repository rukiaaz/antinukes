import {
  Events,
  ChannelType,
  PermissionFlagsBits,
  AuditLogEvent,
  type Guild,
  type DMChannel,
  type GuildBasedChannel,
  type GuildMember,
  type PartialGuildMember,
  type Role,
  type User,
  type GuildEmoji,
  type Sticker,
  type GuildBan,
} from 'discord.js';
import type { Repent } from './Repent';
import type { ActionType, PunishmentType, DetectionResult } from '../types';
import { getGuildConfig, isUserWhitelisted } from '../models/GuildSettings';
import { AuditLogReader } from '../utils/AuditLogReader';
import { CONFIG } from '../utils/config';

export class ProtectionHandler {
  constructor(private readonly client: Repent) {
    this.registerListeners();
  }

  private registerListeners(): void {
    this.client.on(Events.ChannelDelete, this.onChannelDelete.bind(this));
    this.client.on(Events.ChannelCreate, this.onChannelCreate.bind(this));
    this.client.on(Events.ChannelUpdate, this.onChannelUpdate.bind(this));
    this.client.on(Events.GuildRoleDelete, this.onRoleDelete.bind(this));
    this.client.on(Events.GuildRoleCreate, this.onRoleCreate.bind(this));
    this.client.on(Events.GuildRoleUpdate, this.onRoleUpdate.bind(this));
    this.client.on(Events.GuildBanAdd, this.onGuildBanAdd.bind(this));
    this.client.on(Events.GuildMemberRemove, this.onGuildMemberRemove.bind(this));
    this.client.on(Events.GuildMemberUpdate, this.onGuildMemberUpdate.bind(this));
    this.client.on(Events.GuildUpdate, this.onGuildUpdate.bind(this));
    this.client.on(Events.WebhooksUpdate, this.onWebhookUpdate.bind(this));
    this.client.on(Events.GuildEmojiDelete, this.onEmojiDelete.bind(this));
    this.client.on(Events.GuildEmojiCreate, this.onEmojiCreate.bind(this));
    this.client.on(Events.GuildStickerDelete, this.onStickerDelete.bind(this));
    this.client.on(Events.GuildStickerCreate, this.onStickerCreate.bind(this));
    this.client.on(Events.GuildMemberAdd, this.onGuildMemberAdd.bind(this));
  }

  // ─── Channel Delete ───
  private async onChannelDelete(channel: DMChannel | GuildBasedChannel): Promise<void> {
    if (!('guild' in channel) || !channel.guild) return;
    const actionType: ActionType = channel.type === ChannelType.GuildCategory
      ? 'categoryDelete'
      : 'channelDelete';
    await this.handleProtection(channel.guild, actionType, channel.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        channel.guild, actionType, channel.id,
        await this.getThreshold(channel.guild.id, actionType),
        await this.getWindow(channel.guild.id, actionType),
        await this.getPunishment(channel.guild.id, actionType)
      );
    });
  }

  // ─── Channel Create ───
  private async onChannelCreate(channel: GuildBasedChannel): Promise<void> {
    if (!channel.guild) return;
    const actionType: ActionType = 'channelCreate';
    await this.handleProtection(channel.guild, actionType, channel.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        channel.guild, actionType, channel.id,
        await this.getThreshold(channel.guild.id, actionType),
        await this.getWindow(channel.guild.id, actionType),
        await this.getPunishment(channel.guild.id, actionType)
      );
    });
  }

  // ─── Channel Update ───
  private async onChannelUpdate(
    _oldChannel: DMChannel | GuildBasedChannel,
    newChannel: DMChannel | GuildBasedChannel
  ): Promise<void> {
    if (!('guild' in newChannel) || !newChannel.guild) return;
    const actionType: ActionType = newChannel.type === ChannelType.GuildCategory
      ? 'categoryUpdate'
      : 'channelUpdate';
    await this.handleProtection(newChannel.guild, actionType, newChannel.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        newChannel.guild, actionType, newChannel.id,
        await this.getThreshold(newChannel.guild.id, actionType),
        await this.getWindow(newChannel.guild.id, actionType),
        await this.getPunishment(newChannel.guild.id, actionType)
      );
    });
  }

  // ─── Role Delete ───
  private async onRoleDelete(role: Role): Promise<void> {
    const actionType: ActionType = 'roleDelete';
    await this.handleProtection(role.guild, actionType, role.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        role.guild, actionType, role.id,
        await this.getThreshold(role.guild.id, actionType),
        await this.getWindow(role.guild.id, actionType),
        await this.getPunishment(role.guild.id, actionType)
      );
    });
  }

  // ─── Role Create ───
  private async onRoleCreate(role: Role): Promise<void> {
    const actionType: ActionType = 'roleCreate';
    await this.handleProtection(role.guild, actionType, role.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        role.guild, actionType, role.id,
        await this.getThreshold(role.guild.id, actionType),
        await this.getWindow(role.guild.id, actionType),
        await this.getPunishment(role.guild.id, actionType)
      );
    });
  }

  // ─── Role Update ───
  private async onRoleUpdate(oldRole: Role, newRole: Role): Promise<void> {
    const guild = newRole.guild;

    // Check for permission escalation
    const oldPerms = oldRole.permissions.bitfield;
    const newPerms = newRole.permissions.bitfield;
    const addedPerms = newPerms & ~oldPerms;

    const isDangerous = CONFIG.DANGEROUS_PERMISSIONS.some(dp => {
      const permFlag = PermissionFlagsBits[dp as keyof typeof PermissionFlagsBits];
      return permFlag && (addedPerms & permFlag) === permFlag;
    });

    if (isDangerous) {
      const result = await AuditLogReader.getPermissionEscalationEntry(guild, newRole.id);
      if (result.executor) {
        const whitelisted = await this.isWhitelisted(guild, result.executor.id);
        if (!whitelisted) {
          await this.client.punishmentHandler.execute(
            guild, result.executor,
            await this.getPunishment(guild.id, 'permissionEscalation'),
            'permissionEscalation'
          );
          await this.client.punishmentHandler.removeDangerousPermissions(guild, newRole.id);
          await this.client.logHandler.logProtectionTriggered(guild, {
            executor: result.executor,
            actionType: 'permissionEscalation',
            count: 1,
            threshold: 1,
            punishment: await this.getPunishment(guild.id, 'permissionEscalation'),
            targets: [newRole.id],
          });
          return;
        }
      }
    }

    const actionType: ActionType = 'roleUpdate';
    await this.handleProtection(guild, actionType, newRole.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        guild, actionType, newRole.id,
        await this.getThreshold(guild.id, actionType),
        await this.getWindow(guild.id, actionType),
        await this.getPunishment(guild.id, actionType)
      );
    });
  }

  // ─── Guild Ban Add ───
  private async onGuildBanAdd(ban: GuildBan): Promise<void> {
    const guild = ban.guild;
    const actionType: ActionType = 'massBan';
    await this.handleProtection(guild, actionType, ban.user.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        guild, actionType, ban.user.id,
        await this.getThreshold(guild.id, actionType),
        await this.getWindow(guild.id, actionType),
        await this.getPunishment(guild.id, actionType)
      );
    });
  }

  // ─── Guild Member Remove (Kick) ───
  private async onGuildMemberRemove(member: GuildMember | PartialGuildMember): Promise<void> {
    const guild = member.guild;
    const actionType: ActionType = 'massKick';
    await this.handleProtection(guild, actionType, member.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        guild, actionType, member.id,
        await this.getThreshold(guild.id, actionType),
        await this.getWindow(guild.id, actionType),
        await this.getPunishment(guild.id, actionType)
      );
    });
  }

  // ─── Guild Member Update (Timeout) ───
  private async onGuildMemberUpdate(
    oldMember: GuildMember | PartialGuildMember,
    newMember: GuildMember
  ): Promise<void> {
    if (!oldMember.communicationDisabledUntil && newMember.communicationDisabledUntil) {
      const guild = newMember.guild;
      const actionType: ActionType = 'massTimeout';
      await this.handleProtection(guild, actionType, newMember.id, async () => {
        return this.client.actionTracker.recordAndCheck(
          guild, actionType, newMember.id,
          await this.getThreshold(guild.id, actionType),
          await this.getWindow(guild.id, actionType),
          await this.getPunishment(guild.id, actionType)
        );
      });
    }
  }

  // ─── Guild Update ───
  private async onGuildUpdate(_oldGuild: Guild, newGuild: Guild): Promise<void> {
    const actionType: ActionType = 'serverUpdate';
    await this.handleProtection(newGuild, actionType, newGuild.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        newGuild, actionType, newGuild.id,
        await this.getThreshold(newGuild.id, actionType),
        await this.getWindow(newGuild.id, actionType),
        await this.getPunishment(newGuild.id, actionType)
      );
    });
  }

  // ─── Webhook Update ───
  private async onWebhookUpdate({ guild }: { guild: Guild | null }): Promise<void> {
    if (!guild) return;
    try {
      const logs = await guild.fetchAuditLogs({
        limit: 1,
        type: AuditLogEvent.WebhookCreate,
      });
      const entry = logs.entries.first();
      if (entry && entry.executor && !entry.executor.bot) {
        const age = Date.now() - entry.createdTimestamp;
        if (age <= CONFIG.AUDIT_LOG_MAX_AGE_MS) {
          const executor = entry.executor as User;
          await this.handleProtection(guild, 'webhookCreate', entry.targetId ?? guild.id, async () => ({
            triggered: false,
            executor,
            actionType: 'webhookCreate' as ActionType,
            count: 0,
            threshold: 0,
            punishment: 'ban' as PunishmentType,
          }));
        }
      }
    } catch {
      // Ignore webhook audit log failures
    }
  }

  // ─── Emoji Delete ───
  private async onEmojiDelete(emoji: GuildEmoji): Promise<void> {
    const guild = emoji.guild;
    const actionType: ActionType = 'emojiDelete';
    await this.handleProtection(guild, actionType, emoji.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        guild, actionType, emoji.id,
        await this.getThreshold(guild.id, actionType),
        await this.getWindow(guild.id, actionType),
        await this.getPunishment(guild.id, actionType)
      );
    });
  }

  // ─── Emoji Create ───
  private async onEmojiCreate(emoji: GuildEmoji): Promise<void> {
    const guild = emoji.guild;
    const actionType: ActionType = 'emojiCreate';
    await this.handleProtection(guild, actionType, emoji.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        guild, actionType, emoji.id,
        await this.getThreshold(guild.id, actionType),
        await this.getWindow(guild.id, actionType),
        await this.getPunishment(guild.id, actionType)
      );
    });
  }

  // ─── Sticker Delete ───
  private async onStickerDelete(sticker: Sticker): Promise<void> {
    if (!sticker.guild) return;
    const guild = sticker.guild;
    const actionType: ActionType = 'stickerDelete';
    await this.handleProtection(guild, actionType, sticker.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        guild, actionType, sticker.id,
        await this.getThreshold(guild.id, actionType),
        await this.getWindow(guild.id, actionType),
        await this.getPunishment(guild.id, actionType)
      );
    });
  }

  // ─── Sticker Create ───
  private async onStickerCreate(sticker: Sticker): Promise<void> {
    if (!sticker.guild) return;
    const guild = sticker.guild;
    const actionType: ActionType = 'stickerCreate';
    await this.handleProtection(guild, actionType, sticker.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        guild, actionType, sticker.id,
        await this.getThreshold(guild.id, actionType),
        await this.getWindow(guild.id, actionType),
        await this.getPunishment(guild.id, actionType)
      );
    });
  }

  // ─── Bot Add ───
  private async onGuildMemberAdd(member: GuildMember): Promise<void> {
    if (!member.user.bot) return;
    const guild = member.guild;
    const actionType: ActionType = 'botAdd';
    await this.handleProtection(guild, actionType, member.id, async () => {
      return this.client.actionTracker.recordAndCheck(
        guild, actionType, member.id,
        await this.getThreshold(guild.id, actionType),
        await this.getWindow(guild.id, actionType),
        await this.getPunishment(guild.id, actionType)
      );
    });
  }

  // ─── Core Handler ───
  private async handleProtection(
    guild: Guild,
    actionType: ActionType,
    targetId: string,
    detectFn: () => Promise<DetectionResult>
  ): Promise<void> {
    const config = await getGuildConfig(guild.id);
    if (!config) return;
    if (config.panicMode && actionType !== 'serverUpdate') return;

    const protConfig = config.protections[actionType];
    if (!protConfig?.enabled) return;

    const result = await detectFn();
    if (!result.triggered || !result.executor) return;

    const whitelisted = await this.isWhitelisted(guild, result.executor.id);
    if (whitelisted) return;

    // Execute punishment first, log second
    const success = await this.client.punishmentHandler.execute(
      guild, result.executor, result.punishment, actionType
    );

    // Restore from backup
    if (['channelDelete', 'categoryDelete', 'roleDelete', 'webhookDelete', 'emojiDelete', 'stickerDelete'].includes(actionType)) {
      await this.client.restoreFromBackup(guild.id);
    }

    // Remove dangerous permissions for permission escalation
    if (actionType === 'permissionEscalation' && targetId) {
      await this.client.punishmentHandler.removeDangerousPermissions(guild, targetId);
    }

    // Log after punishment
    await this.client.logHandler.logProtectionTriggered(guild, {
      executor: result.executor,
      actionType,
      count: result.count,
      threshold: result.threshold,
      punishment: result.punishment,
      targets: result.targets ?? [targetId],
    });

    await this.client.logHandler.logPunishmentExecuted(guild, {
      target: result.executor,
      punishment: result.punishment,
      success,
      reason: `Repent anti-nuke: ${actionType}`,
    });
  }

  private async isWhitelisted(guild: Guild, userId: string): Promise<boolean> {
    if (guild.ownerId === userId) return true;

    const member = guild.members.cache.get(userId);
    const roleIds = member?.roles.cache.map(r => r.id) ?? [];
    return isUserWhitelisted(guild.id, userId, roleIds);
  }

  private async getThreshold(guildId: string, actionType: ActionType): Promise<number> {
    const config = await getGuildConfig(guildId);
    return config?.protections[actionType]?.threshold ?? 3;
  }

  private async getWindow(guildId: string, actionType: ActionType): Promise<number> {
    const config = await getGuildConfig(guildId);
    return config?.protections[actionType]?.windowSeconds ?? 10;
  }

  private async getPunishment(guildId: string, actionType: ActionType): Promise<PunishmentType> {
    const config = await getGuildConfig(guildId);
    return config?.protections[actionType]?.punishment ?? 'ban';
  }

  public async registerCommands(): Promise<void> {
    const { SlashCommandBuilder, PermissionFlagsBits: Perms } = await import('discord.js');

    const setup = new SlashCommandBuilder()
      .setName('setup')
      .setDescription('Configure Repent protection for this server')
      .addChannelOption(opt =>
        opt
          .setName('log_channel')
          .setDescription('Channel to send protection alerts to')
          .setRequired(true)
      )
      .addStringOption(opt =>
        opt
          .setName('punishment')
          .setDescription('Default punishment for enabled modules')
          .setRequired(true)
          .addChoices(
            { name: 'Ban', value: 'ban' },
            { name: 'Kick', value: 'kick' },
            { name: 'Timeout', value: 'timeout' },
            { name: 'Remove Dangerous Roles', value: 'removeRoles' }
          )
      )
      // Security is enforced in code via DB ownerId checks; keep permissive registration.
      .setDefaultMemberPermissions(Perms.Administrator);

    const whitelistAdd = new SlashCommandBuilder()
      .setName('whitelist-add')
      .setDescription('Add a user or role to the whitelist (owner only)')
      .addUserOption(opt =>
        opt.setName('user').setDescription('User to whitelist').setRequired(false)
      )
      .addRoleOption(opt =>
        opt.setName('role').setDescription('Role to whitelist').setRequired(false)
      )
      .setDefaultMemberPermissions(0);

    const whitelistRemove = new SlashCommandBuilder()
      .setName('whitelist-remove')
      .setDescription('Remove a user or role from the whitelist (owner only)')
      .addUserOption(opt =>
        opt.setName('user').setDescription('User to remove').setRequired(false)
      )
      .addRoleOption(opt =>
        opt.setName('role').setDescription('Role to remove').setRequired(false)
      )
      .setDefaultMemberPermissions(0);

    const configCmd = new SlashCommandBuilder()
      .setName('config')
      .setDescription('View or modify protection configuration')
      .addStringOption(opt =>
        opt.setName('module')
          .setDescription('Protection module to configure')
          .setRequired(false)
          .addChoices(
            { name: 'Channel Delete', value: 'channelDelete' },
            { name: 'Channel Create', value: 'channelCreate' },
            { name: 'Channel Update', value: 'channelUpdate' },
            { name: 'Category Delete', value: 'categoryDelete' },
            { name: 'Category Update', value: 'categoryUpdate' },
            { name: 'Role Delete', value: 'roleDelete' },
            { name: 'Role Create', value: 'roleCreate' },
            { name: 'Role Update', value: 'roleUpdate' },
            { name: 'Permission Escalation', value: 'permissionEscalation' },
            { name: 'Webhook', value: 'webhookCreate' },
            { name: 'Mass Ban', value: 'massBan' },
            { name: 'Mass Kick', value: 'massKick' },
            { name: 'Mass Timeout', value: 'massTimeout' },
            { name: 'Bot Add', value: 'botAdd' },
            { name: 'Emoji Delete', value: 'emojiDelete' },
            { name: 'Emoji Create', value: 'emojiCreate' },
            { name: 'Sticker Delete', value: 'stickerDelete' },
            { name: 'Sticker Create', value: 'stickerCreate' },
            { name: 'Server Update', value: 'serverUpdate' },
          )
      )
      .setDefaultMemberPermissions(Perms.Administrator);

    const status = new SlashCommandBuilder()
      .setName('status')
      .setDescription('View current protection status')
      .setDefaultMemberPermissions(Perms.Administrator);

    const lockdown = new SlashCommandBuilder()
      .setName('lockdown')
      .setDescription('Lock down all channels')
      .setDefaultMemberPermissions(Perms.Administrator);

    const unlockdown = new SlashCommandBuilder()
      .setName('unlockdown')
      .setDescription('Remove lockdown from all channels')
      .setDefaultMemberPermissions(Perms.Administrator);

    const panic = new SlashCommandBuilder()
      .setName('panic')
      .setDescription('Toggle panic mode')
      .setDefaultMemberPermissions(Perms.Administrator);

    const commands = [
      setup.toJSON(),
      whitelistAdd.toJSON(),
      whitelistRemove.toJSON(),
      configCmd.toJSON(),
      status.toJSON(),
      lockdown.toJSON(),
      unlockdown.toJSON(),
      panic.toJSON(),
    ];

    try {
      await this.client.application?.commands.set(commands);
      for (const guild of this.client.guilds.cache.values()) {
        await guild.commands.set(commands);
      }
    } catch {
      // Fail silently on command registration
    }

    this.client.on(Events.InteractionCreate, this.onInteractionCreate.bind(this));
  }

  private async onInteractionCreate(interaction: any): Promise<void> {
    if (!interaction.isChatInputCommand()) return;

    const { commandHandler } = await import('../handlers/CommandHandler');
    await commandHandler.handle(interaction, this.client);
  }
}
