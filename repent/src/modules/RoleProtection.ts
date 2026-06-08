import { Role } from 'discord.js';
import { BaseProtection } from './BaseProtection';

export class RoleProtection extends BaseProtection {
  async handleRoleCreate(role: Role): Promise<void> {
    if (!this.configRepo.isEnabled(role.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      role.guild.id,
      'system',
      'role_create',
      role.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(role.guild, 'role_create', role.id, 'role', detectionResult);
    }
  }

  async handleRoleDelete(role: Role): Promise<void> {
    if (!this.configRepo.isEnabled(role.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      role.guild.id,
      'system',
      'role_delete',
      role.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(role.guild, 'role_delete', role.id, 'role', detectionResult);
    }
  }

  async handleRoleUpdate(_oldRole: Role, newRole: Role): Promise<void> {
    if (!this.configRepo.isEnabled(newRole.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      newRole.guild.id,
      'system',
      'role_update',
      newRole.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(newRole.guild, 'role_update', newRole.id, 'role', detectionResult);
    }
  }
}
