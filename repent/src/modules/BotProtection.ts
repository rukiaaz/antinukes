import { GuildMember } from 'discord.js';
import { BaseProtection } from './BaseProtection';

export class BotProtection extends BaseProtection {
  async handleGuildMemberAdd(member: GuildMember): Promise<void> {
    if (!this.configRepo.isEnabled(member.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      member.guild.id,
      'system',
      'bot_add',
      member.id
    );

    if (detectionResult.triggered) {
      try {
        const auditLogs = await member.guild.fetchAuditLogs({
          limit: 5,
          type: 28,
        });

        const entry = auditLogs.entries.find(e => {
          const target = e.target;
          return target && typeof target === 'object' && 'id' in target && target.id === member.id;
        });

        if (entry?.executor && !entry.executor.partial) {
          const canPunish = await this.punishment.canPunish(member.guild, entry.executor.id);
          if (canPunish) {
            const result = await this.punishment.punish(
              member.guild,
              entry.executor as any,
              'Repent: Unauthorized bot addition'
            );
            await this.logging.logPunishment(member.guild, entry.executor as any, result.action, result.success, result.error);
          }
        }

        await member.kick('Repent: Unauthorized bot');
        this.logger.info('Kicked unauthorized bot', { guildId: member.guild.id, botId: member.id });
      } catch (error) {
        this.logger.error('Failed to handle unauthorized bot', { error, guildId: member.guild.id, botId: member.id });
      }
    }
  }
}
