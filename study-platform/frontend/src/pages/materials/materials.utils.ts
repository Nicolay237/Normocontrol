// Helpers for mapping real WS/REST data onto the materials page's existing,
// design-driven component props. See the block-renderer component for the
// biggest, most speculative piece of this mapping (block_type -> component).
import { apiClient } from '@/api/client';
import { isFolderLikeKind, isShortcutKind } from '@/api/workspace.utils';
import type { UploadedFile } from '@/api/workspace.utils';
import type { RichTextContent, RichTextRun } from './components/rich-text';
import type { SidebarItemIcon } from './components/sidebar-item';
import type { LectureTableRow } from './components/lecture-table';
import type { BlockData, FolderChildData, PageResourceData } from './materials.types';

// ---------------------------------------------------------------------------
// Narrow runtime guards over `unknown` — used both here and by the block
// renderer to defensively read fields off opaque `data`/`kind` values before
// trusting them.
// ---------------------------------------------------------------------------

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function isString(value: unknown): value is string {
  return typeof value === 'string';
}

/** Best-guess reader for a structured rich-text runs array (`{ text, as? }[]`). */
export function asRichRuns(value: unknown): RichTextContent | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const runs: RichTextRun[] = [];
  for (const item of value) {
    if (!isRecord(item) || !isString(item.text)) return null;
    const as = item.as;
    if (as !== undefined && as !== 'strong' && as !== 'em' && as !== 'code') return null;
    runs.push(as ? { text: item.text, as } : { text: item.text });
  }
  return runs;
}

/** Best-guess reader for a plain text field (`text` or `content` as a string). */
export function asPlainText(data: unknown): string | null {
  if (!isRecord(data)) return null;
  if (isString(data.text)) return data.text;
  if (isString(data.content)) return data.content;
  return null;
}

/** Best-guess reader for a heading-ish block (`title` or `text` string). */
export function asHeadingText(data: unknown): string | null {
  if (!isRecord(data)) return null;
  if (isString(data.title)) return data.title;
  if (isString(data.text)) return data.text;
  return null;
}

// ---------------------------------------------------------------------------
// order_key sorting — treated as an opaque, lexicographically-sortable
// fractional-index string (a common backend pattern for this field name).
// ---------------------------------------------------------------------------

export function compareOrderKey(a: { order_key: string }, b: { order_key: string }): number {
  if (a.order_key === b.order_key) return 0;
  return a.order_key < b.order_key ? -1 : 1;
}

export function sortByOrderKey<T extends { order_key: string }>(items: T[]): T[] {
  return [...items].sort(compareOrderKey);
}

// ---------------------------------------------------------------------------
// order_key generation. There's no real block data yet to confirm the
// backend's actual format (see the note above), and we're the only ones
// minting order_keys going forward (new blocks, moves/reorders) — so this
// implements a standard base-36 fractional-indexing scheme: given any two
// neighboring keys, it finds a key that sorts strictly between them by
// comparing digit-by-digit and only extending precision (adding another
// character) once two keys are adjacent at every digit compared so far.
// Ключи пишет только эта функция, поэтому вырожденная пара — два ключа,
// обозначающих одно место при разной длине («i» и «i0»), — сама по себе не
// возникает. Но прийти она может извне: одинаковые ключи у двух блоков уже
// приезжали из базы после починки данных. Полагаться на «такого не бывает»
// нельзя, поэтому случай разобран явно ниже — зациклиться функция не умеет.
// ---------------------------------------------------------------------------

/*
 * Цифры ключа порядка — 0-9, A-Z, a-z, именно в этом порядке.
 *
 * Заглавные добавлены не для ёмкости, а потому что сервер их уже пишет: блок,
 * созданный через `page.block.create` без явного ключа, получает «U», «UU»,
 * «UUU» (см. pages/service.py). Пока алфавит был только строчным, `indexOf`
 * возвращал на «U» минус единицу, `ORDER_KEY_DIGITS[-1]` давало `undefined`,
 * и оно попадало прямо в ключ — в базе оседали строки вида
 * «undefinedundefined0i», а блок уезжал в конец страницы.
 *
 * Порядок символов совпадает с их порядком в кодировке ('0' < 'A' < 'a'),
 * поэтому обычное сравнение строк, которым сортируются блоки, остаётся верным
 * и для старых ключей.
 */
const ORDER_KEY_DIGITS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
const ORDER_KEY_BASE = ORDER_KEY_DIGITS.length;

function orderKeyDigitAt(key: string, index: number): number {
  if (index >= key.length) return 0;
  const digit = ORDER_KEY_DIGITS.indexOf(key[index]);
  // Символ не из алфавита — считаем его нулём. Раньше сюда возвращалось −1, и
  // индексация строки минус первым символом молча давала `undefined`, который
  // дописывался в ключ как есть.
  return digit === -1 ? 0 : digit;
}

/** An order_key that sorts strictly between `lower` and `upper` — omit either bound for "start of list" / "end of list". */
export function orderKeyBetween(lower?: string, upper?: string): string {
  let hi = upper;
  let result = '';
  let index = 0;
  for (;;) {
    /*
     * Верхняя граница кончилась, а разойтись с нижней так и не удалось —
     * значит ключа строго между ними не существует. Так бывает у двух
     * одинаковых ключей и у пары вида «i» и «i0»: они обозначают одно и то же
     * место. Дальше углубляться бессмысленно, и именно здесь функция раньше
     * крутилась вечно — синхронно, в обработчике клавиши, то есть вкладка
     * вставала намертво.
     *
     * Ответа «строго между» тут нет ни у кого, поэтому берём ближайший
     * осмысленный: сразу после нижней границы. Для автора это и есть «новый
     * блок под этим», а порядок остаётся определённым.
     */
    if (hi !== undefined && index >= hi.length) hi = undefined;
    const loDigit = orderKeyDigitAt(lower ?? '', index);
    const hiDigit = hi === undefined ? ORDER_KEY_BASE : orderKeyDigitAt(hi, index);
    if (hiDigit - loDigit > 1) {
      const mid = loDigit + Math.floor((hiDigit - loDigit) / 2);
      return result + ORDER_KEY_DIGITS[mid];
    }
    result += ORDER_KEY_DIGITS[loDigit];
    // Adjacent digits: committing loDigit already puts us strictly below
    // upper, so upper stops constraining anything deeper than this position.
    if (hiDigit - loDigit === 1) hi = undefined;
    index += 1;
  }
}

/** order_key for a new block appended at the end of a (possibly empty) list. */
export function nextOrderKey(existingBlocks: { order_key: string }[]): string {
  if (existingBlocks.length === 0) return orderKeyBetween();
  const sorted = sortByOrderKey(existingBlocks);
  return orderKeyBetween(sorted[sorted.length - 1].order_key);
}

/** order_key that swaps a block with its previous/next sibling — null if it's already at that edge. `sortedBlocks` must already be in order_key order. */
export function orderKeyForMove<T extends { id: string; order_key: string }>(
  sortedBlocks: T[],
  blockId: string,
  direction: 'up' | 'down',
): string | null {
  const index = sortedBlocks.findIndex((block) => block.id === blockId);
  if (index === -1) return null;
  const targetIndex = direction === 'up' ? index - 1 : index + 1;
  if (targetIndex < 0 || targetIndex >= sortedBlocks.length) return null;

  if (direction === 'up') {
    const before = sortedBlocks[targetIndex - 1];
    const after = sortedBlocks[targetIndex];
    return orderKeyBetween(before?.order_key, after.order_key);
  }
  const before = sortedBlocks[targetIndex];
  const after = sortedBlocks[targetIndex + 1];
  return orderKeyBetween(before.order_key, after?.order_key);
}

// ---------------------------------------------------------------------------
// FolderChild.kind -> sidebar icon / navigation guesses.
//
// `kind` is documented only as a free-form `string`; there's no enum of real
// values in the schema. We treat anything that looks like a folder/test/video
// by substring match and fall back to a generic "document" icon + treat it as
// a page link otherwise. This is intentionally permissive so unknown kinds
// degrade to a sane default instead of being skipped or crashing.
// ---------------------------------------------------------------------------

/**
 * Re-exported so the whole app classifies a kind the same way.
 *
 * These live in the API layer because the dashboard's course walk needs them
 * too, and a shortcut mis-read as a page 404s identically wherever it happens
 * — see `useFolderRedirect` for how a shortcut is actually followed.
 */
export { isFolderLikeKind, isShortcutKind };

/**
 * A test is its own resource type — `page.open` cannot read one.
 *
 * Folder-like kinds win: a container named e.g. `test_folder` is a folder, not
 * a test, and must keep drilling down rather than routing to the test screens.
 */
export function isTestKind(kind: string): boolean {
  return !isFolderLikeKind(kind) && kind.toLowerCase().includes('test');
}

/**
 * Icon for a row's `kind`.
 *
 * `FolderChild.kind` is a free-form string, but `page.create` documents
 * document/lecture/resource, and folders and tests arrive as their own kinds.
 * Substring matching rather than equality keeps this working for whatever the
 * backend prefixes or pluralises, and anything unrecognised stays a plain
 * document rather than rendering nothing.
 */
export function childIconForKind(kind: string, iconName?: string | null): SidebarItemIcon {
  // Notes are a `document` like any other as far as the server is concerned;
  // only the marker in `icon_name` tells them apart.
  if (notesLecturePageId(iconName)) return 'notes';
  const k = kind.toLowerCase();
  if (k.includes('shortcut')) return 'folder';
  if (k.includes('folder')) return 'folder';
  if (k.includes('test')) return 'test';
  if (k.includes('video')) return 'video';
  if (k.includes('lecture')) return 'lecture';
  if (k.includes('resource')) return 'resource';
  return 'document';
}

/** Human label for a sidebar row's `kind` — FolderChild's `kind` is a free-form string, not shown to the user verbatim. */
export function childKindLabel(kind: string, iconName?: string | null): string {
  if (notesLecturePageId(iconName)) return 'Заметки';
  const k = kind.toLowerCase();
  if (k.includes('shortcut')) return 'Ярлык';
  if (k.includes('folder')) return 'Раздел';
  if (k.includes('test')) return 'Тест';
  if (k.includes('lecture')) return 'Лекция';
  if (k.includes('resource')) return 'Материал';
  if (k.includes('document')) return 'Документ';
  if (k.includes('video')) return 'Видео';
  return 'Материал';
}

/** The workspace root folder's real `name` is literally "/" — show something readable instead. */
export function displayFolderName(name: string): string {
  return name === '/' || name.trim() === '' ? 'Материалы' : name;
}

/**
 * Where a sidebar row should link — folders drill down by folder_id,
 * everything else opens as a page in the current folder.
 *
 * Takes only the two fields it reads rather than a whole `FolderChild`, so
 * callers that hold a narrower record (the context menu's target, which
 * carries no `order_key`) can use it without inventing the missing ones.
 */
export function childHref(
  currentFolderId: string,
  child: Pick<FolderChildData, 'id' | 'kind'>,
  canEdit = false,
): string {
  if (isFolderLikeKind(child.kind)) return `/materials/${child.id}`;
  // Tests live outside the page routes entirely: opening one as a page calls
  // `page.open` with a test id and comes back "Page not found". Which test
  // screen depends on the viewer — the builder is an editor's tool, while a
  // student needs the attempt, which is started from the test's own page.
  if (isTestKind(child.kind)) {
    return canEdit ? `/tests/${child.id}/edit` : `/tests/${child.id}/start`;
  }
  return `/materials/${currentFolderId}/${child.id}`;
}

/** PageOutput.kind isn't a strict enum in PageOutput itself, but PageCreateInput documents "document"|"lecture"|"resource" as the intended values — used here just as a display label, defaulting gracefully for anything else. */
export function pageKindLabel(kind: string): string {
  switch (kind) {
    case 'lecture':
      return 'Лекция';
    case 'document':
      return 'Документ';
    case 'resource':
      return 'Материал';
    case 'lab':
      return 'Лабораторная';
    default:
      return 'Материал';
  }
}

// ---------------------------------------------------------------------------
// PageResourceOutput -> file list / download wiring.
// ---------------------------------------------------------------------------

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  const units = ['Б', 'КБ', 'МБ', 'ГБ'];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const formatted = unitIndex === 0 ? String(Math.round(value)) : value.toFixed(1);
  return `${formatted} ${units[unitIndex]}`;
}

/**
 * REST download URL, built from the file_id per the documented
 * `GET /files/{file_id}/download` endpoint — routed through apiClient's
 * baseURL so the dev proxy (see vite.config.ts) still applies.
 */
export function buildFileDownloadUrl(fileId: string): string {
  const base = apiClient.defaults.baseURL ?? '';
  return `${base}/files/${fileId}/download`;
}

/**
 * The download endpoint is Bearer-authed (token lives in localStorage, not a
 * cookie — see src/api/token-storage.ts), so a plain `<a href>`/`<img src>`
 * would not carry the Authorization header and would 401. We fetch the file
 * as a blob through `apiClient` (which attaches the header via its request
 * interceptor) and hand back an object URL instead.
 */
export async function fetchFileObjectUrl(fileId: string): Promise<string> {
  const response = await apiClient.get<Blob>(`/files/${fileId}/download`, {
    responseType: 'blob',
  });
  return URL.createObjectURL(response.data);
}

export async function fetchResourceObjectUrl(resource: PageResourceData): Promise<string> {
  return fetchFileObjectUrl(resource.file_id);
}

/**
 * Saves a file to disk by id. The plain REST href is still set on the link as
 * a visible/copyable URL — this is what actually makes the click work (see
 * fetchFileObjectUrl for why a bare href would 401).
 */
export async function downloadFileById(fileId: string, fileName: string): Promise<void> {
  const blobUrl = await fetchFileObjectUrl(fileId);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}

/** Same, for a server-reported resource — `behavior: 'preview'` opens in a tab instead of downloading. */
export async function openResourceFile(resource: PageResourceData): Promise<void> {
  if (resource.behavior === 'preview') {
    const blobUrl = await fetchResourceObjectUrl(resource);
    window.open(blobUrl, '_blank', 'noopener,noreferrer');
    return;
  }
  await downloadFileById(resource.file_id, resource.original_name);
}

/**
 * Turns a completed upload into a PageResourceOutput-shaped entry. Every
 * field comes from the upload endpoint's own response (see UploadedFile), so
 * this fabricates nothing — it just lets the UI show a file the moment it
 * lands, instead of depending on page.open reporting it back.
 */
export function pageResourceFromUpload(
  uploaded: UploadedFile,
  behavior: PageResourceData['behavior'],
): PageResourceData {
  return {
    file_id: uploaded.fileId,
    original_name: uploaded.originalName,
    content_type: uploaded.contentType,
    size: uploaded.size,
    sha256: uploaded.sha256,
    behavior,
  };
}

/**
 * Marker stored in PageOutput.icon_name to remember which uploaded file is
 * the page banner.
 *
 * The obvious home would be the resource's `behavior: 'preview'` flag — but
 * `page.open`'s `resources` is only populated for pages of `kind: "resource"`
 * (see materials.attachments.ts), and a lecture is not one, so nothing
 * uploaded to it can ever be recovered from that field. `icon_name` is a plain
 * string on the page itself that goes through the documented page.update
 * action, so it persists. The prefix keeps the value self-describing: anything
 * not starting with it is treated as a genuine icon name and left alone.
 */
/**
 * Marker stored in `icon_name` identifying a page as private notes, and
 * recording which lecture they belong to.
 *
 * The pairing lived in the page's `name` at first — `«Заметки: <uuid>»` — which
 * had two faults. It showed the reader a raw uuid in their own folder, and
 * renaming the page (an ordinary thing to do to your own document, offered by
 * the row's context menu) silently orphaned the notes: the name *was* the
 * index, so the next visit found nothing and started a fresh empty page.
 *
 * `icon_name` is a free-form string the UI never displays and no dialog edits,
 * which makes it the right place for a machine link. Same trick the page
 * banner already uses — see BANNER_ICON_PREFIX below.
 */
export const NOTES_ICON_PREFIX = 'notes:';

export function notesIconValue(lecturePageId: string): string {
  return `${NOTES_ICON_PREFIX}${lecturePageId}`;
}

/** The lecture these notes annotate, or null when `icon_name` says otherwise. */
export function notesLecturePageId(iconName: string | null | undefined): string | null {
  if (!iconName || !iconName.startsWith(NOTES_ICON_PREFIX)) return null;
  const pageId = iconName.slice(NOTES_ICON_PREFIX.length);
  return pageId.length > 0 ? pageId : null;
}

export const BANNER_ICON_PREFIX = 'banner:';

export function bannerIconValue(fileId: string): string {
  return `${BANNER_ICON_PREFIX}${fileId}`;
}

/** The banner file id recorded on the page, or null when `icon_name` holds something else (or nothing). */
export function bannerFileIdFromIconName(iconName: string | null | undefined): string | null {
  if (!iconName || !iconName.startsWith(BANNER_ICON_PREFIX)) return null;
  const fileId = iconName.slice(BANNER_ICON_PREFIX.length);
  return fileId.length > 0 ? fileId : null;
}

/**
 * Legacy fallback for pages whose banner predates the icon_name marker: the
 * most recently attached `behavior: 'preview'` image resource.
 *
 * It only ever matches on a `kind: "resource"` page, since that is the only
 * kind whose `page.open` reports `resources` at all. Kept because it costs
 * nothing and still covers that case; bannerFileIdFromIconName is what finds
 * a lecture's banner.
 */
export function findBannerResource(
  resources: PageResourceData[] | undefined,
): PageResourceData | null {
  if (!resources) return null;
  const images = resources.filter(
    (resource) => resource.behavior === 'preview' && resource.content_type.startsWith('image/'),
  );
  return images.length > 0 ? images[images.length - 1] : null;
}

// ---------------------------------------------------------------------------
// Table block guesses — see block-renderer for how these are used.
// ---------------------------------------------------------------------------

/** Narrow match for the exact (domain-specific) LectureTableRow shape this page's design uses. */
export function asLectureTableData(
  data: unknown,
): { headers: string[]; rows: LectureTableRow[] } | null {
  if (!isRecord(data)) return null;
  if (!Array.isArray(data.headers) || !data.headers.every(isString)) return null;
  if (!Array.isArray(data.rows)) return null;

  const rows: LectureTableRow[] = [];
  for (const [index, row] of data.rows.entries()) {
    if (!isRecord(row)) return null;
    const { form, requirement, eliminates, status } = row;
    if (!isString(form) || !isString(requirement) || !isString(eliminates) || !isString(status)) {
      return null;
    }
    rows.push({
      id: isString(row.id) ? row.id : `row-${index}`,
      form,
      requirement,
      eliminates,
      status,
    });
  }
  return { headers: data.headers, rows };
}

/** Looser generic table match: string headers + rows of string/number cells. */
export function asGenericTableData(
  data: unknown,
): { headers: string[]; rows: Array<Array<string | number>> } | null {
  if (!isRecord(data)) return null;
  if (!Array.isArray(data.headers) || !data.headers.every(isString)) return null;
  if (!Array.isArray(data.rows)) return null;

  const rows: Array<Array<string | number>> = [];
  for (const row of data.rows) {
    if (!Array.isArray(row)) return null;
    if (!row.every((cell) => isString(cell) || typeof cell === 'number')) return null;
    rows.push(row as Array<string | number>);
  }
  return { headers: data.headers, rows };
}

// ---------------------------------------------------------------------------
// Heading-block helpers shared by the block renderer (component -> markup)
// and the page component (building the TOC sidebar from the same blocks).
// Kept here rather than in block-renderer.component.tsx so that file only
// exports the component itself (better for fast-refresh / lint).
// ---------------------------------------------------------------------------

const HEADING_BLOCK_TYPES = new Set([
  'heading',
  'title',
  'section_heading',
  'heading_1',
  'heading_2',
  'heading_3',
]);

export function isHeadingBlockType(blockType: string): boolean {
  return HEADING_BLOCK_TYPES.has(blockType);
}

/** Stable DOM anchor id for a block, used by both the block renderer (sets it) and the auto-generated TOC (links to it). */
export function blockAnchorId(blockId: string): string {
  return `materials-block-${blockId}`;
}

/** Text of a block, if it's one of our guessed heading types with valid data — used to build the TOC from real block content instead of fabricating entries. */
export function blockHeadingText(block: BlockData): string | null {
  if (!isHeadingBlockType(block.block_type)) return null;
  return asHeadingText(block.data);
}

// ---------------------------------------------------------------------------
// Misc
// ---------------------------------------------------------------------------

export function describeWsError(error: unknown): string {
  if (!(error instanceof Error) || !error.message) return 'Неизвестная ошибка соединения.';

  /*
   * A server-side failure is not the reader's fault and "Internal server
   * error" alone gives them nothing to do about it. The action name and the
   * trace id are what makes the failure reportable — both ride along on the
   * error (see src/api/ws/ws-client.ts).
   */
  const details = error as Error & { code?: string; traceId?: string | null; action?: string };
  if (details.code === 'internal_error' || error.message === 'Internal server error') {
    const where = details.action ? ` (${details.action})` : '';
    const trace = details.traceId ? ` Код для поддержки: ${details.traceId}.` : '';
    return `Ошибка на сервере${where}. Попробуйте ещё раз.${trace}`;
  }

  // Бюджет действий сессии. Клиент уже повторил вызов несколько раз (см.
  // ws-client.ts), так что сюда это доходит, только когда ждать действительно
  // придётся, — и сообщение должно говорить, что делать, а не цитировать
  // английский текст сервера.
  if (/rate limit/i.test(error.message)) {
    return 'Слишком много действий подряд. Подождите полминуты и повторите.';
  }

  return error.message;
}
