import type { ActionType, ActionRecord, DetectionResult, PunishmentType } from '../types';
import { CONFIG } from '../utils/config';
import { AuditLogReader } from '../utils/AuditLogReader';
import type { Guild, User } from 'discord.js';

interface WindowEntry {
  targetId: string;
  timestamp: number;
}

interface UserWindow {
  actions: Map<ActionType, WindowEntry[]>;
  lastCleanup: number;
}

export class ActionTracker {
  private windows: Map<string, UserWindow> = new Map();

  public async recordAndCheck(
    guild: Guild,
    actionType: ActionType,
    targetId: string,
    threshold: number,
    windowSeconds: number,
    punishment: PunishmentType
  ): Promise<DetectionResult> {
    const now = Date.now();
    const windowMs = windowSeconds * 1000;

    const auditResult = await AuditLogReader.getExecutor(guild, actionType, targetId);
    if (!auditResult.executor) {
      return { triggered: false, executor: null, actionType, count: 0, threshold, punishment };
    }

    const executorId = auditResult.executor.id;
    const userWindow = this.getOrCreateWindow(executorId);

    let entries = userWindow.actions.get(actionType);
    if (!entries) {
      entries = [];
      userWindow.actions.set(actionType, entries);
    }

    entries.push({ targetId, timestamp: now });

    const cutoff = now - windowMs;
    const recent = entries.filter(e => e.timestamp >= cutoff);
    userWindow.actions.set(actionType, recent);

    const count = recent.length;
    const triggered = count >= threshold;

    return {
      triggered,
      executor: auditResult.executor,
      actionType,
      count,
      threshold,
      punishment,
      targets: recent.map(e => e.targetId),
    };
  }

  public recordAction(userId: string, actionType: ActionType, targetId: string): void {
    const now = Date.now();
    const userWindow = this.getOrCreateWindow(userId);

    let entries = userWindow.actions.get(actionType);
    if (!entries) {
      entries = [];
      userWindow.actions.set(actionType, entries);
    }

    entries.push({ targetId, timestamp: now });
  }

  public getRecentCount(userId: string, actionType: ActionType, windowSeconds: number): number {
    const userWindow = this.windows.get(userId);
    if (!userWindow) return 0;

    const entries = userWindow.actions.get(actionType);
    if (!entries) return 0;

    const cutoff = Date.now() - windowSeconds * 1000;
    return entries.filter(e => e.timestamp >= cutoff).length;
  }

  public cleanup(): void {
    const now = Date.now();
    const maxWindow = CONFIG.MAX_ACTION_WINDOW_MS;

    for (const [userId, userWindow] of this.windows.entries()) {
      for (const [actionType, entries] of userWindow.actions.entries()) {
        const cutoff = now - maxWindow;
        const recent = entries.filter(e => e.timestamp >= cutoff);
        if (recent.length === 0) {
          userWindow.actions.delete(actionType);
        } else {
          userWindow.actions.set(actionType, recent);
        }
      }

      if (userWindow.actions.size === 0) {
        this.windows.delete(userId);
      }
    }
  }

  public destroy(): void {
    this.windows.clear();
  }

  private getOrCreateWindow(userId: string): UserWindow {
    let window = this.windows.get(userId);
    if (!window) {
      window = { actions: new Map(), lastCleanup: Date.now() };
      this.windows.set(userId, window);
    }
    return window;
  }
}
