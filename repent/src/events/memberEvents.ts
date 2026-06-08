import { GuildBan, GuildMember, PartialGuildMember } from 'discord.js';
import { MemberProtection } from '../modules/MemberProtection';
import { BotProtection } from '../modules/BotProtection';
import { Logger } from '../utils/Logger';

const memberProtection = new MemberProtection();
const botProtection = new BotProtection();
const logger = Logger.getInstance();

export const memberEvents = {
  async handleBanAdd(ban: GuildBan): Promise<void> {
    try {
      await memberProtection.handleGuildBanAdd(ban.guild, ban.user);
    } catch (error) {
      logger.error('Ban add protection error', { error, guildId: ban.guild.id, userId: ban.user.id });
    }
  },

  async handleMemberRemove(member: GuildMember | PartialGuildMember): Promise<void> {
    try {
      await memberProtection.handleGuildMemberRemove(member);
    } catch (error) {
      logger.error('Member remove protection error', { error, guildId: member.guild?.id });
    }
  },

  async handleMemberUpdate(oldMember: GuildMember, newMember: GuildMember): Promise<void> {
    try {
      await memberProtection.handleGuildMemberUpdate(oldMember, newMember);
    } catch (error) {
      logger.error('Member update protection error', { error, guildId: newMember.guild.id });
    }
  },

  async handleMemberAdd(member: GuildMember): Promise<void> {
    if (member.user.bot) {
      try {
        await botProtection.handleGuildMemberAdd(member);
      } catch (error) {
        logger.error('Bot add protection error', { error, guildId: member.guild.id, botId: member.id });
      }
    }
  },
};
