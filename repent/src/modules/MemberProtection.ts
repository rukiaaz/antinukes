import { Guild, GuildMember, User, PartialGuildMember } from 'discord.js';
import { BaseProtection } from './BaseProtection';

export class MemberProtection extends BaseProtection {
  async handleGuildBanAdd(guild: Guild, user: User): Promise<void> {
    if (!this.configRepo.isEnabled(guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      guild.id,
      'system',
      'ban',
      user.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(guild, 'ban', user.id, 'user', detectionResult);
    }
  }

  async handleGuildMemberRemove(member: GuildMember | PartialGuildMember): Promise<void> {
    if (!member.guild || !this.configRepo.isEnabled(member.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      member.guild.id,
      'system',
      'kick',
      member.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(member.guild, 'kick', member.id, 'user', detectionResult);
    }
  }

  async handleGuildMemberUpdate(oldMember: GuildMember, newMember: GuildMember): Promise<void> {
    if (!this.configRepo.isEnabled(newMember.guild.id)) return;

    if (newMember.communicationDisabledUntil !== oldMember.communicationDisabledUntil) {
      const detectionResult = await this.detection.trackAction(
        newMember.guild.id,
        'system',
        'timeout',
        newMember.id
      );

      if (detectionResult.triggered) {
        await this.verifyAndHandle(newMember.guild, 'timeout', newMember.id, 'user', detectionResult);
      }
    }

    const oldRoles = new Set(oldMember.roles.cache.keys());
    const newRoles = new Set(newMember.roles.cache.keys());

    const addedRoles = [...newRoles].filter(id => !oldRoles.has(id));
    const removedRoles = [...oldRoles].filter(id => !newRoles.has(id));

    if (addedRoles.length > 0) {
      for (const roleId of addedRoles) {
        const detectionResult = await this.detection.trackAction(
          newMember.guild.id,
          'system',
          'member_role_update',
          roleId
        );

        if (detectionResult.triggered) {
          await this.verifyAndHandle(newMember.guild, 'member_role_update', newMember.id, 'user', detectionResult);
          break;
        }
      }
    }

    if (removedRoles.length > 0) {
      for (const roleId of removedRoles) {
        const detectionResult = await this.detection.trackAction(
          newMember.guild.id,
          'system',
          'member_role_update',
          roleId
        );

        if (detectionResult.triggered) {
          await this.verifyAndHandle(newMember.guild, 'member_role_update', newMember.id, 'user', detectionResult);
          break;
        }
      }
    }
  }
}
