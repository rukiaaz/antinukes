import {
  Client,
  Collection,
  GatewayIntentBits,
  Partials,
  type Guild,
} from 'discord.js';
import { CONFIG } from '../utils/config';
import { connectDatabase, isConnected } from '../utils/database';
import { createGuildConfig, getGuildConfig } from '../models/GuildSettings';
import { saveBackup, deleteBackups } from '../models/Backup';
import { ActionTracker } from './ActionTracker';
import { BackupManager } from './BackupManager';
import { PunishmentHandler } from './PunishmentHandler';
import { LogHandler } from './LogHandler';
import { ProtectionHandler } from './ProtectionHandler';
import type { BackupData } from '../types';

export class Repent extends Client {
  public readonly actionTracker: ActionTracker;
  public readonly backupManager: BackupManager;
  public readonly punishmentHandler: PunishmentHandler;
  public readonly logHandler: LogHandler;
  public readonly protectionHandler: ProtectionHandler;
  public readonly commands: Collection<string, unknown>;

  private backupInterval: NodeJS.Timeout | null = null;
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor() {
    super({
      intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.GuildModeration,
        GatewayIntentBits.GuildEmojisAndStickers,
        GatewayIntentBits.GuildWebhooks,
        GatewayIntentBits.GuildIntegrations,
      ],
      partials: [Partials.GuildMember, Partials.Channel],
      presence: {
        status: 'online',
        activities: [{ name: 'Protecting servers', type: 0 }],
      },
    });

    this.commands = new Collection();
    this.actionTracker = new ActionTracker();
    this.backupManager = new BackupManager();
    this.punishmentHandler = new PunishmentHandler(this);
    this.logHandler = new LogHandler(this);
    this.protectionHandler = new ProtectionHandler(this);
  }

  public async start(): Promise<void> {
    await connectDatabase();

    this.on('ready', this.onReady.bind(this));
    this.on('guildCreate', this.onGuildCreate.bind(this));
    this.on('guildDelete', this.onGuildDelete.bind(this));

    await this.login(CONFIG.TOKEN);
  }

  private async onReady(): Promise<void> {
    if (!this.user) return;
    console.log(`[Repent] Logged in as ${this.user.tag}`);

    for (const guild of this.guilds.cache.values()) {
      await this.ensureGuildConfig(guild);
      await this.performBackup(guild);
    }

    this.backupInterval = setInterval(() => {
      for (const guild of this.guilds.cache.values()) {
        this.performBackup(guild).catch(() => null);
      }
    }, CONFIG.BACKUP_INTERVAL_MS);

    this.cleanupInterval = setInterval(() => {
      this.actionTracker.cleanup();
    }, CONFIG.CLEANUP_INTERVAL_MS);

    await this.protectionHandler.registerCommands();
  }

  private async onGuildCreate(guild: Guild): Promise<void> {
    await this.ensureGuildConfig(guild);
    await this.performBackup(guild);
  }

  private async onGuildDelete(guild: Guild): Promise<void> {
    await deleteBackups(guild.id);
  }

  private async ensureGuildConfig(guild: Guild): Promise<void> {
    const config = await getGuildConfig(guild.id);
    if (!config) {
      await createGuildConfig(guild.id, guild.ownerId);
    }
  }

  private async performBackup(guild: Guild): Promise<void> {
    try {
      const backup = await this.backupManager.createBackup(guild);
      await saveBackup(guild.id, backup);
    } catch {
      // Silently fail backup to prioritize performance
    }
  }

  public async getLatestBackup(guildId: string): Promise<BackupData | null> {
    const { getLatestBackup: getBackup } = await import('../models/Backup');
    return getBackup(guildId);
  }

  public async restoreFromBackup(guildId: string): Promise<void> {
    const backup = await this.getLatestBackup(guildId);
    if (!backup) return;

    const guild = this.guilds.cache.get(guildId);
    if (!guild) return;

    await this.backupManager.restoreBackup(guild, backup);
  }

  public override destroy(): Promise<void> {
    if (this.backupInterval) clearInterval(this.backupInterval);
    if (this.cleanupInterval) clearInterval(this.cleanupInterval);
    this.actionTracker.destroy();
    return super.destroy();
  }
}
