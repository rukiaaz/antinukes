import { Repent } from './structures/Repent';

const bot = new Repent();

process.on('unhandledRejection', (reason: unknown) => {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (message.includes('Unknown') || message.includes('Missing Access')) return;
  console.error('[Repent] Unhandled rejection:', message);
});

process.on('uncaughtException', (error: Error) => {
  console.error('[Repent] Uncaught exception:', error.message);
});

process.on('SIGINT', () => {
  console.log('[Repent] Shutting down...');
  bot.destroy();
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('[Repent] Shutting down...');
  bot.destroy();
  process.exit(0);
});

bot.start().catch((error: Error) => {
  console.error('[Repent] Failed to start:', error.message);
  process.exit(1);
});
