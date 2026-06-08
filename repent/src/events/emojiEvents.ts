import { GuildEmoji, Sticker } from 'discord.js';
import { EmojiProtection } from '../modules/EmojiProtection';
import { StickerProtection } from '../modules/StickerProtection';
import { Logger } from '../utils/Logger';

const emojiProtection = new EmojiProtection();
const stickerProtection = new StickerProtection();
const logger = Logger.getInstance();

export const emojiEvents = {
  async handleEmojiCreate(emoji: GuildEmoji): Promise<void> {
    try {
      await emojiProtection.handleEmojiCreate(emoji);
    } catch (error) {
      logger.error('Emoji create protection error', { error, emojiId: emoji.id });
    }
  },

  async handleEmojiDelete(emoji: GuildEmoji): Promise<void> {
    try {
      await emojiProtection.handleEmojiDelete(emoji);
    } catch (error) {
      logger.error('Emoji delete protection error', { error, emojiId: emoji.id });
    }
  },

  async handleEmojiUpdate(oldEmoji: GuildEmoji, newEmoji: GuildEmoji): Promise<void> {
    try {
      await emojiProtection.handleEmojiUpdate(oldEmoji, newEmoji);
    } catch (error) {
      logger.error('Emoji update protection error', { error, emojiId: newEmoji.id });
    }
  },

  async handleStickerCreate(sticker: Sticker): Promise<void> {
    try {
      await stickerProtection.handleStickerCreate(sticker);
    } catch (error) {
      logger.error('Sticker create protection error', { error, stickerId: sticker.id });
    }
  },

  async handleStickerDelete(sticker: Sticker): Promise<void> {
    try {
      await stickerProtection.handleStickerDelete(sticker);
    } catch (error) {
      logger.error('Sticker delete protection error', { error, stickerId: sticker.id });
    }
  },

  async handleStickerUpdate(oldSticker: Sticker, newSticker: Sticker): Promise<void> {
    try {
      await stickerProtection.handleStickerUpdate(oldSticker, newSticker);
    } catch (error) {
      logger.error('Sticker update protection error', { error, stickerId: newSticker.id });
    }
  },
};
