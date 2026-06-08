import { initSqlite } from './sqlite';

let connected = false;

export async function connectDatabase(): Promise<void> {
  if (connected) return;

  try {
    await initSqlite();
    connected = true;
  } catch (error) {
    console.error('[Repent] Database connection failed:', error);
    throw error;
  }
}

export function isConnected(): boolean {
  return connected;
}

