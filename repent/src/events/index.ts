import { Client, Events, DMChannel, NonThreadGuildBasedChannel, GuildMember, PartialGuildMember, TextChannel, NewsChannel, VoiceChannel, ForumChannel, MediaChannel } from 'discord.js';
import { Logger } from '../utils/Logger';
import { readyEvent } from './ready';
import { interactionCreateEvent } from './interactionCreate';
import { channelEvents } from './channelEvents';
import { roleEvents } from './roleEvents';
import { memberEvents } from './memberEvents';
import { webhookEvents } from './webhookEvents';
import { emojiEvents } from './emojiEvents';
import { guildEvents } from './guildEvents';

export async function registerEvents(client: Client): Promise<void> {
  const logger = Logger.getInstance();

  client.on(Events.ClientReady, () => readyEvent(client));
  client.on(Events.InteractionCreate, interactionCreateEvent);

  client.on(Events.ChannelCreate, (ch: DMChannel | NonThreadGuildBasedChannel) => {
    if ('guild' in ch) channelEvents.handleCreate(ch as any);
  });
  client.on(Events.ChannelDelete, (ch: DMChannel | NonThreadGuildBasedChannel) => {
    if ('guild' in ch) channelEvents.handleDelete(ch as any);
  });
  client.on(Events.ChannelUpdate, (oldCh: DMChannel | NonThreadGuildBasedChannel, newCh: DMChannel | NonThreadGuildBasedChannel) => {
    if ('guild' in newCh) channelEvents.handleUpdate(oldCh as any, newCh as any);
  });

  client.on(Events.GuildRoleCreate, roleEvents.handleCreate);
  client.on(Events.GuildRoleDelete, roleEvents.handleDelete);
  client.on(Events.GuildRoleUpdate, roleEvents.handleUpdate);

  client.on(Events.GuildBanAdd, memberEvents.handleBanAdd);
  client.on(Events.GuildMemberRemove, memberEvents.handleMemberRemove);
  client.on(Events.GuildMemberUpdate, (oldM: GuildMember | PartialGuildMember, newM: GuildMember) => {
    memberEvents.handleMemberUpdate(oldM as any, newM);
  });
  client.on(Events.GuildMemberAdd, memberEvents.handleMemberAdd);

  client.on(Events.WebhooksUpdate, (ch: TextChannel | NewsChannel | VoiceChannel | ForumChannel | MediaChannel) => {
    webhookEvents.handleWebhooksUpdate(ch as any);
  });

  client.on(Events.GuildEmojiCreate, emojiEvents.handleEmojiCreate);
  client.on(Events.GuildEmojiDelete, emojiEvents.handleEmojiDelete);
  client.on(Events.GuildEmojiUpdate, emojiEvents.handleEmojiUpdate);

  client.on(Events.GuildStickerCreate, emojiEvents.handleStickerCreate);
  client.on(Events.GuildStickerDelete, emojiEvents.handleStickerDelete);
  client.on(Events.GuildStickerUpdate, emojiEvents.handleStickerUpdate);

  client.on(Events.GuildUpdate, guildEvents.handleGuildUpdate);

  logger.info('Event handlers registered');
}
