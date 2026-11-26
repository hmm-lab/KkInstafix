import {PROVIDERS} from './config.js';
import {escapeHTML as h} from './links.js';
import {readBounded} from './security.js';
import {validSetting, validAppearance} from './store.js';

export const BACKUP_LIMIT = 65536;
const backupTables = {
  providers: ['provider_settings', "?, json_extract(value, '$[0]'), json_extract(value, '$[1]')"],
  platform_overrides: ['platform_overrides', "?, json_extract(value, '$[0]'), json_extract(value, '$[1]')"],
  muted_users: ['blocked_users', '?, value'],
  optout_users: ['optout_users', '?, value'],
  user_settings: ['user_settings', "json_extract(value, '$[0]'), ?, json_extract(value, '$[1]'), json_extract(value, '$[2]')"],
};
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const validUserId = id => Number.isSafeInteger(id) && id > 0;

export async function importBackup(msg, store, tg, reply, budget, updateId) {
  const receipt = await store.stmt('SELECT reply FROM backup_restore_receipts WHERE update_id=?', updateId).first();
  if (receipt) return reply(receipt.reply);
  const doc = msg.document ?? msg.reply_to_message?.document;
  if (!doc || doc.file_size > BACKUP_LIMIT) return reply('Send a JSON backup (up to 64 KiB) with caption /import, or reply to one with /import.');
  const file = await tg.call('getFile', {file_id: doc.file_id});
  const response = await tg.net(`https://api.telegram.org/file/bot${tg.token}/${file.file_path}`, {signal: AbortSignal.timeout(5000)});
  if (!response.ok) return reply('Telegram could not download the backup. Try again shortly.');
  let data;
  try {
    data = JSON.parse(new TextDecoder().decode(await readBounded(response.body, BACKUP_LIMIT)));
  } catch {
    return reply('Use a valid JSON backup up to 64 KiB.');
  }
  const chat = msg.chat.id;
  if (!isObject(data) || data.version !== 1 || data.chat_id !== chat) return reply('This backup must belong to the current chat.');
  for (const field of ['settings', 'providers', 'platform_overrides']) {
    if (Object.hasOwn(data, field) && !isObject(data[field])) return reply(`Invalid backup field: ${h(field)}.`);
  }
  for (const field of ['muted_users', 'optout_users', 'user_settings']) {
    if (Object.hasOwn(data, field) && !Array.isArray(data[field])) return reply(`Invalid backup field: ${h(field)}.`);
  }

  const retired = {instagram:['ez','kkclip','kk'],facebook:['ez'],pinterest:['vx'],
    tiktok:['vx','tik','tfx','proxitok'],reddit:['libredd'],bluesky:['vx','cbsky'],spotify:['fix']};
  let migrated = false;
  const rows = {providers: [], platform_overrides: [], muted_users: [], optout_users: [], user_settings: []};
  const settings = Object.entries(data.settings ?? {}).filter(([key]) => key !== 'chat_id');
  for (const [key, value] of settings) {
    if (!validSetting(key, value)) return reply(`Invalid setting: ${h(key)}`);
  }
  for (const [platform, key] of Object.entries(data.providers ?? {})) {
    if (platform === 'linkedin' && ['vx', 'ez'].includes(key)) { migrated = true; continue; }
    if (!Object.hasOwn(PROVIDERS, platform)) return reply('Invalid provider in backup.');
    const config = PROVIDERS[platform];
    if (typeof key === 'string' && Object.hasOwn(config.options, key)) {
      rows.providers.push([platform, key]);
    } else if (Object.hasOwn(retired, platform) && retired[platform].includes(key)) {
      rows.providers.push([platform, config.default]);
      migrated = true;
    } else {
      return reply('Invalid provider in backup.');
    }
  }
  for (const [platform, value] of Object.entries(data.platform_overrides ?? {})) {
    if (platform === 'linkedin' && [0, 1].includes(value)) { migrated = true; continue; }
    if (!Object.hasOwn(PROVIDERS, platform) || ![0, 1].includes(value)) return reply('Invalid platform override in backup.');
    rows.platform_overrides.push([platform, value]);
  }
  for (const field of ['muted_users', 'optout_users']) {
    const ids = data[field] ?? [];
    if (!ids.every(validUserId)) return reply('Invalid user ID in backup.');
    rows[field] = [...new Set(ids)];
  }
  for (const row of data.user_settings ?? []) {
    if (!isObject(row) || !validUserId(row.user_id) || typeof row.key !== 'string' || (row.chat_id !== undefined && row.chat_id !== chat) ||
        !['number', 'string'].includes(typeof row.value)) return reply('Invalid user setting in backup.');
    const value = ['sender_mode', 'caption_style', 'preview_size'].includes(row.key) ? row.value : Number(row.value);
    if (!validSetting(row.key, value) && !validAppearance(row.key, value)) return reply('Invalid user setting in backup.');
    rows.user_settings.push([row.user_id, row.key, String(value)]);
  }

  const fields = Object.keys(backupTables);
  const complete = Object.hasOwn(data, 'settings') && fields.every(field => Object.hasOwn(data, field));
  if (budget) {
    // Count deletes as well as inserts. Reserve room for index writes and delivery bookkeeping.
    let current = 0;
    if (complete) {
      const counts = fields.map(field => `(SELECT COUNT(*) FROM ${backupTables[field][0]} WHERE chat_id=?)`);
      current = (await store.stmt(`SELECT ${counts.join('+')} AS total`, ...fields.map(() => chat)).first()).total;
    }
    const incoming = Object.values(rows).reduce((sum, entries) => sum + entries.length, settings.length);
    const estimated = 6 * (current + incoming) + 24;
    if (estimated > budget.limits.rowsWritten) return reply('This backup exceeds the safe restore size.');
    if (!await store.db.reserveWrites(estimated)) {
      return reply('The bot has insufficient database write allowance for this restore today. Try again after midnight UTC.');
    }
  }

  const statements = [];
  if (settings.length) {
    const columns = settings.map(([key]) => key);
    const values = settings.map(([,value]) => value);
    const changes = columns.map(key => `${key}=excluded.${key}`).join(',');
    statements.push(store.stmt(
      `INSERT INTO chat_settings(chat_id,${columns.join(',')}) VALUES(?,${values.map(() => '?').join(',')})
       ON CONFLICT(chat_id) DO UPDATE SET ${changes}`, chat, ...values));
  }
  // Validate the whole file first, then apply it atomically with a fixed number of SQL statements.
  for (const field of fields) {
    const [table, projection] = backupTables[field];
    if (complete) statements.push(store.stmt(`DELETE FROM ${table} WHERE chat_id=?`, chat));
    if (rows[field].length) {
      statements.push(store.stmt(`INSERT OR REPLACE INTO ${table} SELECT ${projection} FROM json_each(?)`,
        chat, JSON.stringify(rows[field])));
    }
  }
  const confirmation = '✅ Settings restored.' + (complete ? '' : ' Partial backup merged with existing settings.') +
    (migrated ? ' Retired providers were replaced with current defaults; removed platforms were skipped.' : '');
  statements.unshift(store.stmt('INSERT INTO backup_restore_receipts VALUES(?,?,?)', updateId, confirmation, Math.floor(Date.now()/1000)));
  await store.db.batch(statements);
  return reply(confirmation);
}
