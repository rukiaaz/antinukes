import type { BackupData } from '../types';
import { get, run, all } from '../utils/sqlite';

function rowToBackup(row: any): BackupData {
  const parsed = JSON.parse(row.backup_json) as BackupData;
  return parsed;
}

export async function saveBackup(guildId: string, data: BackupData): Promise<void> {
  const countRow = await get<{ count: number }>(
    `SELECT COUNT(*) as count FROM backups WHERE guild_id = ?`,
    [guildId]
  );
  const count = countRow?.count ?? 0;

  if (count >= 5) {
    // delete oldest until count < 5
    const toDelete = count - 4;
    const oldest = await all<{ id: number }>(
      `SELECT id FROM backups WHERE guild_id = ? ORDER BY timestamp_ms ASC LIMIT ?`,
      [guildId, toDelete]
    );
    for (const row of oldest) {
      await run(`DELETE FROM backups WHERE id = ?`, [row.id]);
    }
  }

  await run(
    `INSERT INTO backups (guild_id, backup_json, timestamp_ms) VALUES (?, ?, ?)`,
    [guildId, JSON.stringify(data), (data.timestamp ? (data.timestamp as any).getTime?.() : Date.now()) ?? Date.now()]
  );
}

export async function getLatestBackup(guildId: string): Promise<BackupData | null> {
  const row = await get<any>(
    `SELECT * FROM backups WHERE guild_id = ? ORDER BY timestamp_ms DESC LIMIT 1`,
    [guildId]
  );
  if (!row) return null;
  return rowToBackup(row);
}

export async function deleteBackups(guildId: string): Promise<void> {
  await run(`DELETE FROM backups WHERE guild_id = ?`, [guildId]);
}

