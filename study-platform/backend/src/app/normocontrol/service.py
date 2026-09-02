"""Материал нормоконтроля: постановка в очередь, чтение, права."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access.enums import ResourceType, Role
from app.access.service import AccessService
from app.audit.service import add_audit_event
from app.config import Settings, get_settings
from app.files.models import FileAttachment, StoredFile
from app.normocontrol.enums import (
    RUN_RESOURCE_TYPE,
    FailureReason,
    RunStatus,
)
from app.normocontrol.models import (
    NormocontrolCheck,
    NormocontrolRun,
    NormocontrolSettings,
)
from app.normocontrol.schemas import (
    NormocontrolAuthorOutput,
    NormocontrolCategoryOutput,
    NormocontrolReportOutput,
    NormocontrolRunOutput,
    NormocontrolSettingsInput,
    NormocontrolSettingsOutput,
)
from app.pages.models import Page
from app.users.models import User

READ_ROLES = {Role.OWNER, Role.EDITOR, Role.CONTROLLER, Role.STUDENT}
EDIT_ROLES = {Role.OWNER, Role.EDITOR}
#: Кто может видеть чужие проверки внутри материала.
REVIEW_ROLES = {Role.OWNER, Role.EDITOR, Role.CONTROLLER}
PAGE_KIND = "normocontrol"
HISTORY_LIMIT = 50


class NormocontrolService:
    def __init__(
        self,
        db: AsyncSession,
        access: AccessService,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.access = access
        self.settings = settings or get_settings()

    # --- страница и настройки -------------------------------------------

    async def _page(self, user_id: UUID, page_id: UUID, roles: set[Role]) -> Page:
        page = await self.db.scalar(
            select(Page).where(Page.id == page_id, Page.deleted_at.is_(None))
        )
        if page is None:
            raise LookupError("Page not found")
        if page.kind != PAGE_KIND:
            raise ValueError("Page is not a normocontrol material")
        await self.access.require_at_least(user_id, ResourceType.PAGE, page.id, roles)
        return page

    async def _settings_row(
        self, page_id: UUID
    ) -> tuple[NormocontrolSettings, bool]:
        row = await self.db.get(NormocontrolSettings, page_id)
        if row is not None:
            return row, True
        # Умолчания колонок SQLAlchemy проставляет при вставке, а этот объект в
        # базу не попадает: без явного значения `accepting` был бы None, и
        # ненастроенный материал молча перестал бы принимать документы.
        return NormocontrolSettings(page_id=page_id, accepting=True), False

    def _settings_output(
        self, row: NormocontrolSettings, configured: bool
    ) -> NormocontrolSettingsOutput:
        # Умолчания колонок проставляются при вставке, а сюда объект приходит и
        # до неё — материал мог быть создан, но не настроен.
        return NormocontrolSettingsOutput(
            page_id=row.page_id,
            instructions=row.instructions,
            accepting=True if row.accepting is None else bool(row.accepting),
            configured=configured,
            allowed_extensions=list(self.settings.normocontrol_allowed_extensions),
            max_file_size=self.settings.normocontrol_max_file_size,
        )

    async def get_settings(
        self, user_id: UUID, page_id: UUID
    ) -> NormocontrolSettingsOutput:
        await self._page(user_id, page_id, READ_ROLES)
        row, configured = await self._settings_row(page_id)
        return self._settings_output(row, configured)

    async def set_settings(
        self, user_id: UUID, session_id: UUID, data: NormocontrolSettingsInput
    ) -> NormocontrolSettingsOutput:
        await self._page(user_id, data.page_id, EDIT_ROLES)
        row = await self.db.get(NormocontrolSettings, data.page_id)
        if row is None:
            row = NormocontrolSettings(page_id=data.page_id)
            self.db.add(row)
        row.instructions = data.instructions
        row.accepting = data.accepting
        row.updated_at = datetime.now(UTC)
        add_audit_event(
            self.db,
            event_type="normocontrol.settings.updated",
            actor_user_id=user_id,
            actor_session_id=session_id,
            resource_type="page",
            resource_id=data.page_id,
            after={"accepting": data.accepting},
        )
        await self.db.flush()
        return self._settings_output(row, True)

    # --- чтение -----------------------------------------------------------

    def service_available(self) -> bool:
        return bool(self.settings.normocontrol_base_url)

    async def _report_output(
        self, check_id: UUID | None
    ) -> NormocontrolReportOutput | None:
        if check_id is None:
            return None
        check = await self.db.get(NormocontrolCheck, check_id)
        if check is None:
            return None
        raw = check.raw or {}
        categories = [
            NormocontrolCategoryOutput.model_validate(item)
            for item in raw.get("categories", [])
            if isinstance(item, dict)
        ]
        return NormocontrolReportOutput(
            total_issues=check.total_issues,
            is_clean=check.is_clean,
            notes=[note for note in raw.get("notes", []) if isinstance(note, str)],
            categories=categories,
            raw=raw,
            checker_version=check.checker_version,
            schema_version=check.schema_version,
            norms_version=check.norms_version,
            computed_at=check.computed_at,
        )

    async def _queue_position(self, run: NormocontrolRun) -> int | None:
        if run.status != RunStatus.QUEUED.value:
            return None
        ahead = await self.db.scalar(
            select(func.count())
            .select_from(NormocontrolRun)
            .where(
                NormocontrolRun.status == RunStatus.QUEUED.value,
                NormocontrolRun.created_at < run.created_at,
            )
        )
        return int(ahead or 0) + 1

    async def to_output(
        self,
        run: NormocontrolRun,
        *,
        author: User | None = None,
    ) -> NormocontrolRunOutput:
        return NormocontrolRunOutput(
            id=run.id,
            page_id=run.page_id,
            user_id=run.user_id,
            status=RunStatus(run.status),
            original_name=run.original_name,
            size=run.size,
            queue_position=await self._queue_position(run),
            error_code=FailureReason(run.error_code) if run.error_code else None,
            created_at=run.created_at,
            finished_at=run.finished_at,
            report=await self._report_output(run.check_id),
            author=NormocontrolAuthorOutput.model_validate(author)
            if author is not None
            else None,
        )

    async def visible_runs(
        self, user_id: UUID, page_id: UUID
    ) -> tuple[list[NormocontrolRun], bool]:
        """Own history for students, whole material history for reviewers."""

        role = await self.access.effective_role(user_id, ResourceType.PAGE, page_id)
        reviewing_all = role in REVIEW_ROLES
        conditions = [
            NormocontrolRun.page_id == page_id,
            NormocontrolRun.status != RunStatus.DRAFT.value,
        ]
        if not reviewing_all:
            conditions.append(NormocontrolRun.user_id == user_id)
        rows = await self.db.scalars(
            select(NormocontrolRun)
            .where(*conditions)
            .order_by(NormocontrolRun.created_at.desc())
            .limit(HISTORY_LIMIT)
        )
        return list(rows), reviewing_all

    async def to_outputs(
        self,
        runs: list[NormocontrolRun],
        *,
        include_authors: bool,
    ) -> list[NormocontrolRunOutput]:
        authors: dict[UUID, User] = {}
        if include_authors and runs:
            users = await self.db.scalars(
                select(User).where(User.id.in_({run.user_id for run in runs}))
            )
            authors = {user.id: user for user in users}
        return [
            await self.to_output(run, author=authors.get(run.user_id))
            for run in runs
        ]

    async def pending_count(self, user_id: UUID) -> int:
        value = await self.db.scalar(
            select(func.count())
            .select_from(NormocontrolRun)
            .where(
                NormocontrolRun.user_id == user_id,
                NormocontrolRun.status.in_(
                    (RunStatus.QUEUED.value, RunStatus.RUNNING.value)
                ),
            )
        )
        return int(value or 0)

    async def get_run(self, user_id: UUID, run_id: UUID) -> NormocontrolRun:
        run = await self.db.get(NormocontrolRun, run_id)
        if run is None:
            raise LookupError("Check not found")
        if run.user_id != user_id:
            # Чужую проверку видит только тот, кто ведёт материал.
            role = await self.access.effective_role(
                user_id, ResourceType.PAGE, run.page_id
            )
            if role not in REVIEW_ROLES:
                raise PermissionError("Access denied")
        return run

    # --- запись -----------------------------------------------------------

    async def create_run(self, user_id: UUID, page_id: UUID) -> NormocontrolRun:
        """Пустой прогон, к которому прикладывается документ.

        Он нужен раньше самого файла: `POST /files/upload` привязывает файл к
        ресурсу в момент загрузки, а привязать документ к странице материала
        нельзя — его прочитал бы любой, у кого есть доступ к материалу.
        """

        await self._page(user_id, page_id, READ_ROLES)
        row, _ = await self._settings_row(page_id)
        if row.accepting is False:
            raise ValueError("This material does not accept documents right now")
        if not self.service_available():
            raise ValueError("Document checking is not configured on this platform")

        existing = await self.db.scalar(
            select(NormocontrolRun).where(
                NormocontrolRun.page_id == page_id,
                NormocontrolRun.user_id == user_id,
                NormocontrolRun.status == RunStatus.DRAFT.value,
            )
        )
        if existing is not None:
            return existing

        if await self.pending_count(user_id) >= (
            self.settings.normocontrol_user_queue_limit
        ):
            raise ValueError("Too many checks are already queued, wait for them")

        run = NormocontrolRun(
            id=uuid4(),
            page_id=page_id,
            user_id=user_id,
            status=RunStatus.DRAFT.value,
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def may_upload_to(self, user_id: UUID, run_id: UUID) -> bool:
        """Приложить документ можно только к своему незапущенному прогону."""

        run = await self.db.get(NormocontrolRun, run_id)
        if run is None or run.user_id != user_id:
            return False
        return run.status == RunStatus.DRAFT.value

    async def may_read_run_file(self, user_id: UUID, run_id: UUID) -> bool:
        run = await self.db.get(NormocontrolRun, run_id)
        if run is None:
            return False
        if run.user_id == user_id:
            return True
        role = await self.access.effective_role(
            user_id, ResourceType.PAGE, run.page_id
        )
        return role in REVIEW_ROLES

    async def submit(
        self, user_id: UUID, session_id: UUID, run_id: UUID, file_id: UUID
    ) -> NormocontrolRun:
        run = await self.db.get(NormocontrolRun, run_id)
        if run is None or run.user_id != user_id:
            raise LookupError("Check not found")
        if run.status != RunStatus.DRAFT.value:
            raise ValueError("This check has already been sent")
        await self._page(user_id, run.page_id, READ_ROLES)

        stored = await self.db.get(StoredFile, file_id)
        if stored is None or stored.deleted_at is not None:
            raise LookupError("File not found")
        if stored.uploaded_by != user_id:
            raise PermissionError("File was uploaded by another user")

        extension = Path(stored.original_name).suffix.lower()
        if extension not in self.settings.normocontrol_allowed_extensions:
            raise ValueError("Only .docx and .pdf documents can be checked")
        if stored.size > self.settings.normocontrol_max_file_size:
            raise ValueError("Document is too large to check")

        attachment = await self.db.scalar(
            select(FileAttachment).where(
                FileAttachment.file_id == file_id,
                FileAttachment.resource_type == RUN_RESOURCE_TYPE,
                FileAttachment.resource_id == run_id,
            )
        )
        if attachment is None:
            raise ValueError("Attach the document to this check before sending")

        now = datetime.now(UTC)
        run.file_id = file_id
        run.original_name = stored.original_name
        run.content_sha256 = stored.sha256
        run.size = stored.size
        run.status = RunStatus.QUEUED.value
        run.queued_at = now
        add_audit_event(
            self.db,
            event_type="normocontrol.run.queued",
            actor_user_id=user_id,
            actor_session_id=session_id,
            resource_type="page",
            resource_id=run.page_id,
            after={"run_id": str(run.id), "size": stored.size},
        )
        await self.db.flush()
        return run

    async def cancel(self, user_id: UUID, run_id: UUID) -> NormocontrolRun:
        run = await self.db.get(NormocontrolRun, run_id)
        if run is None or run.user_id != user_id:
            raise LookupError("Check not found")
        if run.status not in (RunStatus.DRAFT.value, RunStatus.QUEUED.value):
            # Выполняющуюся уже не отменить: она у внешнего сервиса.
            raise ValueError("This check can no longer be cancelled")
        run.status = RunStatus.CANCELLED.value
        run.finished_at = datetime.now(UTC)
        await self.db.flush()
        return run
