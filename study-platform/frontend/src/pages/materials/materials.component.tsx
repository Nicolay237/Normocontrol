// Real data wiring:
//   - Sidebar tree + breadcrumbs  <- folder.open({ folder_id: :folderId })
//   - Hero / topic / lecture body <- page.open({ page_id: :pageId })
//   - Tabs (конспект/файлы/тест/обсуждение) <- block zones on the same page,
//     plus user.data (private notes) and chat.* (discussion). See
//     materials.tabs.ts and materials.zones.ts.
// Route params: :folderId (required), :pageId (optional — no page selected
// yet renders a folder-landing state) and :tab (optional, defaults to the
// lecture). See routes.tsx for the registration.
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type FormEvent,
  type MouseEvent,
} from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  BookMarked,
  Download,
  FilePlus,
  FolderPlus,
  History,
  List,
  ListTree,
  MoreHorizontal,
  NotebookPen,
  PanelLeft,
  Pencil,
  Trash2,
  UploadCloud,
  Users,
  X,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { DocScope, toBlockDataList, toDocBlocks, usePageDoc } from './doc';
import { cn } from '@/lib/cn';
import { useWsQuery } from '@/app/ws';
import { uploadFile } from '@/api/workspace.utils';
import { usePrimaryNavLinks } from '@/components/top-nav';
import { PageShell } from '@/components/page-shell';
import { PinButton } from '@/components/pin-button';
import { Button } from '@/components/button';
import { Spinner } from '@/components/spinner';
import { Dialog } from '@/components/dialog';
import { AccessPanel } from './components/access-panel';
import { SourcesPanel } from './components/sources-panel';
import { TextInputDialog } from './components/text-input-dialog';
import { PageHistory } from './components/page-history';
import { PublishControl } from './components/publish-control';
import { EditingPresence } from './components/editing-presence';
import { UserDirectory, type UserDirectoryEntry } from './components/user-directory';
import { LectureDiscussion } from './components/lecture-discussion';
import { LectureFiles } from './components/lecture-files';
import { LectureNotes } from './components/lecture-notes';
import { LectureTest } from './components/lecture-test';
import { BannerUploadControl, useBannerImage } from './components/banner';
import { ResumeReading } from './components/resume-reading';
import { useReadingPosition } from './use-reading-position';
import { Breadcrumb, type BreadcrumbLink } from './components/breadcrumb';
import { PageEditor } from './components/block-editor';
import { BlockRenderer } from './components/block-renderer';
import { CourseHero } from './components/course-hero';
import { LabPanel } from './components/lab-panel';
import { NormocontrolPanel } from './components/normocontrol-panel';
import { CoursePicker } from './components/course-picker';
import { CourseSidebar, type CourseSidebarSection } from './components/course-sidebar';
import { FolderTree } from './components/folder-tree';
import { LectureNav, type LectureNavDotState, type LectureNavLink } from './components/lecture-nav';
import {
  LectureSidebar,
  type LectureExternalLink,
  type LectureFile,
  type TocItem,
} from './components/lecture-sidebar';
import type { SidebarItemData } from './components/sidebar-item';
import { TabsBar } from './components/tabs-bar';
import styles from './materials.style.module.css';
import {
  blockAnchorId,
  blockHeadingText,
  buildFileDownloadUrl,
  childHref,
  childIconForKind,
  notesLecturePageId,
  describeWsError,
  displayFolderName,
  isTestKind,
  downloadFileById,
  formatFileSize,
  isFolderLikeKind,
  nextOrderKey,
  openResourceFile,
  pageKindLabel,
  sortByOrderKey,
} from './materials.utils';
import {
  ATTACHMENT_BLOCK_TYPE,
  attachmentBlockData,
  attachmentKind,
  attachmentMeta,
  readAttachment,
} from './materials.attachments';
import { fileAbbrevFromContentType, fileKindFromContentType } from './materials.file-types';
import { ATTACHMENT_ZONE, splitPageZones } from './materials.zones';
import { buildTabItems, resolveTab, type MaterialsTab } from './materials.tabs';
import {
  canEditResource,
  canManageAccess,
  isBlockedRole,
  type Role,
} from './materials.permissions';
import { useChildVisibility, type ChildVisibility } from './use-child-visibility';
import { collectSubtree, describeSubtree } from './folder-subtree';
import { clearDeletedResource, readDeletedResource } from './deleted-resources.store';
import { useResourceMenu } from './use-resource-menu';
import { useSidebarWidth, SIDEBAR_MAX, SIDEBAR_MIN } from './use-sidebar-width';
import { useNotesPanelOpen } from './use-notes-panel-open';
import { NotesPanel } from './components/notes-panel';
import { NotesPage } from './components/notes-page';
import {
  NOTES_PANEL_DEFAULT,
  NOTES_PANEL_MAX,
  NOTES_PANEL_MIN,
} from './components/notes-panel/notes-panel.constants';
import { useResizableWidth } from '@/hooks/use-resizable-width';
import { useFloatingPanel } from '@/hooks/use-floating-panel';
import type { ResourceMenuTarget } from './components/resource-menu';
import {
  collectPersonalFolderUserIds,
  folderDisplayName,
  isUserDirectoryFolder,
  personalFolderMeta,
  personalFolderUserId,
  type UserLookup,
} from './materials.users';
import { useUserDirectory } from './use-users';
import { useReachableAncestors } from './use-reachable-ancestors';
import { useFolderRedirect } from './use-folder-redirect';
import { useTreeMode } from './use-tree-mode';
import { EdgePanel } from '@/components/edge-panel';
import { useMediaQuery } from '@/hooks/use-media-query';
import { useMaterialsRealtime } from './use-materials-realtime';
import {
  isPagePublished,
  readSnapshot,
  usePublishedRevision,
  type RevisionData,
} from './use-page-publication';
import { usePageRevisions } from './use-page-revisions';
import { usePageSources, type SourceData } from './use-page-sources';
import { useCreateTest, useDeleteTest } from './use-page-test';
import {
  useCreateBlock,
  useCreateFolder,
  useCreatePage,
  useDeleteBlock,
  useDeleteFolder,
  useDeletePage,
  useRenameFolder,
  useRenamePage,
  useRestoreFolder,
  useRestorePage,
  type PageKind,
} from './use-materials-mutations';
import type {
  BlockData,
  FolderChildData,
  FolderData,
  MaterialsPageProps,
  PageData,
  PageOpenResult,
  PageResourceData,
} from './materials.types';

// ---------------------------------------------------------------------------
// Data -> prop mapping helpers
// ---------------------------------------------------------------------------

function buildBreadcrumbLinks(
  ancestors: FolderData[],
  users: UserLookup,
  isReachable: (folderId: string) => boolean,
): BreadcrumbLink[] {
  return ancestors.map((folder): BreadcrumbLink => ({
    id: folder.id,
    label: folderDisplayName(folder.name, users),
    href: `/materials/${folder.id}`,
    isReachable: isReachable(folder.id),
  }));
}

/**
 * No section-grouping metadata exists on FolderChild — everything from one
 * folder.open call becomes a single flat list. Children whose name is a user
 * id are personal folders (see materials.users.ts) and are shown as the
 * person they belong to, not as a uuid-named "Раздел".
 */
function buildSidebarSections(
  folderId: string,
  activePageId: string | undefined,
  users: UserLookup,
  /**
   * Which children may be shown, and how — the same rules the tree applies.
   * See use-child-visibility.ts for why this is shared rather than inlined.
   */
  visibility: ChildVisibility,
  /**
   * Whether the viewer can edit the folder itself. Per-child roles come from
   * `page.open`, which is only issued for non-editors (and never for tests,
   * which aren't pages at all) — so the folder's own role is what decides
   * whether a test row offers its editor/results shortcuts.
   */
  canEditFolder: boolean,
  /** Invoked by a test row's delete action; confirmation lives with the caller. */
  onDeleteTest: (testId: string, name: string) => void,
): CourseSidebarSection[] {
  const sorted = sortByOrderKey(visibility.visible);
  const items: SidebarItemData[] = sorted.map((child): SidebarItemData => {
    const userId = personalFolderUserId(child.name);
    const childRole = visibility.roles.get(child.id) ?? 'student';
    const blocked = visibility.isBlocked(child.id);
    const canEditChild = canEditFolder || canEditResource(childRole);
    return {
      id: child.id,
      href: childHref(folderId, child, canEditChild),
      // Editors get one-click access to a test's builder and its results
      // without first opening the test itself.
      actions:
        isTestKind(child.kind) && canEditChild && !blocked
          ? [
              {
                id: 'edit',
                href: `/tests/${child.id}/edit`,
                icon: 'edit',
                label: 'Редактор теста',
              },
              {
                id: 'stats',
                href: `/tests/${child.id}/students/results`,
                icon: 'stats',
                label: 'Результаты',
              },
              {
                id: 'delete',
                icon: 'delete',
                danger: true,
                label: 'Удалить тест',
                onClick: () => onDeleteTest(child.id, child.name),
              },
            ]
          : undefined,
      icon: blocked ? 'locked' : userId ? 'user' : childIconForKind(child.kind, child.icon_name),
      name: userId ? folderDisplayName(child.name, users) : child.name,
      // Empty for ordinary materials: the glyph already says what the kind is,
      // and a second line per row is what makes a long folder feel heavy. Kept
      // where it carries something extra — who owns a personal folder, that a
      // resource is out of reach, or that a document is app-maintained notes
      // and belongs to a lecture elsewhere.
      sub: blocked
        ? 'Недоступно'
        : userId
          ? personalFolderMeta(userId, users)
          : notesLecturePageId(child.icon_name)
            ? 'Личные заметки'
            : '',
      active: child.id === activePageId,
      // No per-item completion tracking in FolderChild — always 'none' (no badge/checkmark) for real data.
      status: 'none',
    };
  });
  return [{ id: 'contents', title: 'Содержимое', items }];
}

/** Rows for the user registry — one per personal folder in this container. */
function buildUserDirectoryEntries(
  folderId: string,
  children: FolderChildData[],
  users: UserLookup,
): UserDirectoryEntry[] {
  return sortByOrderKey(children).flatMap((child): UserDirectoryEntry[] => {
    const userId = personalFolderUserId(child.name);
    if (!userId) return [];
    return [
      {
        folderId: child.id,
        href: childHref(folderId, child),
        userId,
        user: users.get(userId) ?? null,
      },
    ];
  });
}

/** TOC entries are derived from heading-type blocks (best-guess block_type mapping, see block-renderer) instead of any dedicated schema field — there isn't one. */
function buildTocItems(blocks: BlockData[]): TocItem[] {
  const headings = sortByOrderKey(blocks).filter((block) => blockHeadingText(block) !== null);
  return headings.map((block, index): TocItem => ({
    id: block.id,
    num: String(index + 1).padStart(2, '0'),
    name: blockHeadingText(block) as string,
    href: `#${blockAnchorId(block.id)}`,
    state: 'none',
  }));
}

/**
 * The sidebar's file card. Attachment blocks are the real source (see
 * materials.attachments.ts for why `page.resources` cannot be); whatever the
 * server reports in `resources` is appended after, so nothing is lost if that
 * field ever starts working.
 */
function buildAttachmentFiles(
  attachmentBlocks: BlockData[],
  resources: PageResourceData[] | undefined,
  onRemove: ((block: BlockData) => void) | null,
): LectureFile[] {
  const fromBlocks = sortByOrderKey(attachmentBlocks).flatMap((block): LectureFile[] => {
    const attachment = readAttachment(block);
    if (!attachment) return [];
    return [
      {
        id: block.id,
        name: attachment.name,
        meta: attachmentMeta(attachment),
        kind: attachmentKind(attachment),
        href: buildFileDownloadUrl(attachment.fileId),
        onClick: (event) => {
          event.preventDefault();
          void downloadFileById(attachment.fileId, attachment.name);
        },
        onRemove: onRemove ? () => onRemove(block) : undefined,
      },
    ];
  });
  return [...fromBlocks, ...buildFileItems(resources)];
}

function buildFileItems(resources: PageResourceData[] | undefined): LectureFile[] {
  if (!resources) return [];
  return resources.map((resource): LectureFile => ({
    id: resource.file_id,
    name: resource.original_name,
    meta: `${fileAbbrevFromContentType(resource.content_type, resource.original_name)} · ${formatFileSize(resource.size)}`,
    kind: fileKindFromContentType(resource.content_type, resource.original_name),
    href: buildFileDownloadUrl(resource.file_id),
    onClick: (event) => {
      event.preventDefault();
      void openResourceFile(resource);
    },
  }));
}

interface PageDownload {
  id: string;
  label: string;
  href: string;
  onClick: (event: MouseEvent<HTMLAnchorElement>) => void;
}

/** Replaces the mock "Скачать PDF" button — one action per download-behavior resource. */
function buildPageDownloads(resources: PageResourceData[] | undefined): PageDownload[] {
  if (!resources) return [];
  return resources
    .filter((resource) => resource.behavior === 'download')
    .map((resource): PageDownload => ({
      id: resource.file_id,
      label: resource.original_name,
      href: buildFileDownloadUrl(resource.file_id),
      onClick: (event) => {
        event.preventDefault();
        void openResourceFile(resource);
      },
    }));
}

function buildExternalLinks(sources: SourceData[]): LectureExternalLink[] {
  return sources.flatMap((source) => {
    const rawUrl = source.url?.trim();
    if (!rawUrl) return [];

    try {
      const url = new URL(/^[a-z][a-z\d+.-]*:/i.test(rawUrl) ? rawUrl : `https://${rawUrl}`);
      if (url.protocol !== 'http:' && url.protocol !== 'https:') return [];

      const site = url.hostname.replace(/^www\./i, '');
      return [
        {
          id: source.id,
          title: source.title.trim() || site,
          site,
          href: url.href,
          faviconHref: new URL('/favicon.ico', url.origin).href,
        },
      ];
    } catch {
      return [];
    }
  });
}

interface LectureNavData {
  prev?: LectureNavLink;
  next?: LectureNavLink;
  dots: LectureNavDotState[];
  current: number;
  total: number;
}

/**
 * Derived from folder.open's `children`, not a dedicated "course sequence"
 * action — restricted to non-folder-like siblings, ordered by order_key. No
 * "done" dot state is synthesized (that would fabricate completion data);
 * only the current item is marked, everything else is 'upcoming'.
 */
function buildLectureNavData(
  folderId: string,
  children: FolderChildData[],
  currentPageId: string,
): LectureNavData | null {
  const siblings = sortByOrderKey(children.filter((child) => !isFolderLikeKind(child.kind)));
  const index = siblings.findIndex((child) => child.id === currentPageId);
  if (index === -1) return null;

  const prevChild = siblings[index - 1];
  const nextChild = siblings[index + 1];
  return {
    prev: prevChild
      ? {
          label: 'Предыдущая',
          name: prevChild.name,
          href: `/materials/${folderId}/${prevChild.id}`,
        }
      : undefined,
    next: nextChild
      ? { label: 'Следующая', name: nextChild.name, href: `/materials/${folderId}/${nextChild.id}` }
      : undefined,
    dots: siblings.map((child): LectureNavDotState =>
      child.id === currentPageId ? 'active' : 'upcoming',
    ),
    current: index + 1,
    total: siblings.length,
  };
}

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

function StateScreen({
  title,
  description,
  onRetry,
  scoped,
}: {
  title: string;
  description?: string;
  onRetry?: () => void;
  scoped?: boolean;
}) {
  return (
    <div className={scoped ? styles.stateScoped : styles.stateScreen}>
      <div className={styles.stateTitle}>{title}</div>
      {description && <div className={styles.stateText}>{description}</div>}
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Повторить
        </Button>
      )}
    </div>
  );
}

/** Landing state for the bare `/materials` route — the picker owns everything inside the shell. */
function CoursePickerScreen() {
  const navLinks = usePrimaryNavLinks();
  return (
    <PageShell navLinks={navLinks}>
      <CoursePicker />
    </PageShell>
  );
}

/**
 * "Отменить" for the folder or page that was just deleted.
 *
 * The API has no way to browse the trash, so the id kept in
 * deleted-resources.store.ts is the only handle a restore can be issued with —
 * once this banner goes, the resource is only recoverable by someone with
 * database access. It appears in the parent the delete navigated to, and only
 * within the store's short window.
 *
 * For a folder it deliberately does not promise a full undo: `test.restore`
 * does not exist, so any tests in the subtree stayed deleted and the wording
 * says so. A page has no such caveat — `page.restore` brings it back whole.
 */
function DeletedResourceNotice({ parentFolderId }: { parentFolderId: string | null }) {
  const [entry, setEntry] = useState(() => readDeletedResource());
  const restoreFolder = useRestoreFolder();
  const restorePage = useRestorePage();
  const restore = entry?.kind === 'page' ? restorePage : restoreFolder;

  // Only offered in the folder the delete returned to — surfacing it anywhere
  // else in the app would be a button with no context around it.
  if (!entry || entry.parentId !== parentFolderId) return null;

  async function handleRestore() {
    if (!entry) return;
    try {
      if (entry.kind === 'page') {
        await restorePage.mutateAsync({ pageId: entry.resourceId, folderId: entry.parentId });
      } else {
        await restoreFolder.mutateAsync({
          folderId: entry.resourceId,
          parentId: entry.parentId,
        });
      }
    } catch {
      // Kept on screen with the error shown: this is the last handle on the
      // resource, so a failed restore must not clear the offer to retry it.
      return;
    }
    clearDeletedResource();
    setEntry(null);
  }

  function handleDismiss() {
    clearDeletedResource();
    setEntry(null);
  }

  return (
    <output className={styles.undoBar}>
      <span className={styles.undoText}>
        {entry.kind === 'page'
          ? `Материал «${entry.name}» удалён.`
          : 'Раздел удалён вместе с содержимым. Тесты внутри восстановить нельзя.'}
      </span>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => void handleRestore()}
        disabled={restore.isPending}
      >
        {restore.isPending ? 'Восстановление…' : 'Отменить'}
      </Button>
      <button
        type="button"
        className={styles.undoDismiss}
        aria-label="Скрыть"
        onClick={handleDismiss}
      >
        <X size={14} />
      </button>
      {restore.error && <span className={styles.formError}>{describeWsError(restore.error)}</span>}
    </output>
  );
}

function FolderLanding({ folder, title }: { folder: FolderData; title: string }) {
  return (
    <div className={styles.folderLanding}>
      <div className={styles.folderLandingTitle}>{title}</div>
      {folder.description && (
        <p className={styles.folderLandingDescription}>{folder.description}</p>
      )}
      <div className={styles.folderLandingHint}>
        Выберите материал в списке слева, чтобы открыть его.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Editing UI (folders, pages, blocks) — only rendered for owner/editor roles,
// gated by canEditResource(effective_role). See materials.permissions.ts.
// ---------------------------------------------------------------------------

/**
 * What the "Новый материал" dialog can create. The first three are `kind`
 * values of a single `page.create`; a test is a separate resource type with
 * its own action, so it is carried as a fourth option here and branched on at
 * submit rather than being squeezed into `PageKind`.
 */
type CreateKind = PageKind | 'test';

const PAGE_KIND_OPTIONS: { value: CreateKind; label: string; hint: string }[] = [
  { value: 'lecture', label: 'Лекция', hint: 'Конспект, файлы, тест и обсуждение' },
  { value: 'document', label: 'Документ', hint: 'Текстовая страница' },
  { value: 'resource', label: 'Материал', hint: 'Ссылки и вложения' },
  { value: 'lab', label: 'Лабораторная', hint: 'Сдача файлом и оценка' },
  {
    value: 'normocontrol',
    label: 'Нормоконтроль',
    hint: 'Проверка оформления по ГОСТ, без оценки',
  },
  { value: 'test', label: 'Тест', hint: 'Банки вопросов и попытки' },
];

/** Same as TextInputDialog, plus a kind selector (page.create's `kind`, or a test). */
function CreatePageDialog({
  open,
  isPending,
  error,
  onClose,
  onSubmit,
}: {
  open: boolean;
  isPending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (name: string, kind: CreateKind) => void;
}) {
  const [name, setName] = useState('');
  const [kind, setKind] = useState<CreateKind>('lecture');

  useEffect(() => {
    if (open) {
      setName('');
      setKind('lecture');
    }
  }, [open]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (trimmed) onSubmit(trimmed, kind);
  }

  return (
    <Dialog open={open} title="Новый материал" onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.formLabel} htmlFor="create-page-name">
          Название
        </label>
        <input
          id="create-page-name"
          className={styles.formInput}
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoFocus
        />

        <span className={styles.formLabel}>Тип</span>
        <div className={styles.kindOptions}>
          {PAGE_KIND_OPTIONS.map((option) => (
            <label
              key={option.value}
              // Both label and hint are read out: the hint is what tells the
              // two similar-sounding kinds apart.
              aria-label={`${option.label} — ${option.hint}`}
              className={cn(styles.kindOption, kind === option.value && styles.kindOptionActive)}
            >
              <input
                type="radio"
                name="page-kind"
                value={option.value}
                checked={kind === option.value}
                onChange={() => setKind(option.value)}
              />
              <span className={styles.kindOptionBody}>
                <span className={styles.kindOptionLabel}>{option.label}</span>
                <span className={styles.kindOptionHint}>{option.hint}</span>
              </span>
            </label>
          ))}
        </div>

        {error && <p className={styles.formError}>{error}</p>}
        <div className={styles.formActions}>
          <Button type="submit" size="sm" disabled={isPending || !name.trim()}>
            {isPending ? 'Создание…' : 'Создать'}
          </Button>
          <Button type="button" size="sm" variant="secondary" onClick={onClose}>
            Отмена
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

type DialogKind = 'create-folder' | 'create-page' | 'rename-folder' | 'rename-page' | null;

/** Create/rename/delete for the current folder, plus "create subfolder/page" and the access panel — lives above CourseSidebar. */
function SidebarToolbar({
  folderId,
  parentId,
  folderName,
  folderLabel,
  folderChildren,
  viewerRole,
}: {
  folderId: string;
  parentId: string | null;
  /**
   * The folder's *stored* name — what the rename field must start from. For a
   * personal folder that's the owner's user id, and it has to stay that way:
   * the id in the name is the only link back to the user, so prefilling the
   * resolved display name would silently break it on save.
   */
  folderName: string;
  /** The resolved, human-readable name — for confirmations and dialog titles. */
  folderLabel: string;
  /** This folder's own children — the starting point for the pre-delete walk. */
  folderChildren: FolderChildData[];
  viewerRole: Role;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<DialogKind>(null);
  const [isAccessOpen, setIsAccessOpen] = useState(false);
  const createFolder = useCreateFolder();
  const createPage = useCreatePage();
  const createTest = useCreateTest();
  const renameFolder = useRenameFolder();
  const deleteFolder = useDeleteFolder();

  function closeDialog() {
    setDialog(null);
    createFolder.reset();
    createPage.reset();
    createTest.reset();
    renameFolder.reset();
  }

  async function handleDeleteFolder() {
    // Deletion is recursive server-side, so the prompt has to name what else
    // goes with it — and that tests among them cannot be restored. See
    // folder-subtree.ts.
    const contents = collectSubtree(queryClient, folderId, folderChildren);
    if (!window.confirm(describeSubtree(folderLabel, contents))) return;
    await deleteFolder.mutateAsync({
      folderId,
      name: folderLabel,
      parentId: parentId ?? undefined,
      contents,
    });
    navigate(parentId ? `/materials/${parentId}` : '/materials');
  }

  return (
    <div className={styles.sidebarToolbar}>
      {/* Creation is the primary job here, so it gets a full-width row and
          visible labels. Management stays quieter below it, with destruction
          isolated at the far edge instead of sitting beside "new material". */}
      <div className={cn(styles.sidebarToolbarGroup, styles.sidebarCreateGroup)}>
        <button
          type="button"
          className={cn(styles.toolbarButton, styles.toolbarButtonCreate)}
          onClick={() => setDialog('create-folder')}
          title="Новый раздел"
          aria-label="Новый раздел"
        >
          <FolderPlus size={14} />
          <span>Раздел</span>
        </button>
        <button
          type="button"
          className={cn(styles.toolbarButton, styles.toolbarButtonCreate)}
          onClick={() => setDialog('create-page')}
          title="Новый материал"
          aria-label="Новый материал"
        >
          <FilePlus size={14} />
          <span>Материал</span>
        </button>
      </div>

      <div className={cn(styles.sidebarToolbarGroup, styles.sidebarManageGroup)}>
        <button
          type="button"
          className={styles.toolbarButton}
          onClick={() => setDialog('rename-folder')}
          title="Переименовать раздел"
          aria-label="Переименовать раздел"
        >
          <Pencil size={14} />
          <span>Изменить</span>
        </button>
        {canManageAccess(viewerRole) && (
          <button
            type="button"
            className={styles.toolbarButton}
            onClick={() => setIsAccessOpen(true)}
            title="Доступ к разделу"
            aria-label="Доступ к разделу"
          >
            <Users size={14} />
            <span>Доступ</span>
          </button>
        )}
        <button
          type="button"
          className={cn(styles.toolbarButton, styles.toolbarButtonDanger)}
          onClick={() => void handleDeleteFolder()}
          disabled={deleteFolder.isPending}
          title="Удалить раздел"
          aria-label="Удалить раздел"
        >
          <Trash2 size={14} />
          <span>Удалить</span>
        </button>
      </div>

      <AccessPanel
        open={isAccessOpen}
        resourceType="folder"
        resourceId={folderId}
        resourceName={folderLabel}
        viewerRole={viewerRole}
        onClose={() => setIsAccessOpen(false)}
      />

      <TextInputDialog
        open={dialog === 'create-folder'}
        title="Новый раздел"
        label="Название"
        submitLabel="Создать"
        isPending={createFolder.isPending}
        error={createFolder.error ? describeWsError(createFolder.error) : null}
        onClose={closeDialog}
        onSubmit={async (name) => {
          const folder = await createFolder.mutateAsync({ parentId: folderId, name });
          closeDialog();
          navigate(`/materials/${folder.id}`);
        }}
      />
      <CreatePageDialog
        open={dialog === 'create-page'}
        isPending={createPage.isPending || createTest.isPending}
        error={
          createPage.error
            ? describeWsError(createPage.error)
            : createTest.error
              ? describeWsError(createTest.error)
              : null
        }
        onClose={closeDialog}
        onSubmit={async (name, kind) => {
          // A standalone test: its own resource type, and the builder is the
          // only screen that can do anything with an empty one.
          if (kind === 'test') {
            const test = await createTest.mutateAsync({ folderId, name });
            closeDialog();
            navigate(`/tests/${test.id}/edit`);
            return;
          }
          const page = await createPage.mutateAsync({ folderId, name, kind });
          closeDialog();
          navigate(`/materials/${folderId}/${page.id}`);
        }}
      />
      <TextInputDialog
        open={dialog === 'rename-folder'}
        title="Переименовать раздел"
        label="Название"
        initialValue={displayFolderName(folderName)}
        isPending={renameFolder.isPending}
        error={renameFolder.error ? describeWsError(renameFolder.error) : null}
        onClose={closeDialog}
        onSubmit={async (name) => {
          await renameFolder.mutateAsync({ folderId, name });
          closeDialog();
        }}
      />
    </div>
  );
}

/**
 * Everything you can *do* to the open page, and nothing about what it is.
 *
 * It used to sit under a second heading repeating the name already set in the
 * hero — two titles, one page. The name lives in the hero now; this row is
 * purely a toolbar, so it disappears entirely for a reader with nothing to
 * download.
 */
function PageToolbar({
  page,
  folderId,
  draftBlocks,
  publishedRevision,
  downloads,
  canEdit,
  viewerRole,
  isNotesOpen,
  onToggleNotes,
}: {
  page: PageData;
  folderId: string;
  /** Live draft, handed to the history panel for its diff against a revision. */
  draftBlocks: BlockData[];
  publishedRevision: RevisionData | null;
  /** Shown to readers too — a download is the point of the page, not an editing tool. */
  downloads: PageDownload[];
  canEdit: boolean;
  /** This page's own effective_role, straight from `page.open` — the access panel needs it, not just the boolean. */
  viewerRole: Role;
  /** Whether the private notes column is showing beside the lecture. */
  isNotesOpen: boolean;
  onToggleNotes: () => void;
}) {
  const navigate = useNavigate();
  const [isRenaming, setIsRenaming] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isAccessOpen, setIsAccessOpen] = useState(false);
  const [isSourcesOpen, setIsSourcesOpen] = useState(false);
  // Mobile only: rename/versions/delete collapse behind "…" so the reader is
  // not met by a wall of editing controls before the lecture itself.
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const pageId = page.id;
  const pageName = page.name;
  const renamePage = useRenamePage();
  const deletePage = useDeletePage();
  // Only read while the sources panel is open: a provenance report is always
  // about one revision, and nothing else in this toolbar needs the list.
  const history = usePageRevisions(pageId, isSourcesOpen);

  async function handleDelete() {
    if (!window.confirm(`Удалить материал «${pageName}»?`)) return;
    await deletePage.mutateAsync({ pageId, folderId, name: pageName });
    navigate(`/materials/${folderId}`);
  }

  return (
    <div className={styles.pageToolbar}>
      {/*
        Four zones, left to right: what a reader uses, what the publication
        state is, what manages the page, and the one thing that destroys it.
        They used to be a single flat row of nine equal chips, which is why it
        read as clutter — nothing said which of them was the important one.
      */}
      <div className={styles.tbZone}>
        <PinButton resourceType="page" resourceId={pageId} resourceName={pageName} />
        {/* Everyone gets this: private notes are a reader's tool, not an
            editor's. Hidden below the tablet breakpoint together with the
            column it opens — see notes-panel.style. */}
        <button
          type="button"
          className={cn(styles.tbAction, styles.notesToggle)}
          aria-pressed={isNotesOpen}
          title={isNotesOpen ? 'Скрыть мои заметки' : 'Показать мои заметки'}
          onClick={onToggleNotes}
        >
          <NotebookPen size={13} /> Заметки
        </button>
      </div>

      {canEdit && (
        <>
          <span className={styles.tbDivider} />
          <PublishControl page={page} folderId={folderId} publishedRevision={publishedRevision} />
          <EditingPresence />
        </>
      )}

      <span className={styles.toolbarSpacer} />

      {downloads.length > 0 && (
        <div className={styles.tbZone}>
          {downloads.map((download) => (
            <a
              key={download.id}
              className={styles.tbAction}
              href={download.href}
              onClick={download.onClick}
            >
              <Download size={13} /> {download.label}
            </a>
          ))}
        </div>
      )}

      {canEdit && (
        <>
          {/* Wide screens keep every action in the row. Narrow ones get one
              labelled button opening a bottom sheet — Material's guidance for
              an overflow list on a phone, and the one shape that cannot end
              up rendered off the edge of the screen. */}
          <div className={styles.toolbarGroup}>
            {/* Four destinations that all open a dialog about this page, so
                they read as one segmented control rather than four rivals. */}
            <div className={styles.tbGroup}>
              <button type="button" className={styles.tbAction} onClick={() => setIsRenaming(true)}>
                <Pencil size={13} /> Переименовать
              </button>
              <button
                type="button"
                className={styles.tbAction}
                onClick={() => setIsHistoryOpen(true)}
              >
                <History size={13} /> Версии
              </button>
              {/* A lecture carries its own ACL. Managing it only from the
                  folder — which is all this used to offer — cannot express
                  "this one lecture is open to another group", since a resource
                  resolves at the first matching level (docs/access.md). */}
              <button
                type="button"
                className={styles.tbAction}
                onClick={() => setIsAccessOpen(true)}
              >
                <Users size={13} /> Доступ
              </button>
              {/* Sources and provenance marks are what a report counts, and
                  the report is per revision — so it lives next to «Версии». */}
              <button
                type="button"
                className={styles.tbAction}
                onClick={() => setIsSourcesOpen(true)}
              >
                <BookMarked size={13} /> Источники
              </button>
            </div>

            <span className={styles.tbDivider} />

            {/* Icon-only and behind a divider: a destructive action does not
                belong at the same width and weight as "Переименовать", a
                pixel away from it. */}
            <button
              type="button"
              className={cn(styles.tbAction, styles.tbIconOnly, styles.tbActionDanger)}
              onClick={() => void handleDelete()}
              disabled={deletePage.isPending}
              title="Удалить материал"
              aria-label="Удалить материал"
            >
              <Trash2 size={13} />
            </button>
          </div>

          <button
            type="button"
            className={styles.toolbarMore}
            aria-haspopup="dialog"
            onClick={() => setIsMoreOpen(true)}
          >
            <MoreHorizontal size={15} /> Ещё
          </button>

          <Dialog
            open={isMoreOpen}
            title="Действия с материалом"
            size="sheet"
            onClose={() => setIsMoreOpen(false)}
          >
            <div className={styles.sheetActions}>
              <button
                type="button"
                className={styles.sheetAction}
                onClick={() => {
                  setIsMoreOpen(false);
                  setIsRenaming(true);
                }}
              >
                <Pencil size={16} /> Переименовать
              </button>
              <button
                type="button"
                className={styles.sheetAction}
                onClick={() => {
                  setIsMoreOpen(false);
                  setIsHistoryOpen(true);
                }}
              >
                <History size={16} /> Версии
              </button>
              <button
                type="button"
                className={styles.sheetAction}
                onClick={() => {
                  setIsMoreOpen(false);
                  setIsAccessOpen(true);
                }}
              >
                <Users size={16} /> Доступ
              </button>
              <button
                type="button"
                className={styles.sheetAction}
                onClick={() => {
                  setIsMoreOpen(false);
                  setIsSourcesOpen(true);
                }}
              >
                <BookMarked size={16} /> Источники
              </button>
              <button
                type="button"
                className={cn(styles.sheetAction, styles.sheetActionDanger)}
                disabled={deletePage.isPending}
                onClick={() => {
                  setIsMoreOpen(false);
                  void handleDelete();
                }}
              >
                <Trash2 size={16} /> Удалить
              </button>
            </div>
          </Dialog>
        </>
      )}

      <TextInputDialog
        open={isRenaming}
        title="Переименовать материал"
        label="Название"
        initialValue={pageName}
        isPending={renamePage.isPending}
        error={renamePage.error ? describeWsError(renamePage.error) : null}
        onClose={() => {
          setIsRenaming(false);
          renamePage.reset();
        }}
        onSubmit={async (name) => {
          await renamePage.mutateAsync({ pageId, folderId, name });
          setIsRenaming(false);
        }}
      />

      {isHistoryOpen && (
        <PageHistory
          open
          page={page}
          draftBlocks={draftBlocks}
          onClose={() => setIsHistoryOpen(false)}
        />
      )}

      {isSourcesOpen && (
        <SourcesPanel
          open
          pageId={pageId}
          pageName={pageName}
          canEdit={canEdit}
          revisions={history.revisions}
          onClose={() => setIsSourcesOpen(false)}
        />
      )}

      {isAccessOpen && (
        <AccessPanel
          open
          resourceType="page"
          resourceId={pageId}
          resourceName={pageName}
          // `page.open` reports this page's own effective_role, and this
          // toolbar only renders for someone who can edit it.
          viewerRole={viewerRole}
          onClose={() => setIsAccessOpen(false)}
        />
      )}
    </div>
  );
}

/**
 * Uploads a file (`POST /files/upload`) and records it on the page as an
 * attachment block.
 *
 * The block is the whole point: uploading alone does *not* make the file show
 * up in `page.open`'s `resources` — that field is always empty (see
 * materials.attachments.ts for the evidence), which is why attached files
 * used to disappear as soon as you left the lecture.
 */
function FileUploadButton({ pageId, blocks }: { pageId: string; blocks: BlockData[] }) {
  const createBlock = useCreateBlock();
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setIsUploading(true);
    setError(null);
    try {
      const uploaded = await uploadFile({
        file,
        resourceType: 'page',
        resourceId: pageId,
        behavior: 'download',
      });
      if (!uploaded) {
        setError('Файл загружен, но сервер не вернул его идентификатор.');
        return;
      }
      await createBlock.mutateAsync({
        pageId,
        blockType: ATTACHMENT_BLOCK_TYPE,
        zone: ATTACHMENT_ZONE,
        data: attachmentBlockData(uploaded),
        orderKey: nextOrderKey(blocks),
      });
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Не удалось загрузить файл');
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <label className={styles.uploadButton}>
      <UploadCloud size={14} />
      {isUploading ? 'Загрузка…' : 'Прикрепить файл'}
      <input
        type="file"
        className={styles.uploadInput}
        onChange={(e) => void handleFileChange(e)}
        disabled={isUploading}
      />
      {error && <span className={styles.formError}>{error}</span>}
    </label>
  );
}

function LectureContent({
  folderId,
  folderName,
  folderChildren,
  page,
  canEdit,
  tab,
  isNotesOpen,
  isNotesFloating,
  onToggleNotes,
}: {
  folderId: string;
  folderName: string;
  folderChildren: FolderChildData[];
  page: PageOpenResult;
  canEdit: boolean;
  tab: MaterialsTab;
  /** Notes-column state, owned by the page — the column is its grid sibling. */
  isNotesOpen: boolean;
  isNotesFloating: boolean;
  onToggleNotes: () => void;
}) {
  // Readers get the published snapshot, editors the live draft. page.open
  // always returns the draft — see use-page-publication.ts for the measurement
  // that shows a reader would otherwise be served unpublished text.
  const publishedRevision = usePublishedRevision(
    page.page.published_revision_id,
    page.page.published_revision_id !== null,
  );
  const snapshot = readSnapshot(publishedRevision.revision);

  /*
   * Документ страницы — единственный источник того, что на экране у автора.
   *
   * Сервер отдаёт блоки в `page.blocks`; документ кладёт поверх всё, что автор
   * уже сделал, но подтверждения ещё нет. Читателю он не нужен: тот смотрит
   * опубликованный снимок и ничего не правит.
   */
  const serverBlocks = useMemo(() => toDocBlocks(page.blocks), [page.blocks]);
  const { engine, blocks: docBlocks } = usePageDoc(page.page.id, serverBlocks, canEdit);
  const liveBlocks = useMemo(() => toBlockDataList(docBlocks), [docBlocks]);
  const view = canEdit ? { page: page.page, blocks: liveBlocks } : snapshot;

  // One page carries every tab's content, separated by block zone — see
  // materials.zones.ts.
  const zones = splitPageZones(view?.blocks ?? []);
  const { content: contentBlocks, attachments } = zones;
  const deleteBlock = useDeleteBlock();

  function handleRemoveAttachment(block: BlockData) {
    const attachment = readAttachment(block);
    if (!window.confirm(`Убрать файл «${attachment?.name ?? ''}» из лекции?`)) return;
    void deleteBlock.mutateAsync({
      pageId: page.page.id,
      blockId: block.id,
      expectedVersion: block.block_version,
    });
  }

  const navData = buildLectureNavData(folderId, folderChildren, page.page.id);
  // `page.resources` is always [] in practice (see materials.attachments.ts);
  // it's still passed through so the banner's pre-icon_name fallback keeps
  // working and so this starts populating for free if the field is ever
  // implemented server-side.
  // The name/description/banner a reader sees come from the snapshot too —
  // an unpublished rename would otherwise leak through the hero.
  const shown = view?.page ?? page.page;
  const banner = useBannerImage(shown, page.resources);
  // Лаба — не лекция: у неё свои вкладки, подписи и нижняя навигация.
  const isLab = shown.kind === 'lab';
  const isNormocontrol = shown.kind === 'normocontrol';

  // Отметка о заходе (её же читает палитра по Ctrl+K) и место, до которого
  // дочитали. Только на вкладке лекции: на «файлах» возвращаться некуда.
  const reading = useReadingPosition({
    id: page.page.id,
    folderId,
    name: shown.name,
    folderName,
    kind: isLab ? 'lab' : 'page',
    enabled: tab === 'lecture',
  });

  // Built once — the sidebar card and the "Файлы" tab show the same list.
  const files = buildAttachmentFiles(
    attachments,
    page.resources,
    canEdit ? handleRemoveAttachment : null,
  );
  const uploadSlot = canEdit ? (
    <FileUploadButton pageId={page.page.id} blocks={attachments} />
  ) : undefined;
  const downloads = buildPageDownloads(page.resources);
  const pageSources = usePageSources(page.page.id, tab === 'lecture');
  const externalLinks = buildExternalLinks(pageSources.sources);
  const tocItems = buildTocItems(contentBlocks);
  const tocPanel = useFloatingPanel({ storageKey: 'materials.tocDockPosition' });
  const isNarrowLecture = useMediaQuery('(max-width: 768px)');
  const tocIsFloating = tocPanel.isFloating;
  const toggleTocFloating = tocPanel.toggleFloating;
  useEffect(() => {
    if (isNarrowLecture && tocIsFloating) toggleTocFloating();
  }, [isNarrowLecture, tocIsFloating, toggleTocFloating]);
  const hasFilesCard = files.length > 0 || uploadSlot !== undefined;
  const hasLinksCard = pageSources.isPending || pageSources.isError || externalLinks.length > 0;
  const hasSidebarFlowContent =
    (tocItems.length > 0 && !tocPanel.isFloating) || hasFilesCard || hasLinksCard;

  // A reader whose snapshot hasn't arrived (or didn't parse) gets a state
  // screen, never the draft.
  if (!canEdit && !view) {
    return publishedRevision.isPending ? (
      <div className={styles.stateScoped}>
        <Spinner label="Загрузка материала…" />
      </div>
    ) : (
      <StateScreen
        title="Не удалось загрузить опубликованную версию"
        description={
          publishedRevision.isError
            ? describeWsError(publishedRevision.error)
            : 'Сервер вернул снимок страницы в неожиданном виде.'
        }
        scoped
      />
    );
  }

  return (
    <DocScope engine={engine}>
      {reading.canResume && (
        <ResumeReading
          scroll={reading.savedScroll}
          onResume={reading.resume}
          onDismiss={reading.dismiss}
        />
      )}
      <CourseHero
        // Carries the page kind now that the second heading is gone — it was
        // the only thing that header said which the hero didn't.
        eyebrow={`${folderName} · ${pageKindLabel(shown.kind)}`}
        titleLine1={shown.name}
        description={shown.description ?? undefined}
        // Автор приезжает вместе со страницей: отдельным запросом его не
        // достать — `system.users.get` требует прав администратора, и у
        // студента, открывшего лекцию, он бы не отработал.
        author={
          page.page.author
            ? {
                id: page.page.author.id,
                username: page.page.author.username,
                displayName: page.page.author.display_name,
                avatarId: page.page.author.avatar_id ?? null,
              }
            : undefined
        }
        backgroundImageUrl={banner.imageUrl}
        bannerControl={
          canEdit ? (
            <BannerUploadControl
              hasManualBanner={banner.hasManualBanner}
              isUploading={banner.isUploading}
              error={banner.error}
              onFileChange={(event) => void banner.onFileChange(event)}
            />
          ) : undefined
        }
      />

      {/* The toolbar row now always renders: the notes toggle belongs to every
          reader, not only to editors and pages carrying a download. */}
      <div className={styles.pageToolbarWrap}>
        {/* Publishing state lives in PublishControl now — a banner above it
            saying the same thing was pure noise. */}
        <PageToolbar
          page={page.page}
          folderId={folderId}
          draftBlocks={page.blocks}
          publishedRevision={publishedRevision.revision}
          downloads={downloads}
          canEdit={canEdit}
          viewerRole={page.effective_role}
          isNotesOpen={isNotesOpen}
          onToggleNotes={onToggleNotes}
        />
      </div>

      <div className={styles.tabsRow}>
        <TabsBar
          tabs={buildTabItems(
            folderId,
            page.page.id,
            tab,
            { files: files.length, discussion: undefined },
            shown.kind,
          )}
        />
      </div>

      <div className={styles.lectureArea}>
        {tab === 'lecture' && (
          <div
            className={cn(
              styles.lectureContent,
              !hasSidebarFlowContent && styles.lectureContentWide,
            )}
          >
            <div className={styles.lectureColumn}>
              <div className={styles.lectureText}>
                {canEdit ? (
                  <PageEditor blocks={contentBlocks} pageId={page.page.id} />
                ) : (
                  <BlockRenderer blocks={contentBlocks} pageId={page.page.id} />
                )}
                {/* У лабы условие может быть ещё не написано, и пустая
                    карточка ничего об этом не говорит. */}
                {isLab && contentBlocks.length === 0 && !canEdit && (
                  <p className={styles.emptyTask}>
                    Преподаватель ещё не описал задание. Сдать работу можно и так.
                  </p>
                )}
              </div>

              {/* Соседом, а не внутри карточки условия: условие — это текст
                  задания, а сдача — отдельная работа над ним. Вложенные друг в
                  друга карточки и делали экран разнородным. */}
              {isLab && (
                <LabPanel
                  pageId={page.page.id}
                  canGrade={canManageAccess(page.effective_role)}
                  canEdit={canEdit}
                />
              )}

              {/* Тоже соседом, а не внутри условия: текст материала — это
                  объяснение, а проверка — работа над своим документом. */}
              {isNormocontrol && <NormocontrolPanel pageId={page.page.id} canEdit={canEdit} />}
            </div>

            {/*
              На телефоне те же панели уезжают в выдвижную — от правого края,
              как в оболочке Samsung. Иначе содержание лекции оказывается в
              самом низу страницы, за всем её текстом: чтобы перейти к разделу,
              нужно сначала прокрутить лекцию целиком.
            */}
            {isNarrowLecture ? (
              hasSidebarFlowContent && (
                <EdgePanel title={isLab ? 'Задание' : 'Лекция'} handleLabel="Содержание">
                  <LectureSidebar
                    tocTitle={isLab ? 'Содержание задания' : 'Содержание лекции'}
                    toc={tocItems}
                    filesTitle={isLab ? 'Материалы к заданию' : 'Файлы к лекции'}
                    files={files}
                    linksTitle="Внешние ссылки"
                    links={externalLinks}
                    linksPending={pageSources.isPending}
                    linksError={pageSources.isError}
                    tocPanel={tocPanel}
                    hasFlowContent={hasSidebarFlowContent}
                    avoidFloatingNotes={isNotesFloating}
                    uploadSlot={uploadSlot}
                  />
                </EdgePanel>
              )
            ) : (
              <LectureSidebar
                tocTitle={isLab ? 'Содержание задания' : 'Содержание лекции'}
                toc={tocItems}
                filesTitle={isLab ? 'Материалы к заданию' : 'Файлы к лекции'}
                files={files}
                linksTitle="Внешние ссылки"
                links={externalLinks}
                linksPending={pageSources.isPending}
                linksError={pageSources.isError}
                tocPanel={tocPanel}
                hasFlowContent={hasSidebarFlowContent}
                avoidFloatingNotes={isNotesFloating}
                uploadSlot={uploadSlot}
              />
            )}
          </div>
        )}

        {tab === 'notes' && (
          <LectureNotes pageId={page.page.id} summaryBlocks={zones.summary} canEdit={canEdit} />
        )}

        {tab === 'files' && <LectureFiles files={files} uploadSlot={uploadSlot} />}

        {tab === 'test' && (
          <LectureTest
            pageId={page.page.id}
            folderId={folderId}
            testBlocks={zones.test}
            canEdit={canEdit}
          />
        )}

        {tab === 'discussion' && <LectureDiscussion pageId={page.page.id} />}
      </div>

      {tab === 'lecture' && navData && (
        <LectureNav
          prev={navData.prev}
          next={navData.next}
          dots={navData.dots}
          unitLabel={isLab ? 'Работа' : 'Лекция'}
          current={navData.current}
          total={navData.total}
        />
      )}
    </DocScope>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function MaterialsPage(_props: MaterialsPageProps) {
  const { folderId, pageId, tab } = useParams<'folderId' | 'pageId' | 'tab'>();
  const activeTab = resolveTab(tab);

  // Route-param presence is handled inside queryFn: resolve to `null` without
  // calling the action at all when the id isn't in the URL yet. useWsQuery
  // does accept an `enabled` option (it ANDs it with its own socket-ready
  // check), but gating that way would leave the query permanently `pending`
  // with `data === undefined` — resolving to `null` instead gives this
  // component a settled value it can branch on.
  const folderQuery = useWsQuery(['materials', 'folder.open', folderId], async (wsClient) => {
    if (!folderId) return null;
    return wsClient.actions.folder.open({ folder_id: folderId });
  });

  const pageQuery = useWsQuery(['materials', 'page.open', pageId], async (wsClient) => {
    if (!pageId) return null;
    return wsClient.actions.page.open({ page_id: pageId });
  });

  // Personal folders are named by their owner's user id and carry nothing
  // else about them, so every uuid-named folder in play — the children, the
  // breadcrumb trail and the open folder itself — is resolved to a person up
  // front. Called before the early returns below to keep hook order fixed;
  // an undefined `data` simply yields an empty id list and no requests.
  const openFolder = folderQuery.data;
  const personalUserIds = collectPersonalFolderUserIds(
    openFolder ? [...openFolder.children, ...openFolder.breadcrumbs, openFolder.folder] : [],
  );
  const directory = useUserDirectory(personalUserIds);

  // folder.open / page.open subscribed this connection to the folder's and
  // page's change events; this is what listens to them.
  useMaterialsRealtime(folderId, pageId);

  const canEditFolder = openFolder ? canEditResource(openFolder.effective_role) : false;

  /*
   * Mobile only: the section tree is a drawer below the tablet breakpoint.
   *
   * It closes when a *page* opens, not on every navigation. Walking down
   * folders is still browsing — closing the drawer each time meant reopening
   * it at every level, which on a deep tree is most of the taps.
   */
  /*
   * The tree is the only sensible shape on a phone — a flat list of one folder
   * means reopening the drawer at every level — so below the tablet width it
   * is forced on. Above it the flat list stays the default and the toggle
   * beside the course name opts in.
   *
   * Decided in JS rather than CSS because the two are different component
   * trees, not two skins: rendering both would mean a second set of queries
   * for a panel only one of which is on screen.
   */
  const [isTreeView, setIsTreeView] = useTreeMode();
  const isNarrow = useMediaQuery('(max-width: 768px)');
  const showTree = isTreeView || isNarrow;
  const [isTreeOpen, setIsTreeOpen] = useState(false);
  useEffect(() => {
    if (pageId) setIsTreeOpen(false);
  }, [pageId]);

  /*
   * Readers must not be offered unpublished lectures, and `hidden`/`blocked`
   * children have to be dropped or marked. The state isn't on FolderChild, so
   * it costs one `page.open` per child — which is why it is gated on the flat
   * list actually being on screen. When the tree is showing, the same reads
   * happen inside it, per branch; doing both would double the fan-out and, on
   * a phone, spend the session's action budget on a list nobody can see.
   * See use-child-visibility.ts and use-page-publication.ts.
   */
  const visibility = useChildVisibility(
    openFolder?.children ?? [],
    canEditFolder,
    openFolder !== undefined && !showTree,
  );

  // Right-click / long-press actions for the rows, shared by the flat list and
  // the tree so the two cannot offer different things.
  const resourceMenu = useResourceMenu();

  // Desktop only in effect: the handle that sets this is hidden below 1024px,
  // where the sidebar stops being a column at all.
  const sidebar = useSidebarWidth();
  const coursePanel = useFloatingPanel({ storageKey: 'materials.courseSidebarPosition' });

  /*
   * The notes column. Owned here rather than inside LectureContent because it
   * is a child of `.page` — the grid that spans the viewport — and not of
   * `main`. Nested in `main` its sticky offset was measured from the wrong
   * containing block, which left a gap above it and cut it short below.
   */
  const [isNotesOpen, setIsNotesOpen] = useNotesPanelOpen();
  const notesWidth = useResizableWidth({
    storageKey: 'materials.notesPanelWidth',
    min: NOTES_PANEL_MIN,
    max: NOTES_PANEL_MAX,
    initial: NOTES_PANEL_DEFAULT,
    cssVar: '--notes-w',
    // The handle sits on the panel's *leading* edge, so dragging right narrows.
    direction: 'end',
  });
  const notesPanel = useFloatingPanel({ storageKey: 'materials.notesPanelPosition' });

  // Which crumbs are actually openable — see the hook for why `breadcrumbs`
  // alone cannot answer that.
  const reachable = useReachableAncestors(openFolder?.breadcrumbs ?? []);

  // A shortcut folder answers `folder.open` with the folder it stands for; the
  // client is the one that has to follow it.
  const isRedirecting = useFolderRedirect(openFolder?.redirect_target_id, folderId);

  // Deleting a test is irreversible — there is no `test.restore` to match
  // `folder.restore` / `page.restore` — so it always asks first.
  const deleteTest = useDeleteTest();
  const handleDeleteTest = useCallback(
    (testId: string, name: string) => {
      if (
        !window.confirm(
          `Удалить тест «${name}» со всеми вопросами и попытками? Отменить это нельзя.`,
        )
      ) {
        return;
      }
      deleteTest.mutate({ testId, folderId });
    },
    [deleteTest, folderId],
  );

  const navLinks = usePrimaryNavLinks();

  if (!folderId) {
    return <CoursePickerScreen />;
  }

  // A shortcut has no contents of its own; rendering it for a frame before the
  // redirect lands would flash an empty section.
  if (folderQuery.isPending || isRedirecting) {
    return (
      <PageShell navLinks={navLinks}>
        <Spinner fullHeight label={isRedirecting ? 'Переход к разделу…' : 'Загрузка раздела…'} />
      </PageShell>
    );
  }

  if (folderQuery.isError) {
    return (
      <PageShell navLinks={navLinks}>
        <StateScreen
          title="Не удалось загрузить раздел"
          description={describeWsError(folderQuery.error)}
          onRetry={() => void folderQuery.refetch()}
        />
      </PageShell>
    );
  }

  const folderData = folderQuery.data;
  if (!folderData) {
    return (
      <PageShell navLinks={navLinks}>
        <StateScreen title="Раздел не найден" description="Сервер не вернул данные раздела." />
      </PageShell>
    );
  }

  // `breadcrumbs` includes the current folder itself (confirmed by the root
  // folder rendering as its own crumb twice) — drop that self-reference and
  // re-add the folder exactly once, either as a link (when a page is open
  // beyond it) or as `current` (see breadcrumbCurrent below).
  const ancestorFolders = folderData.breadcrumbs.filter((b) => b.id !== folderData.folder.id);
  const ancestors: FolderData[] = [...ancestorFolders, folderData.folder];
  /*
   * Where the section tree starts.
   *
   * Not `ancestorFolders[0]`: `breadcrumbs` runs all the way back to the
   * workspace root whatever the viewer's access is, so for anyone whose grant
   * sits partway down the chain that first crumb is a folder `folder.open`
   * refuses — and a tree rooted there renders its header and nothing else,
   * while the flat list beside it works fine. `topReachable` is the highest
   * crumb the viewer may actually open; the current folder is the fallback for
   * the window before the entrypoints are known.
   */
  const rootAncestor = reachable.topReachable ?? folderData.folder;

  const users = directory.users;
  /*
   * One condition drives both halves on purpose.
   *
   * They used to disagree: the links included the folder whenever `pageId` was
   * in the URL, while the trailing crumb fell back to the folder's own name
   * when the page had not loaded. A page that 404s — which is exactly what a
   * shortcut opened as a page did — therefore rendered the folder twice in a
   * row. With no page to show, the trail is the folder's own.
   */
  const openPage = pageId ? (pageQuery.data ?? null) : null;
  const breadcrumbLinks = openPage
    ? buildBreadcrumbLinks(ancestors, users, reachable.isReachable)
    : buildBreadcrumbLinks(ancestorFolders, users, reachable.isReachable);
  const breadcrumbCurrent = openPage
    ? displayFolderName(openPage.page.name)
    : folderDisplayName(folderData.folder.name, users);
  const canEdit = canEditResource(folderData.effective_role);
  /*
   * The open page's own role, which is not always the folder's.
   *
   * ACLs are per-resource and resolve at the first level that matches (see
   * docs/access.md), so a personal invite or a group condition set on the page
   * itself can grant more than the folder does. Deciding this from the folder
   * alone sent anyone holding such a grant down the reader path, where a page
   * with no published revision renders as "снята с публикации" — for a person
   * who is in fact its editor. The folder's role remains the fallback for the
   * window before `page.open` answers.
   */
  const canEditPage = openPage ? canEditResource(openPage.effective_role) || canEdit : canEdit;
  const folderLabel = folderDisplayName(folderData.folder.name, users);
  // A container of nothing but personal folders is the user registry — it
  // gets the directory view instead of the "pick something on the left"
  // landing, which has nothing useful to offer here.
  const showUserDirectory = !pageId && isUserDirectoryFolder(folderData.children);

  /*
   * Non-null when the open page is a private notes page, holding the id of the
   * lecture it annotates. Read from `icon_name`, which is where the pairing
   * lives — see NOTES_ICON_PREFIX for why it is not in the name.
   */
  const notesLectureId = openPage ? notesLecturePageId(openPage.page.icon_name) : null;
  const notesCanOpen = isNotesOpen && Boolean(pageId) && notesLectureId === null;
  const courseIsFloating = coursePanel.isFloating && !isNarrow;
  const notesAreFloating = notesCanOpen && notesPanel.isFloating;

  /**
   * A sidebar row id back to everything its menu needs.
   *
   * The narrowing of `folderData` and `folderId` established by the guards
   * above does not reach inside a function declaration, so both are captured
   * here rather than re-read.
   */
  const menuChildren = folderData.children;
  const menuFolderId = folderId;
  function menuTargetFor(childId: string): ResourceMenuTarget | null {
    const child = menuChildren.find((candidate) => candidate.id === childId);
    if (!child) return null;
    return {
      id: child.id,
      name: child.name,
      kind: child.kind,
      parentFolderId: menuFolderId,
      role: visibility.roles.get(child.id) ?? null,
      canEditParent: canEdit,
      blocked: visibility.isBlocked(child.id),
    };
  }

  return (
    <PageShell navLinks={navLinks}>
      {/* One instance for the whole page: the popover and its dialogs are
          shared by the tree and the flat list. */}
      {resourceMenu.element}

      <div
        // Both resizers write their custom property to this one element, so
        // both refs point at it.
        ref={(node) => {
          sidebar.containerRef.current = node;
          notesWidth.containerRef.current = node;
        }}
        className={cn(
          styles.page,
          isTreeOpen && styles.pageTreeOpen,
          (sidebar.isDragging || notesWidth.isDragging) && styles.pageResizing,
          courseIsFloating && styles.pageSidebarFloating,
          notesCanOpen && !notesAreFloating && styles.pageWithNotes,
        )}
        // The committed widths only. During a drag each hook writes its own
        // property straight to the node, once per animation frame, so the
        // column tracks the cursor without re-rendering the page beneath it.
        style={
          {
            '--sidebar-w': `${sidebar.width}px`,
            '--notes-w': `${notesWidth.width}px`,
          } as CSSProperties
        }
      >
        <Breadcrumb
          links={breadcrumbLinks}
          current={breadcrumbCurrent}
          leading={
            // Shares the trail's row rather than claiming one of its own —
            // navigation controls belong together, and a phone has no vertical
            // space to spend on a lone button.
            <button
              type="button"
              className={styles.treeToggle}
              aria-label={isTreeOpen ? 'Закрыть содержание' : 'Открыть содержание'}
              aria-expanded={isTreeOpen}
              onClick={() => setIsTreeOpen((open) => !open)}
            >
              {isTreeOpen ? <X size={16} /> : <PanelLeft size={16} />}
            </button>
          }
        />

        {/* Closes the drawer by tapping the dimmed page behind it. */}
        {isTreeOpen && (
          <button
            type="button"
            className={styles.treeScrim}
            aria-label="Закрыть содержание"
            onClick={() => setIsTreeOpen(false)}
          />
        )}

        <CourseSidebar
          // Carries the grid placement and drawer styling. Keyed to a class
          // rather than `.page > aside`, which also matched the notes panel
          // and handed it this column.
          className={styles.sectionColumn}
          // On a phone this is the existing modal drawer. Omitting the
          // controller also omits its saved inline position, so the drawer's
          // left edge remains authoritative while preserving desktop state.
          floatingPanel={isNarrow ? undefined : coursePanel}
          eyebrow={folderDisplayName(rootAncestor.name, users)}
          courseName={folderLabel}
          viewToggle={
            <button
              type="button"
              className={styles.viewToggle}
              aria-pressed={isTreeView}
              title={isTreeView ? 'Показать только этот раздел' : 'Показать дерево разделов'}
              aria-label={isTreeView ? 'Показать только этот раздел' : 'Показать дерево разделов'}
              onClick={() => setIsTreeView(!isTreeView)}
            >
              {isTreeView ? <List size={14} /> : <ListTree size={14} />}
            </button>
          }
          tree={
            showTree ? (
              <FolderTree
                rootId={rootAncestor.id}
                rootName={folderDisplayName(rootAncestor.name, users)}
                currentFolderId={folderId}
                currentPageId={pageId}
                /* Only the part of the path at or below the tree's root.
                   Auto-expanding a crumb above it would fire a `folder.open`
                   the viewer is not allowed to make. */
                ancestorIds={ancestors
                  .filter((folder) => reachable.isReachable(folder.id))
                  .map((folder) => folder.id)}
                canEdit={canEdit}
                menu={resourceMenu}
              />
            ) : undefined
          }
          sections={buildSidebarSections(
            folderId,
            pageId,
            users,
            visibility,
            canEdit,
            handleDeleteTest,
          )}
          onOpenItemMenu={(itemId, point) => {
            const target = menuTargetFor(itemId);
            if (target) resourceMenu.openAt(point, target);
          }}
          onItemContextMenu={(itemId, event) => {
            const target = menuTargetFor(itemId);
            if (target) resourceMenu.onContextMenu(event, target);
          }}
          pinControl={
            <PinButton resourceType="folder" resourceId={folderId} resourceName={folderLabel} />
          }
          toolbar={
            canEdit ? (
              <SidebarToolbar
                folderId={folderId}
                parentId={folderData.folder.parent_id}
                folderName={folderData.folder.name}
                folderLabel={folderLabel}
                folderChildren={folderData.children}
                viewerRole={folderData.effective_role}
              />
            ) : undefined
          }
        />

        {/*
          Drag to resize the sidebar. A `separator` with `aria-valuenow` is the
          role a resize handle is expected to carry, and it is focusable so the
          arrow keys in useSidebarWidth are reachable without a pointer.
          Hidden by CSS below the tablet breakpoint, where the sidebar is a
          drawer and a dragged width means nothing.
        */}
        <button
          type="button"
          className={cn(
            styles.sidebarHandle,
            courseIsFloating && styles.sidebarHandleHidden,
            sidebar.isDragging && styles.sidebarHandleActive,
          )}
          // eslint-disable-next-line jsx-a11y/prefer-tag-over-role -- an <hr> is neither focusable nor operable, and this handle answers the arrow keys; a focusable `separator` with aria-valuenow is the window-splitter pattern
          role="separator"
          aria-orientation="vertical"
          aria-label="Ширина боковой панели"
          aria-valuenow={sidebar.width}
          aria-valuemin={SIDEBAR_MIN}
          aria-valuemax={SIDEBAR_MAX}
          title="Потяните, чтобы изменить ширину. Двойной клик — вернуть по умолчанию."
          onPointerDown={sidebar.onPointerDown}
          onKeyDown={sidebar.onKeyDown}
          onDoubleClick={sidebar.onDoubleClick}
        />

        <main className={styles.main}>
          <DeletedResourceNotice parentFolderId={folderId} />

          {showUserDirectory && (
            <UserDirectory
              title={folderLabel}
              entries={buildUserDirectoryEntries(folderId, folderData.children, users)}
              isPending={directory.isPending}
              unresolvedCount={directory.unresolvedCount}
              canManage={canEdit}
            />
          )}

          {!pageId && !showUserDirectory && (
            <FolderLanding folder={folderData.folder} title={folderLabel} />
          )}

          {pageId && pageQuery.isPending && (
            <div className={styles.stateScoped}>
              <Spinner label="Загрузка материала…" />
            </div>
          )}

          {pageId && pageQuery.isError && (
            <StateScreen
              title="Не удалось загрузить материал"
              description={describeWsError(pageQuery.error)}
              onRetry={() => void pageQuery.refetch()}
              scoped
            />
          )}

          {/* Private notes get their own view. They are `document` pages in a
              personal folder, so the lecture layout below would otherwise wrap
              them in publishing controls, a tab bar and a files card — none of
              which mean anything for a note only its author can see. */}
          {pageId && pageQuery.data && notesLectureId !== null && (
            <NotesPage page={pageQuery.data} folderId={folderId} lecturePageId={notesLectureId} />
          )}

          {/* Unpublished lectures are not shown to readers. The server sends
              the draft anyway (see use-page-publication.ts), so this hides
              it from the page, not from the network. */}
          {/* `blocked` is an explicit denial: the resource is still shown, but
              marked unavailable rather than quietly emptied. */}
          {pageId &&
            pageQuery.data &&
            notesLectureId === null &&
            isBlockedRole(pageQuery.data.effective_role) && (
              <StateScreen
                title="Материал недоступен"
                description="Для вас закрыт доступ к этому материалу."
                scoped
              />
            )}

          {pageId &&
            pageQuery.data &&
            notesLectureId === null &&
            !isBlockedRole(pageQuery.data.effective_role) &&
            !canEditPage &&
            !isPagePublished(pageQuery.data.page) && (
              <StateScreen
                title="Лекция снята с публикации"
                description="Преподаватель временно закрыл доступ к этому материалу."
                scoped
              />
            )}

          {pageId &&
            pageQuery.data &&
            notesLectureId === null &&
            !isBlockedRole(pageQuery.data.effective_role) &&
            (canEditPage || isPagePublished(pageQuery.data.page)) && (
              <LectureContent
                folderId={folderId}
                folderName={folderLabel}
                folderChildren={folderData.children}
                page={pageQuery.data}
                canEdit={canEditPage}
                tab={activeTab}
                isNotesOpen={isNotesOpen}
                isNotesFloating={notesAreFloating}
                onToggleNotes={() => setIsNotesOpen(!isNotesOpen)}
              />
            )}
        </main>

        {/* A third grid column, beside `main` rather than inside it — the
            sticky offsets only line up against `.page`, which spans the
            viewport. Only for an open material: there is nothing to annotate
            on a folder landing. */}
        {/* Never on a notes page itself — notes about your notes. */}
        {isNotesOpen && pageId && pageQuery.data && notesLectureId === null && (
          <NotesPanel
            className={styles.notesColumn}
            floatingPanel={notesPanel}
            lecturePageId={pageId}
            lectureName={pageQuery.data.page.name}
            onClose={() => setIsNotesOpen(false)}
            size={notesWidth}
          />
        )}
      </div>
    </PageShell>
  );
}
