import { GuildChannel } from 'discord.js';
import { BaseProtection } from './BaseProtection';

export class ChannelProtection extends BaseProtection {
  async handleChannelDelete(channel: GuildChannel): Promise<void> {
    if (!this.configRepo.isEnabled(channel.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      channel.guild.id,
      'system',
      'channel_delete',
      channel.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(channel.guild, 'channel_delete', channel.id, 'channel', detectionResult);
    }
  }

  async handleChannelCreate(channel: GuildChannel): Promise<void> {
    if (!this.configRepo.isEnabled(channel.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      channel.guild.id,
      'system',
      'channel_create',
      channel.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(channel.guild, 'channel_create', channel.id, 'channel', detectionResult);
    }
  }

  async handleChannelUpdate(_oldChannel: GuildChannel, newChannel: GuildChannel): Promise<void> {
    if (!this.configRepo.isEnabled(newChannel.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      newChannel.guild.id,
      'system',
      'channel_update',
      newChannel.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(newChannel.guild, 'channel_update', newChannel.id, 'channel', detectionResult);
    }
  }
}
