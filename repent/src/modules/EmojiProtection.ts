import { GuildEmoji } from 'discord.js';
import { BaseProtection } from './BaseProtection';

export class EmojiProtection extends BaseProtection {
  async handleEmojiCreate(emoji: GuildEmoji): Promise<void> {
    if (!this.configRepo.isEnabled(emoji.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      emoji.guild.id,
      'system',
      'emoji_create',
      emoji.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(emoji.guild, 'emoji_create', emoji.id, 'emoji', detectionResult);
    }
  }

  async handleEmojiDelete(emoji: GuildEmoji): Promise<void> {
    if (!this.configRepo.isEnabled(emoji.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      emoji.guild.id,
      'system',
      'emoji_delete',
      emoji.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(emoji.guild, 'emoji_delete', emoji.id, 'emoji', detectionResult);

      try {
        await this.recovery.createSnapshot(emoji.guild, `emoji-recovery-${Date.now()}`);
      } catch (error) {
        this.logger.error('Failed to create emoji recovery snapshot', { error, guildId: emoji.guild.id });
      }
    }
  }

  async handleEmojiUpdate(_oldEmoji: GuildEmoji, newEmoji: GuildEmoji): Promise<void> {
    if (!this.configRepo.isEnabled(newEmoji.guild.id)) return;

    const detectionResult = await this.detection.trackAction(
      newEmoji.guild.id,
      'system',
      'emoji_update',
      newEmoji.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(newEmoji.guild, 'emoji_update', newEmoji.id, 'emoji', detectionResult);
    }
  }
}
