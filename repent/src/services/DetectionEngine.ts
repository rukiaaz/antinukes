import { ActionHistoryRepo } from '../database/ActionHistoryRepo';
import { ThresholdRepo } from '../database/ThresholdRepo';
import { WhitelistRepo } from '../database/WhitelistRepo';
import type { TrackedAction, DetectionResult } from '../types';
import { PermissionFlagsBits } from 'discord.js';

export class DetectionEngine {
  private actionHistory: ActionHistoryRepo;
  private thresholdRepo: ThresholdRepo;
  private whitelistRepo: WhitelistRepo;
  private recentActions: Map<string, number[]>;

  constructor() {
    this.actionHistory = new ActionHistoryRepo();
    this.thresholdRepo = new ThresholdRepo();
    this.whitelistRepo = new WhitelistRepo();
    this.recentActions = new Map();
  }

  async trackAction(
    guildId: string,
    userId: string,
    action: TrackedAction,
    targetId: string | null,
    _member?: any
  ): Promise<DetectionResult> {
    const threshold = this.thresholdRepo.getThresholdForAction(guildId, action);

    if (!threshold) {
      return {
        triggered: false,
        userId,
        action,
        count: 0,
        threshold: 0,
        window: 0,
      };
    }

    this.actionHistory.recordAction(guildId, userId, action, targetId);

    const windowMs = threshold.window * 1000;
    const count = this.actionHistory.getActionCount(guildId, userId, action, windowMs);

    const cacheKey = `${guildId}:${userId}:${action}`;
    const timestamps = this.recentActions.get(cacheKey) || [];
    const now = Date.now();
    const validTimestamps = timestamps.filter(t => now - t < windowMs);
    validTimestamps.push(now);
    this.recentActions.set(cacheKey, validTimestamps);

    const memoryCount = validTimestamps.length;
    const finalCount = Math.max(count, memoryCount);

    return {
      triggered: finalCount >= threshold.limit,
      userId,
      action,
      count: finalCount,
      threshold: threshold.limit,
      window: threshold.window,
    };
  }

  async checkPermissionEscalation(
    _guildId: string,
    _executorId: string,
    _executorMember: any | undefined,
    newPermissions: bigint
  ): Promise<DetectionResult> {
    const dangerousPerms = [
      PermissionFlagsBits.Administrator,
      PermissionFlagsBits.ManageGuild,
      PermissionFlagsBits.ManageRoles,
      PermissionFlagsBits.ManageChannels,
      PermissionFlagsBits.BanMembers,
      PermissionFlagsBits.KickMembers,
      PermissionFlagsBits.ManageWebhooks,
      PermissionFlagsBits.ManageEmojisAndStickers,
      PermissionFlagsBits.ManageEvents,
      PermissionFlagsBits.ModerateMembers,
    ];

    const hasDangerous = dangerousPerms.some(perm => (newPermissions & perm) === perm);

    if (!hasDangerous) {
      return {
        triggered: false,
        userId: '',
        action: 'permission_escalation',
        count: 0,
        threshold: 1,
        window: 0,
      };
    }

    return {
      triggered: true,
      userId: '',
      action: 'permission_escalation',
      count: 1,
      threshold: 1,
      window: 0,
    };
  }

  isWhitelisted(guildId: string, userId: string, member?: any): boolean {
    const roleIds = member?.roles?.cache?.map((r: any) => r.id) || [];
    return this.whitelistRepo.isWhitelisted(guildId, userId, roleIds);
  }

  cleanup(): void {
    const now = Date.now();
    const maxWindow = 60000;

    for (const [key, timestamps] of this.recentActions.entries()) {
      const valid = timestamps.filter(t => now - t < maxWindow);
      if (valid.length === 0) {
        this.recentActions.delete(key);
      } else {
        this.recentActions.set(key, valid);
      }
    }
  }
}
