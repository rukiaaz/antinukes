import { Guild, User } from 'discord.js';
import { DetectionEngine } from '../services/DetectionEngine';
import { AuditLogVerifier } from '../services/AuditLogVerifier';
import { PunishmentService } from '../services/PunishmentService';
import { LoggingService } from '../services/LoggingService';
import { RecoveryService } from '../services/RecoveryService';
import { WhitelistRepo } from '../database/WhitelistRepo';
import { GuildConfigRepo } from '../database/GuildConfigRepo';
import { Logger } from '../utils/Logger';
import type { TrackedAction, DetectionResult } from '../types';

export abstract class BaseProtection {
  protected detection: DetectionEngine;
  protected auditLog: AuditLogVerifier;
  protected punishment: PunishmentService;
  protected logging: LoggingService;
  protected recovery: RecoveryService;
  protected whitelistRepo: WhitelistRepo;
  protected configRepo: GuildConfigRepo;
  protected logger: Logger;

  constructor() {
    this.detection = new DetectionEngine();
    this.auditLog = new AuditLogVerifier();
    this.punishment = new PunishmentService();
    this.logging = new LoggingService();
    this.recovery = new RecoveryService();
    this.whitelistRepo = new WhitelistRepo();
    this.configRepo = new GuildConfigRepo();
    this.logger = Logger.getInstance();
  }

  protected async handleViolation(
    guild: Guild,
    executor: User,
    action: TrackedAction,
    targetId: string | null,
    targetType: string,
    detectionResult: DetectionResult
  ): Promise<void> {
    try {
      const canPunish = await this.punishment.canPunish(guild, executor.id);
      if (!canPunish) {
        this.logger.warn('Cannot punish user, insufficient permissions', {
          guildId: guild.id,
          userId: executor.id,
        });
        return;
      }

      const result = await this.punishment.punish(
        guild,
        executor,
        `Repent: ${action} violation (count: ${detectionResult.count}, threshold: ${detectionResult.threshold})`
      );

      await this.logging.logPunishment(guild, executor, result.action, result.success, result.error);

      await this.logging.logProtection({
        guild,
        executor,
        action,
        targetId,
        targetType,
        detectionResult,
      });

      if (result.success) {
        await this.recovery.createSnapshot(guild, `auto-recovery-${Date.now()}`);
      }
    } catch (error) {
      this.logger.error('Error handling violation', { error, guildId: guild.id, userId: executor.id });
    }
  }

  protected async verifyAndHandle(
    guild: Guild,
    action: TrackedAction,
    targetId: string | null,
    targetType: string,
    detectionResult: DetectionResult
  ): Promise<void> {
    const verification = await this.auditLog.verify(guild, action, targetId || undefined);

    if (!verification.verified || !verification.executor) {
      this.logger.debug('Audit log verification failed, skipping punishment', {
        guildId: guild.id,
        action,
        targetId,
      });
      return;
    }

    if (verification.executor.id === guild.client.user?.id) {
      return;
    }

    if (verification.executor.id === guild.ownerId) {
      return;
    }

    await this.handleViolation(
      guild,
      verification.executor,
      action,
      targetId,
      targetType,
      detectionResult
    );
  }
}
