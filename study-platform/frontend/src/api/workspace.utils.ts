import { apiClient } from './client';
import type { WsApiClient } from './ws/ws-client';
import type { CurrentUser } from './auth.types';

type WorkspaceEntrypointsResult = Awaited<
  ReturnType<WsApiClient['actions']['workspace']['entrypoints']>
>;
export type WorkspaceResource = WorkspaceEntrypointsResult['resources'][number];

/** The folder holding one personal folder per user. See isUsersContainer. */
export const USERS_CONTAINER_NAME = 'Пользователи';

/**
 * Per the backend team: `workspace.entrypoints` mixes real course-like
 * content (Кафедры / Учебные планы) with system containers that aren't
 * meant to be browsed as "courses" — `Пользователи` holds every student's
 * personal folder (auto-created per user) and shouldn't be listed here.
 * There's no structural flag for this on WorkspaceResourceOutput, so this
 * is a deliberate name-based exclusion, not a fragile guess.
 */
const HIDDEN_CONTAINER_NAMES = new Set([USERS_CONTAINER_NAME, 'Системное']);

/**
 * Confirmed against live data: an owner/root-level account's entrypoints
 * collapse to a single folder literally named "/" (the workspace root,
 * fixed id `00000000-0000-0000-0000-000000000010`) — its real children
 * (Кафедры, Учебные планы, ...) live one `folder.open` call deeper. Regular
 * (non-root) accounts aren't expected to see this.
 */
export const WORKSPACE_ROOT_NAME = '/';

/**
 * A shortcut is a folder pointing at another folder.
 *
 * `folder.shortcut.create({ parent_id, target_folder_id })` returns a
 * `FolderOutput` and `folder.shortcut.update` addresses it by `folder_id`, so
 * it must never be routed to as a page — `page.open` on a folder id answers
 * "Page not found". Where it leads arrives as `redirect_target_id` on
 * `folder.open`.
 *
 * `FolderChild.kind` is free-form, hence substring matching, same as
 * everywhere else that reads a kind.
 */
export function isShortcutKind(kind: string): boolean {
  return kind.toLowerCase().includes('shortcut');
}

/** Folders and shortcuts both drill down rather than opening as a page. */
export function isFolderLikeKind(kind: string): boolean {
  const k = kind.toLowerCase();
  return k.includes('folder') || k.includes('shortcut');
}

export function isHiddenContainer(resource: WorkspaceResource): boolean {
  return resource.resource_type === 'folder' && HIDDEN_CONTAINER_NAMES.has(resource.name.trim());
}

/**
 * The container every personal folder lives in — where account management
 * happens, and the only place the whole user list exists (system.users.search
 * refuses an empty query, so "everyone" is not otherwise enumerable).
 *
 * Matched on the name, like the exclusion above, because
 * WorkspaceResourceOutput carries no flag for it. Seeing this container at all
 * is what tells the nav that this account administers users: a student's
 * entrypoints contain their own personal folder, never its parent.
 */
export function isUsersContainer(resource: WorkspaceResource): boolean {
  return resource.resource_type === 'folder' && resource.name.trim() === USERS_CONTAINER_NAME;
}

export function isWorkspaceRoot(resource: WorkspaceResource): boolean {
  return resource.resource_type === 'folder' && resource.name.trim() === WORKSPACE_ROOT_NAME;
}

/**
 * Confirmed against live data: personal folders under `Пользователи` are
 * named by the owning user's id (a uuid), not their display name/username.
 */
export function isOwnPersonalFolder(
  resource: WorkspaceResource,
  user: CurrentUser | null,
): boolean {
  return resource.resource_type === 'folder' && !!user && resource.name.trim() === user.id;
}

export interface SplitWorkspaceResources {
  personalFolder: WorkspaceResource | null;
  folders: WorkspaceResource[];
  tests: WorkspaceResource[];
}

export function splitWorkspaceResources(
  resources: WorkspaceResource[],
  user: CurrentUser | null,
): SplitWorkspaceResources {
  const personalFolder = resources.find((resource) => isOwnPersonalFolder(resource, user)) ?? null;

  const folders = resources.filter(
    (resource) =>
      resource.resource_type === 'folder' &&
      !isHiddenContainer(resource) &&
      resource.resource_id !== personalFolder?.resource_id,
  );

  const tests = resources.filter((resource) => resource.resource_type === 'test');

  return { personalFolder, folders, tests };
}

/**
 * Everything the upload endpoint tells us about the stored file. These are
 * exactly the fields PageResourceOutput carries (minus `behavior`, which the
 * caller chooses), so a successful upload is enough to show the new file
 * immediately without waiting for the page to report it back.
 */
export interface UploadedFile {
  fileId: string;
  originalName: string;
  contentType: string;
  size: number;
  sha256: string;
}

/**
 * Uploads a file via the REST endpoint and attaches it to a page (or other
 * resource). Confirmed against the live API (the endpoint's response schema
 * is `additionalProperties: true` in OpenAPI, so it documents nothing): the
 * body comes back as `{ id, original_name, content_type, size, sha256 }` —
 * the uploaded file's id is `id`, *not* `file_id`, even though
 * PageResourceOutput calls the very same value `file_id` everywhere else in
 * this API. `file_id` is still accepted as a fallback in case the endpoint is
 * ever aligned with the rest; `null` when neither key is present, so callers
 * that need the id (inline image blocks) can show a clear error instead of
 * silently using a wrong value. The remaining fields fall back to what the
 * browser knows about the picked File if the server omits them.
 */
export async function uploadFile(params: {
  file: File;
  resourceType: 'page' | 'folder' | 'test';
  resourceId: string;
  behavior: 'download' | 'preview';
}): Promise<UploadedFile | null> {
  const form = new FormData();
  form.append('upload', params.file);
  form.append('resource_type', params.resourceType);
  form.append('resource_id', params.resourceId);
  form.append('behavior', params.behavior);
  // apiClient sets a default `Content-Type: application/json` header (see
  // client.ts). Axios's transformRequest checks that header *before* handling
  // FormData: if it looks like JSON, axios actually JSON.stringifies the
  // FormData (dropping the file bytes and the multipart boundary) instead of
  // sending it raw — that was the real cause of the 422 "field required"
  // errors (the server received no multipart body at all). Explicitly
  // clearing it here lets axios fall through to the FormData branch, which
  // sends the data untouched and lets the browser set the correct
  // multipart boundary itself.
  const response = await apiClient.post('/files/upload', form, {
    headers: { 'Content-Type': undefined },
  });
  const body: unknown = response.data;
  if (!body || typeof body !== 'object') return null;

  const raw = body as Record<string, unknown>;
  const fileId =
    typeof raw.id === 'string' ? raw.id : typeof raw.file_id === 'string' ? raw.file_id : null;
  if (fileId === null) return null;

  return {
    fileId,
    originalName: typeof raw.original_name === 'string' ? raw.original_name : params.file.name,
    contentType: typeof raw.content_type === 'string' ? raw.content_type : params.file.type,
    size: typeof raw.size === 'number' ? raw.size : params.file.size,
    sha256: typeof raw.sha256 === 'string' ? raw.sha256 : '',
  };
}
