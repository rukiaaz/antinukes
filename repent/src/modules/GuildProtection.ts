import { Guild } from 'discord.js';
import { BaseProtection } from './BaseProtection';
import { SnapshotRepo } from '../database/SnapshotRepo';

export class GuildProtection extends BaseProtection {
  private snapshotRepo: SnapshotRepo;

  constructor() {
    super();
    this.snapshotRepo = new SnapshotRepo();
  }

  async handleGuildUpdate(oldGuild: Guild, newGuild: Guild): Promise<void> {
    if (!this.configRepo.isEnabled(newGuild.id)) return;

    const changes: string[] = [];

    if (oldGuild.name !== newGuild.name) changes.push('name');
    if (oldGuild.icon !== newGuild.icon) changes.push('icon');
    if (oldGuild.banner !== newGuild.banner) changes.push('banner');
    if (oldGuild.splash !== newGuild.splash) changes.push('splash');
    if (oldGuild.description !== newGuild.description) changes.push('description');
    if (oldGuild.verificationLevel !== newGuild.verificationLevel) changes.push('verificationLevel');
    if (oldGuild.defaultMessageNotifications !== newGuild.defaultMessageNotifications) changes.push('notifications');
    if (oldGuild.explicitContentFilter !== newGuild.explicitContentFilter) changes.push('contentFilter');

    if (changes.length === 0) return;

    const detectionResult = await this.detection.trackAction(
      newGuild.id,
      'system',
      'guild_update',
      newGuild.id
    );

    if (detectionResult.triggered) {
      await this.verifyAndHandle(newGuild, 'guild_update', newGuild.id, 'guild', detectionResult);

      try {
        const snapshot = this.snapshotRepo.getLatest(newGuild.id);
        if (snapshot?.data.guildSettings) {
          const updateData: any = {};
          const settings = snapshot.data.guildSettings;

          if (changes.includes('name') && settings.name) updateData.name = settings.name;
          if (changes.includes('verificationLevel') && settings.verificationLevel !== null) {
            updateData.verificationLevel = settings.verificationLevel;
          }

          if (Object.keys(updateData).length > 0) {
            await newGuild.edit(updateData);
          }
        }
      } catch (error) {
        this.logger.error('Failed to restore guild settings', { error, guildId: newGuild.id });
      }
    }
  }
}
