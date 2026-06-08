import { Sticker } from 'discord.js';
import { BaseProtection } from './BaseProtection';

export class StickerProtection extends BaseProtection {
  async handleStickerCreate(sticker: Sticker): Promise<void> {
    if (!sticker.guildId || !this.configRepo.isEnabled(sticker.guildId)) return;

    const detectionResult = await this.detection.trackAction(
      sticker.guildId,
      'system',
      'sticker_create',
      sticker.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(sticker.guild!, 'sticker_create', sticker.id, 'sticker', detectionResult);
    }
  }

  async handleStickerDelete(sticker: Sticker): Promise<void> {
    if (!sticker.guildId || !this.configRepo.isEnabled(sticker.guildId)) return;

    const detectionResult = await this.detection.trackAction(
      sticker.guildId,
      'system',
      'sticker_delete',
      sticker.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(sticker.guild!, 'sticker_delete', sticker.id, 'sticker', detectionResult);
    }
  }

  async handleStickerUpdate(_oldSticker: Sticker, newSticker: Sticker): Promise<void> {
    if (!newSticker.guildId || !this.configRepo.isEnabled(newSticker.guildId)) return;

    const detectionResult = await this.detection.trackAction(
      newSticker.guildId,
      'system',
      'sticker_update',
      newSticker.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(newSticker.guild!, 'sticker_update', newSticker.id, 'sticker', detectionResult);
    }
  }
}
