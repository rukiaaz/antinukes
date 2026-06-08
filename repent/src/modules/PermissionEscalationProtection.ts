import { Role, PermissionFlagsBits } from 'discord.js';
import { BaseProtection } from './BaseProtection';
import type { DangerousPermission } from '../types';

export class PermissionEscalationProtection extends BaseProtection {
  private dangerousPermissions: DangerousPermission[] = [
    'Administrator',
    'ManageGuild',
    'ManageRoles',
    'ManageChannels',
    'BanMembers',
    'KickMembers',
    'ManageWebhooks',
    'ManageEmojisAndStickers',
    'ManageEvents',
    'ModerateMembers',
  ];

  async handleRoleUpdate(oldRole: Role, newRole: Role): Promise<void> {
    if (!this.configRepo.isEnabled(newRole.guild.id)) return;

    const oldPerms = oldRole.permissions;
    const newPerms = newRole.permissions;

    const grantedDangerous: DangerousPermission[] = [];

    for (const permName of this.dangerousPermissions) {
      const flag = PermissionFlagsBits[permName];
      if (!oldPerms.has(flag) && newPerms.has(flag)) {
        grantedDangerous.push(permName);
      }
    }

    if (grantedDangerous.length === 0) return;

    this.logger.warn('Dangerous permissions granted', {
      guildId: newRole.guild.id,
      roleId: newRole.id,
      permissions: grantedDangerous,
    });

    try {
      const auditLogs = await newRole.guild.fetchAuditLogs({
        limit: 5,
        type: 31,
      });

      const entry = auditLogs.entries.find(e => {
        const target = e.target;
        return target && typeof target === 'object' && 'id' in target && target.id === newRole.id;
      });

      if (!entry || !entry.executor || entry.executor.partial) return;

      if (entry.executor.id === newRole.guild.client.user?.id) return;
      if (entry.executor.id === newRole.guild.ownerId) return;

      try {
        await newRole.setPermissions(oldPerms, 'Repent: Reverting dangerous permission escalation');
      } catch (permError) {
        this.logger.error('Failed to revert role permissions', { error: permError, roleId: newRole.id });
      }

      const executor = entry.executor as any;
      const canPunish = await this.punishment.canPunish(newRole.guild, executor.id);
      if (!canPunish) return;

      const result = await this.punishment.punish(
        newRole.guild,
        executor,
        `Repent: Permission escalation (${grantedDangerous.join(', ')}) on role ${newRole.name}`
      );

      await this.logging.logPunishment(newRole.guild, executor, result.action, result.success, result.error);

      await this.logging.logProtection({
        guild: newRole.guild,
        executor: executor,
        action: 'permission_escalation',
        targetId: newRole.id,
        targetType: 'role',
        detectionResult: {
          triggered: true,
          userId: executor.id,
          action: 'permission_escalation',
          count: 1,
          threshold: 1,
          window: 0,
        },
      });
    } catch (error) {
      this.logger.error('Permission escalation handling failed', { error, guildId: newRole.guild.id });
    }
  }
}
