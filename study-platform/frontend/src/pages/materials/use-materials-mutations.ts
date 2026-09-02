import { useQueryClient } from '@tanstack/react-query';
import { useWsMutation } from '@/app/ws';
import type { WsApiClient } from '@/api/ws/ws-client';
import { forgetExpanded } from './use-tree-mode';
import { rememberDeletedResource } from './deleted-resources.store';
import { nextOrderKey } from './materials.utils';
import { cancelPageRefresh, refreshPage } from './page-refresh';
import {
  addBlock,
  dropBlock,
  holdPageReads,
  pageSnapshot,
  patchBlocks,
  replaceBlock,
  restorePage,
} from './page-blocks.cache';
import type { SubtreeContents } from './folder-subtree';
import type { BlockData, PageOpenResult } from './materials.types';

// ---------------------------------------------------------------------------
// Folders
// ---------------------------------------------------------------------------

export function useCreateFolder() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { parentId: string; name: string }) =>
      client.actions.folder.create({ parent_id: vars.parentId, name: vars.name }),
    {
      onSuccess: (_data, vars) => {
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.parentId],
        });
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'entrypoints'] });
      },
    },
  );
}

export function useRenameFolder() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { folderId: string; name: string }) =>
      client.actions.folder.update({ folder_id: vars.folderId, name: vars.name }),
    {
      onSuccess: (_data, vars) => {
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.folderId],
        });
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'entrypoints'] });
      },
    },
  );
}

/**
 * Deletes a folder and drops everything the server took with it.
 *
 * `folder.delete` is recursive: the pages, tests and subfolders inside go too.
 * Invalidating the parent alone — which is all this used to do — left every
 * descendant sitting in the cache still marked fresh, so a bookmark or a back
 * button would happily re-open a lecture that no longer exists. The subtree is
 * therefore *removed*, not invalidated: invalidation keeps the data and merely
 * schedules a refetch, which is the opposite of what a deleted resource needs.
 *
 * `contents` comes from collectSubtree (see folder-subtree.ts) and is best
 * effort — a branch the user never opened isn't in the cache to be evicted,
 * but it isn't in the cache to be served either, so nothing stale survives.
 */
export function useDeleteFolder() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (
      client,
      vars: { folderId: string; name: string; parentId?: string; contents?: SubtreeContents },
    ) => client.actions.folder.delete({ folder_id: vars.folderId }),
    {
      onSuccess: (_data, vars) => {
        const { folderIds = [], pageIds = [], testIds = [] } = vars.contents ?? {};
        const goneFolders = [vars.folderId, ...folderIds];

        for (const folderId of goneFolders) {
          queryClient.removeQueries({ queryKey: ['materials', 'folder.open', folderId] });
        }
        for (const pageId of pageIds) {
          queryClient.removeQueries({ queryKey: ['materials', 'page.open', pageId] });
          queryClient.removeQueries({ queryKey: ['materials', 'page.revisions', pageId] });
        }
        for (const testId of testIds) {
          queryClient.removeQueries({ queryKey: ['materials', 'test.open', testId] });
        }

        // A remembered branch pointing at a deleted folder would re-open on the
        // next visit and render as "Не удалось открыть" forever.
        forgetExpanded(goneFolders);

        // There is no trash-browsing action in the API, so the id is the only
        // way back — and `folder.restore` needs it. Tests inside are gone for
        // good either way (no `test.restore`), which the confirm text says.
        rememberDeletedResource({
          kind: 'folder',
          resourceId: vars.folderId,
          parentId: vars.parentId ?? null,
          name: vars.name,
          deletedAt: Date.now(),
        });

        if (vars.parentId) {
          void queryClient.invalidateQueries({
            queryKey: ['materials', 'folder.open', vars.parentId],
          });
        }
        // Pins may point into the subtree that just went away.
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'pinned'] });
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'entrypoints'] });
      },
    },
  );
}

/** Restores a soft-deleted folder. Its pages come back with it; tests do not exist to come back. */
export function useRestoreFolder() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { folderId: string; parentId?: string | null }) =>
      client.actions.folder.restore({ folder_id: vars.folderId }),
    {
      onSuccess: (_data, vars) => {
        if (vars.parentId) {
          void queryClient.invalidateQueries({
            queryKey: ['materials', 'folder.open', vars.parentId],
          });
        }
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'entrypoints'] });
      },
    },
  );
}

/**
 * Moves a folder under a different parent.
 *
 * `folder.move` needs rights on *both* sides (docs/actions.md), so a refusal
 * here usually means the target, not the folder being moved — the dialog says
 * so rather than showing the raw message alone.
 *
 * `order_key` is left out on purpose: without it the folder lands at the end of
 * the target, which is the only placement that cannot collide with an existing
 * sibling's key. Reordering afterwards is `folder.update`'s job.
 *
 * Both parents are invalidated: the folder left one child list and joined
 * another, and the tree renders from whichever branches are expanded.
 */
export function useMoveFolder() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { folderId: string; fromParentId: string | null; toParentId: string }) =>
      client.actions.folder.move({ folder_id: vars.folderId, parent_id: vars.toParentId }),
    {
      onSuccess: (_data, vars) => {
        for (const parentId of [vars.fromParentId, vars.toParentId]) {
          if (!parentId) continue;
          void queryClient.invalidateQueries({
            queryKey: ['materials', 'folder.open', parentId],
          });
        }
        // The folder's own breadcrumbs changed with its parent.
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.folderId],
        });
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'entrypoints'] });
      },
    },
  );
}

// ---------------------------------------------------------------------------
// Shortcuts
//
// A shortcut is a real folder that carries a `target_folder_id` and redirects
// when opened (see use-folder-redirect.ts). The app could follow one but never
// create one, so a section could not be surfaced in a second place without
// copying it.
// ---------------------------------------------------------------------------

export function useCreateFolderShortcut() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { parentId: string; targetFolderId: string; name: string }) =>
      client.actions.folder.shortcut.create({
        parent_id: vars.parentId,
        target_folder_id: vars.targetFolderId,
        name: vars.name,
      }),
    {
      onSuccess: (_data, vars) => {
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.parentId],
        });
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'entrypoints'] });
      },
    },
  );
}

/** `folder_id` addresses the shortcut itself, never the folder it points at. */
export function useUpdateFolderShortcut() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (
      client,
      vars: {
        shortcutId: string;
        parentId: string;
        name?: string;
        targetFolderId?: string;
      },
    ) =>
      client.actions.folder.shortcut.update({
        folder_id: vars.shortcutId,
        ...(vars.name !== undefined ? { name: vars.name } : {}),
        ...(vars.targetFolderId !== undefined ? { target_folder_id: vars.targetFolderId } : {}),
      }),
    {
      onSuccess: (_data, vars) => {
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.parentId],
        });
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.shortcutId],
        });
      },
    },
  );
}

/**
 * Removes the signpost, never the destination.
 *
 * This is the whole reason it is a separate action from `folder.delete`: the
 * target folder keeps existing, so the confirmation must not warn about losing
 * contents the way a real folder deletion does.
 */
export function useDeleteFolderShortcut() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { shortcutId: string; parentId: string }) =>
      client.actions.folder.shortcut.delete({ folder_id: vars.shortcutId }),
    {
      onSuccess: (_data, vars) => {
        queryClient.removeQueries({
          queryKey: ['materials', 'folder.open', vars.shortcutId],
        });
        forgetExpanded([vars.shortcutId]);
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.parentId],
        });
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'entrypoints'] });
      },
    },
  );
}

// ---------------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------------

export type PageKind = 'document' | 'lecture' | 'resource' | 'lab' | 'normocontrol';

export function useCreatePage() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { folderId: string; name: string; kind: PageKind }) =>
      client.actions.page.create({ folder_id: vars.folderId, name: vars.name, kind: vars.kind }),
    {
      onSuccess: (_data, vars) => {
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.folderId],
        });
      },
    },
  );
}

export function useRenamePage() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { pageId: string; folderId: string; name: string }) =>
      client.actions.page.update({ page_id: vars.pageId, name: vars.name }),
    {
      onSuccess: (_data, vars) => {
        refreshPage(queryClient, vars.pageId);
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.folderId],
        });
      },
    },
  );
}

export function useDeletePage() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { pageId: string; folderId: string; name: string }) =>
      client.actions.page.delete({ page_id: vars.pageId }),
    {
      onSuccess: (_data, vars) => {
        // Soft, like a folder's — and just as un-browsable afterwards, so the
        // id is kept for the undo bar. See deleted-resources.store.ts.
        cancelPageRefresh(vars.pageId);
        queryClient.removeQueries({ queryKey: ['materials', 'page.open', vars.pageId] });
        rememberDeletedResource({
          kind: 'page',
          resourceId: vars.pageId,
          parentId: vars.folderId,
          name: vars.name,
          deletedAt: Date.now(),
        });
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.folderId],
        });
        void queryClient.invalidateQueries({ queryKey: ['workspace', 'pinned'] });
      },
    },
  );
}

/**
 * Restores a soft-deleted page.
 *
 * Rights are checked against the *parent folder*, not the page (docs/actions.md),
 * so this can succeed for someone who could no longer open the page itself —
 * and it fails outright if the folder around it went too, which is why the
 * folder undo is offered first when both are pending.
 */
export function useRestorePage() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { pageId: string; folderId: string | null }) =>
      client.actions.page.restore({ page_id: vars.pageId }),
    {
      onSuccess: (_data, vars) => {
        if (vars.folderId) {
          void queryClient.invalidateQueries({
            queryKey: ['materials', 'folder.open', vars.folderId],
          });
        }
        refreshPage(queryClient, vars.pageId);
      },
    },
  );
}

/** Records which uploaded file is the page banner — see BANNER_ICON_PREFIX in materials.utils.ts for why it lives in `icon_name`. */
export function useSetPageBanner() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { pageId: string; iconName: string }) =>
      client.actions.page.update({ page_id: vars.pageId, icon_name: vars.iconName }),
    {
      onSuccess: (_data, vars) => {
        refreshPage(queryClient, vars.pageId);
      },
    },
  );
}

/**
 * Publishing and unpublishing are two different actions, not two sides of a
 * toggle.
 *
 * `page.publish` works on an already-published page — it compiles a fresh
 * revision and moves the pointer to it (verified against the live API). The
 * old toggle hid that: once published, the only button on offer said "снять с
 * публикации", so pushing an edit out meant unpublishing and republishing,
 * which briefly took the lecture away from every reader for no reason.
 */
function usePublishMutation<TData>(
  action: (client: WsApiClient, pageId: string) => Promise<TData>,
) {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { pageId: string; folderId: string }) => action(client, vars.pageId),
    {
      onSuccess: (_data, vars) => {
        refreshPage(queryClient, vars.pageId);
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'page.revisions', vars.pageId],
        });
        // Readers' sidebars list only published lectures, and that list is
        // derived from the folder's children — so it has to be re-read too.
        void queryClient.invalidateQueries({
          queryKey: ['materials', 'folder.open', vars.folderId],
        });
      },
    },
  );
}

/** Compiles the current draft into a new published revision. Safe to call while already published. */
export function usePublishPage() {
  return usePublishMutation((client, pageId) => client.actions.page.publish({ page_id: pageId }));
}

/** Clears the published pointer. History and share links survive — see the confirm text. */
export function useUnpublishPage() {
  return usePublishMutation((client, pageId) => client.actions.page.unpublish({ page_id: pageId }));
}

// ---------------------------------------------------------------------------
// Blocks — editing/deleting/moving an *existing* block needs a short-lived
// edit lock (page.block.lock.acquire -> ...action... -> lock.release).
// Creating a brand new block doesn't need one.
// ---------------------------------------------------------------------------

export function useCreateBlock() {
  const queryClient = useQueryClient();
  return useWsMutation(
    (
      client,
      vars: {
        pageId: string;
        blockType: string;
        data: object;
        orderKey?: string;
        /**
         * Verified against the live API: `zone` is a free-form string that
         * round-trips unchanged, and the server defaults it to `"content"`.
         * Left unset for ordinary blocks so they keep landing in the default
         * zone; attachments pass ATTACHMENT_ZONE to stay out of the lecture
         * body (see materials.attachments.ts).
         */
        zone?: string;
      },
    ) =>
      client.actions.page.block.create({
        page_id: vars.pageId,
        block_type: vars.blockType,
        data: vars.data,
        ...(vars.zone !== undefined ? { zone: vars.zone } : {}),
        ...(vars.orderKey !== undefined ? { order_key: vars.orderKey } : {}),
      }),
    {
      /*
       * Блок появляется на странице сразу, ещё до ответа сервера.
       *
       * Id назначает сервер, поэтому у местного блока он временный: когда
       * приходит настоящий, временный заменяется. Это нужно ровно затем, чтобы
       * Enter не выглядел как задержка — строка над кареткой должна появиться
       * в тот же миг, а не через круг до сервера.
       *
       * Без `orderKey` местный блок не поставить: без него порядок задаёт
       * сервер, и угадывать место значило бы показать блок не там, где он
       * окажется. Такие вызовы (их немного) ждут ответа, как раньше.
       */
      onMutate: async (vars) => {
        if (vars.orderKey === undefined) return {};
        await holdPageReads(queryClient, vars.pageId);
        const tempId = `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        addBlock(queryClient, vars.pageId, {
          id: tempId,
          page_id: vars.pageId,
          block_type: vars.blockType,
          data: vars.data,
          zone: vars.zone ?? 'content',
          order_key: vars.orderKey,
          block_version: 1,
          schema_version: 1,
          ownership: 'owned',
        } as unknown as BlockData);
        return { tempId };
      },
      onError: (_error, vars, context) => {
        if (context?.tempId) dropBlock(queryClient, vars.pageId, context.tempId);
      },
      onSuccess: (created, vars, context) => {
        if (context?.tempId) dropBlock(queryClient, vars.pageId, context.tempId);
        addBlock(queryClient, vars.pageId, created as BlockData);
        refreshPage(queryClient, vars.pageId);
      },
    },
  );
}

/**
 * Saves a block using a lease the editor is already holding (see
 * useBlockLease) and the version the draft was started from.
 *
 * `expectedVersion` must be the version captured when editing began, never the
 * one from the latest render: with realtime updates in place, a colleague's
 * save refreshes the block and would otherwise hand this call *their* version,
 * turning optimistic concurrency into a silent overwrite. Measured against the
 * live API — the colleague's text was replaced with no error at all.
 */
export function useEditBlock() {
  const queryClient = useQueryClient();
  return useWsMutation(
    async (
      client,
      vars: {
        pageId: string;
        blockId: string;
        leaseId: string;
        expectedVersion: number;
        data: object;
      },
    ) =>
      client.actions.page.block.update({
        block_id: vars.blockId,
        lease_id: vars.leaseId,
        expected_block_version: vars.expectedVersion,
        data: vars.data,
      }),
    {
      onSuccess: (saved, vars) => {
        // Ответ несёт блок целиком — ставим его на место сразу, не
        // дожидаясь перечитывания страницы: иначе запоздавшее чтение
        // успевало вернуть прежнее состояние.
        replaceBlock(queryClient, vars.pageId, saved as BlockData);
        refreshPage(queryClient, vars.pageId);
      },
    },
  );
}

/**
 * Runs one lease-guarded action on a block the editor is *not* already holding.
 *
 * Reordering, changing a zone and changing a type are all one-shot writes
 * issued from a menu rather than from an open editor, so each takes its own
 * short-lived lease and gives it straight back. The release is best-effort:
 * the write already committed, and a lease left behind expires on its own TTL
 * (and unconditionally when the connection drops, per docs/protocol.md).
 */
async function withBlockLease<T>(
  client: WsApiClient,
  blockId: string,
  action: (leaseId: string) => Promise<T>,
): Promise<T> {
  const lease = await client.actions.page.block.lock.acquire({ block_id: blockId });
  try {
    return await action(lease.lease_id);
  } finally {
    await client.actions.page.block.lock
      .release({ block_id: blockId, lease_id: lease.lease_id })
      .catch(() => undefined);
  }
}

/** Reorders a block by giving it a new order_key — see materials.utils.ts's orderKeyForMove for how neighbors are computed. `zone` is passed through unchanged (BlockMoveInput requires it, but we're not relocating blocks between zones here). */
export function useMoveBlock() {
  const queryClient = useQueryClient();
  return useWsMutation(
    async (
      client,
      vars: {
        pageId: string;
        blockId: string;
        expectedVersion: number;
        zone: string;
        orderKey: string;
      },
    ) =>
      withBlockLease(client, vars.blockId, (leaseId) =>
        client.actions.page.block.move({
          block_id: vars.blockId,
          lease_id: leaseId,
          expected_block_version: vars.expectedVersion,
          zone: vars.zone,
          order_key: vars.orderKey,
        }),
      ),
    {
      /*
       * Блок переезжает сразу: Cmd+Shift+стрелка иначе ждёт три круга до
       * сервера, и строка какое-то время остаётся на прежнем месте.
       */
      onMutate: async (vars) => {
        await holdPageReads(queryClient, vars.pageId);
        const snapshot = pageSnapshot(queryClient, vars.pageId);
        patchBlocks(queryClient, vars.pageId, (blocks) =>
          blocks.map((block) =>
            block.id === vars.blockId
              ? { ...block, zone: vars.zone, order_key: vars.orderKey }
              : block,
          ),
        );
        return { snapshot };
      },
      onError: (_error, vars, context) => {
        restorePage(queryClient, vars.pageId, context?.snapshot);
      },
      onSuccess: (saved, vars) => {
        // Ответ несёт блок целиком — ставим его на место, чтобы версия и
        // порядок совпали с серверными.
        replaceBlock(queryClient, vars.pageId, saved as BlockData);
        refreshPage(queryClient, vars.pageId);
      },
    },
  );
}

/**
 * Moves a block into another zone — i.e. into another tab of the same lecture.
 *
 * Zones are how this app splits one page across its tabs (see
 * materials.zones.ts), so "перенести в конспект" is a zone change and nothing
 * else. It goes through `page.block.change_zone` rather than `page.block.move`:
 * the two take the identical payload and the docs call one an alias of the
 * other, but the action name is what ends up in the page's audit trail, and a
 * reorder and a relocation are worth telling apart there.
 *
 * The destination `order_key` is computed here rather than passed in: the
 * target zone is by definition the tab the author is *not* looking at, so its
 * blocks are nowhere near the call site — but they are in the cached
 * `page.open`, which is the same list the other tab renders from. The block
 * lands last in the destination.
 */
export function useChangeBlockZone() {
  const queryClient = useQueryClient();
  return useWsMutation(
    async (
      client,
      vars: {
        pageId: string;
        blockId: string;
        expectedVersion: number;
        zone: string;
      },
    ) => {
      const page = queryClient.getQueryData<PageOpenResult>([
        'materials',
        'page.open',
        vars.pageId,
      ]);
      const destination = (page?.blocks ?? []).filter(
        (block) => block.zone === vars.zone && block.id !== vars.blockId,
      );
      return withBlockLease(client, vars.blockId, (leaseId) =>
        client.actions.page.block.change_zone({
          block_id: vars.blockId,
          lease_id: leaseId,
          expected_block_version: vars.expectedVersion,
          zone: vars.zone,
          order_key: nextOrderKey(destination),
        }),
      );
    },
    {
      onSuccess: (saved, vars) => {
        // Ответ несёт блок целиком — ставим его на место сразу, не
        // дожидаясь перечитывания страницы: иначе запоздавшее чтение
        // успевало вернуть прежнее состояние.
        replaceBlock(queryClient, vars.pageId, saved as BlockData);
        refreshPage(queryClient, vars.pageId);
      },
    },
  );
}

/**
 * Changes a block's type, replacing its `data` wholesale.
 *
 * `page.block.type.change` does not merge — whatever `data` is passed becomes
 * the block's entire content. So the caller decides what survives the
 * conversion (see block-registry.convert.ts): text-shaped kinds hand their
 * text over, and anything else starts from the new kind's default rather than
 * keeping a payload the new renderer cannot read.
 */
export function useChangeBlockType() {
  const queryClient = useQueryClient();
  return useWsMutation(
    async (
      client,
      vars: {
        pageId: string;
        blockId: string;
        expectedVersion: number;
        blockType: string;
        data: object;
      },
    ) =>
      withBlockLease(client, vars.blockId, (leaseId) =>
        client.actions.page.block.type.change({
          block_id: vars.blockId,
          lease_id: leaseId,
          expected_block_version: vars.expectedVersion,
          block_type: vars.blockType,
          data: vars.data,
        }),
      ),
    {
      /*
       * Блок меняет вид сразу, ещё до ответа сервера.
       *
       * Замерено: «# » превращалось в заголовок за секунду при задержке сети
       * 250 мс — смена типа успевает сходить за блокировкой, дописать текст и
       * поменять тип, и всё это время на экране абзац. Для человека, который
       * набирает разметку, это и есть «тормозит ввод».
       */
      onMutate: async (vars) => {
        await holdPageReads(queryClient, vars.pageId);
        const snapshot = pageSnapshot(queryClient, vars.pageId);
        patchBlocks(queryClient, vars.pageId, (blocks) =>
          blocks.map((block) =>
            block.id === vars.blockId
              ? { ...block, block_type: vars.blockType, data: vars.data }
              : block,
          ),
        );
        return { snapshot };
      },
      onError: (_error, vars, context) => {
        restorePage(queryClient, vars.pageId, context?.snapshot);
      },
      onSuccess: (saved, vars) => {
        // Ответ несёт блок целиком — ставим его на место, чтобы версия и
        // порядок совпали с серверными.
        replaceBlock(queryClient, vars.pageId, saved as BlockData);
        refreshPage(queryClient, vars.pageId);
      },
    },
  );
}

export function useDeleteBlock() {
  const queryClient = useQueryClient();
  return useWsMutation(
    async (client, vars: { pageId: string; blockId: string; expectedVersion: number }) => {
      const lease = await client.actions.page.block.lock.acquire({ block_id: vars.blockId });
      try {
        return await client.actions.page.block.delete({
          block_id: vars.blockId,
          lease_id: lease.lease_id,
          expected_block_version: vars.expectedVersion,
        });
      } catch (error) {
        await client.actions.page.block.lock
          .release({ block_id: vars.blockId, lease_id: lease.lease_id })
          .catch(() => undefined);
        throw error;
      }
    },
    {
      /*
       * Блок исчезает сразу, не дожидаясь сервера.
       *
       * Здесь и было «стёрлось, вернулось, снова пропало»: чтение страницы,
       * ушедшее до удаления, приходило после него и возвращало блок в кеш.
       * Поэтому чтения на этот момент отменяются, а состояние до правки
       * сохраняется — чтобы вернуть его, если сервер откажет.
       */
      onMutate: async (vars) => {
        await holdPageReads(queryClient, vars.pageId);
        const snapshot = pageSnapshot(queryClient, vars.pageId);
        dropBlock(queryClient, vars.pageId, vars.blockId);
        return { snapshot };
      },
      onError: (_error, vars, context) => {
        restorePage(queryClient, vars.pageId, context?.snapshot);
      },
      onSuccess: (_data, vars) => {
        refreshPage(queryClient, vars.pageId);
      },
    },
  );
}
