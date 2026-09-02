"""Материал нормоконтроля: права, приём документов, очередь."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.access.enums import Role
from app.access.service import AccessService
from app.config import Settings
from app.normocontrol.enums import RUN_RESOURCE_TYPE, FailureReason, RunStatus
from app.normocontrol.models import (
    NormocontrolCheck,
    NormocontrolRun,
    NormocontrolSettings,
)
from app.normocontrol.service import NormocontrolService
from app.users.models import User

PAGE_ID = uuid4()
USER_ID = uuid4()
SESSION_ID = uuid4()
FILE_ID = uuid4()


class _Access:
    def __init__(self, role: Role | None) -> None:
        self.role = role

    async def effective_role(self, user_id, resource_type, resource_id):
        return self.role

    async def require_at_least(self, user_id, resource_type, resource_id, roles):
        if self.role not in roles:
            raise PermissionError("Access denied")
        return self.role


class FakeDb:
    """Ровно то, чем пользуется сервис: get/scalar/add/flush."""

    def __init__(self, page: Any, settings_row: NormocontrolSettings | None) -> None:
        self.page = page
        self.added: list[Any] = []
        self.store: dict[tuple[type, Any], Any] = {}
        self.scalars_result: list[Any] = []
        self.scalars_statements: list[str] = []
        self.counts: list[int] = []
        self.attachment: Any = None
        self.draft: NormocontrolRun | None = None
        if settings_row is not None:
            self.store[(NormocontrolSettings, settings_row.page_id)] = settings_row

    def add(self, item: Any) -> None:
        self.added.append(item)
        if isinstance(item, NormocontrolRun):
            self.store[(NormocontrolRun, item.id)] = item
        if isinstance(item, NormocontrolCheck):
            self.store[(NormocontrolCheck, item.id)] = item

    async def get(self, model: type, pk: Any) -> Any:
        return self.store.get((model, pk))

    async def scalar(self, statement: Any) -> Any:
        text = str(statement)
        if "FROM pages" in text:
            return self.page
        if "count" in text.lower():
            return self.counts.pop(0) if self.counts else 0
        if "file_attachments" in text:
            return self.attachment
        if "normocontrol_runs" in text:
            return self.draft
        return None

    async def scalars(self, statement: Any) -> list[Any]:
        self.scalars_statements.append(str(statement))
        return list(self.scalars_result)

    async def flush(self) -> None:
        return None


def _settings(**kwargs) -> Settings:
    return Settings(
        normocontrol_base_url=kwargs.pop("base_url", "http://normocontrol:8080"),
        _env_file=None,
        **kwargs,
    )


def _page(kind: str = "normocontrol") -> SimpleNamespace:
    return SimpleNamespace(id=PAGE_ID, kind=kind, deleted_at=None)


def _service(
    db: FakeDb, role: Role | None = Role.STUDENT, settings: Settings | None = None
) -> NormocontrolService:
    return NormocontrolService(
        cast(AsyncSession, db),
        cast(AccessService, _Access(role)),
        settings or _settings(),
    )


def _stored(name: str = "vkr.docx", size: int = 2048, owner=USER_ID):
    return SimpleNamespace(
        id=FILE_ID,
        original_name=name,
        size=size,
        sha256="a" * 64,
        uploaded_by=owner,
        deleted_at=None,
        storage_key="ab/cd/file",
    )


def _run(status: RunStatus = RunStatus.DRAFT, user_id=USER_ID) -> NormocontrolRun:
    run = NormocontrolRun(
        page_id=PAGE_ID, user_id=user_id, status=status.value, attempts=0
    )
    run.id = uuid4()
    run.created_at = datetime.now(UTC)
    return run


# --- материал ---------------------------------------------------------------


async def test_other_page_kinds_are_not_normocontrol_materials() -> None:
    db = FakeDb(_page(kind="lab"), None)

    with pytest.raises(ValueError, match="not a normocontrol material"):
        await _service(db).get_settings(USER_ID, PAGE_ID)


async def test_unconfigured_material_is_marked_as_such() -> None:
    """Как у лабораторных: подставленные умолчания — не чей-то выбор."""
    db = FakeDb(_page(), None)

    output = await _service(db).get_settings(USER_ID, PAGE_ID)

    assert output.configured is False
    assert output.accepting is True
    assert output.allowed_extensions == [".docx", ".pdf"]


async def test_only_editors_change_the_material() -> None:
    from app.normocontrol.schemas import NormocontrolSettingsInput

    db = FakeDb(_page(), None)

    with pytest.raises(PermissionError):
        await _service(db, Role.STUDENT).set_settings(
            USER_ID,
            SESSION_ID,
            NormocontrolSettingsInput(page_id=PAGE_ID, accepting=False),
        )


# --- приём документов -------------------------------------------------------


async def test_run_is_refused_when_the_service_is_not_configured() -> None:
    """Без адреса сервиса материал честно не принимает файлы."""
    db = FakeDb(_page(), None)
    service = _service(db, settings=_settings(base_url=None))

    assert service.service_available() is False
    with pytest.raises(ValueError, match="not configured"):
        await service.create_run(USER_ID, PAGE_ID)


async def test_closed_material_does_not_accept_documents() -> None:
    row = NormocontrolSettings(page_id=PAGE_ID, accepting=False)
    db = FakeDb(_page(), row)

    with pytest.raises(ValueError, match="does not accept"):
        await _service(db).create_run(USER_ID, PAGE_ID)


async def test_queue_limit_stops_one_person_from_filling_it() -> None:
    db = FakeDb(_page(), None)
    db.draft = None
    db.counts = [5]  # столько уже ждёт

    with pytest.raises(ValueError, match="Too many checks"):
        await _service(db).create_run(USER_ID, PAGE_ID)


async def test_repeated_create_returns_the_same_draft() -> None:
    db = FakeDb(_page(), None)
    draft = _run(RunStatus.DRAFT)
    db.draft = draft

    assert (await _service(db).create_run(USER_ID, PAGE_ID)) is draft


async def test_only_own_draft_accepts_a_document() -> None:
    db = FakeDb(_page(), None)
    mine = _run(RunStatus.DRAFT)
    theirs = _run(RunStatus.DRAFT, user_id=uuid4())
    queued = _run(RunStatus.QUEUED)
    for run in (mine, theirs, queued):
        db.store[(NormocontrolRun, run.id)] = run
    service = _service(db)

    assert await service.may_upload_to(USER_ID, mine.id) is True
    assert await service.may_upload_to(USER_ID, theirs.id) is False
    # Уже отправленную проверку дополнить нельзя.
    assert await service.may_upload_to(USER_ID, queued.id) is False


@pytest.mark.parametrize("name", ["work.txt", "work.doc", "work.zip", "work"])
async def test_only_documents_are_accepted(name) -> None:
    from app.files.models import StoredFile

    db = FakeDb(_page(), None)
    run = _run(RunStatus.DRAFT)
    db.store[(NormocontrolRun, run.id)] = run
    db.store[(StoredFile, FILE_ID)] = _stored(name=name)
    db.attachment = object()

    with pytest.raises(ValueError, match="docx"):
        await _service(db).submit(USER_ID, SESSION_ID, run.id, FILE_ID)


async def test_oversized_document_is_refused_before_the_queue() -> None:
    from app.files.models import StoredFile

    db = FakeDb(_page(), None)
    run = _run(RunStatus.DRAFT)
    db.store[(NormocontrolRun, run.id)] = run
    db.store[(StoredFile, FILE_ID)] = _stored(size=64 * 1024 * 1024)
    db.attachment = object()

    with pytest.raises(ValueError, match="too large"):
        await _service(db).submit(USER_ID, SESSION_ID, run.id, FILE_ID)


async def test_document_of_another_user_is_refused() -> None:
    from app.files.models import StoredFile

    db = FakeDb(_page(), None)
    run = _run(RunStatus.DRAFT)
    db.store[(NormocontrolRun, run.id)] = run
    db.store[(StoredFile, FILE_ID)] = _stored(owner=uuid4())
    db.attachment = object()

    with pytest.raises(PermissionError):
        await _service(db).submit(USER_ID, SESSION_ID, run.id, FILE_ID)


async def test_submit_puts_the_run_into_the_queue() -> None:
    from app.files.models import StoredFile

    db = FakeDb(_page(), None)
    run = _run(RunStatus.DRAFT)
    db.store[(NormocontrolRun, run.id)] = run
    db.store[(StoredFile, FILE_ID)] = _stored()
    db.attachment = object()

    result = await _service(db).submit(USER_ID, SESSION_ID, run.id, FILE_ID)

    assert result.status == RunStatus.QUEUED.value
    # Имя, размер и хеш скопированы: документ удалится, история останется.
    assert result.original_name == "vkr.docx"
    assert result.content_sha256 == "a" * 64
    assert result.size == 2048


async def test_submit_needs_the_document_attached_first() -> None:
    from app.files.models import StoredFile

    db = FakeDb(_page(), None)
    run = _run(RunStatus.DRAFT)
    db.store[(NormocontrolRun, run.id)] = run
    db.store[(StoredFile, FILE_ID)] = _stored()
    db.attachment = None

    with pytest.raises(ValueError, match="Attach the document"):
        await _service(db).submit(USER_ID, SESSION_ID, run.id, FILE_ID)


# --- чужие проверки ---------------------------------------------------------


async def test_student_history_query_is_limited_to_their_runs() -> None:
    db = FakeDb(_page(), None)

    _, reviewing_all = await _service(db, Role.STUDENT).visible_runs(
        USER_ID, PAGE_ID
    )

    assert reviewing_all is False
    assert "normocontrol_runs.user_id =" in db.scalars_statements[-1]


@pytest.mark.parametrize("role", [Role.OWNER, Role.EDITOR, Role.CONTROLLER])
async def test_reviewer_history_query_includes_every_user(role: Role) -> None:
    db = FakeDb(_page(), None)

    _, reviewing_all = await _service(db, role).visible_runs(USER_ID, PAGE_ID)

    assert reviewing_all is True
    assert "normocontrol_runs.user_id =" not in db.scalars_statements[-1]


async def test_reviewer_run_output_contains_author() -> None:
    db = FakeDb(_page(), None)
    run = _run(RunStatus.DONE, user_id=uuid4())
    author = User(
        id=run.user_id,
        username="student",
        display_name="Студент",
        status="active",
        is_protected=False,
    )

    output = await _service(db, Role.CONTROLLER).to_output(run, author=author)

    assert output.author is not None
    assert output.author.id == run.user_id
    assert output.author.display_name == "Студент"


async def test_another_student_does_not_see_someone_elses_check() -> None:
    db = FakeDb(_page(), None)
    theirs = _run(RunStatus.DONE, user_id=uuid4())
    db.store[(NormocontrolRun, theirs.id)] = theirs

    with pytest.raises(PermissionError):
        await _service(db, Role.STUDENT).get_run(USER_ID, theirs.id)


async def test_teacher_sees_checks_inside_their_material() -> None:
    db = FakeDb(_page(), None)
    theirs = _run(RunStatus.DONE, user_id=uuid4())
    db.store[(NormocontrolRun, theirs.id)] = theirs

    assert await _service(db, Role.CONTROLLER).get_run(USER_ID, theirs.id) is theirs


async def test_document_of_another_student_is_not_downloadable() -> None:
    db = FakeDb(_page(), None)
    theirs = _run(RunStatus.QUEUED, user_id=uuid4())
    db.store[(NormocontrolRun, theirs.id)] = theirs

    assert await _service(db, Role.STUDENT).may_read_run_file(USER_ID, theirs.id) is (
        False
    )


# --- отмена -----------------------------------------------------------------


async def test_queued_check_can_be_cancelled() -> None:
    db = FakeDb(_page(), None)
    run = _run(RunStatus.QUEUED)
    db.store[(NormocontrolRun, run.id)] = run

    result = await _service(db).cancel(USER_ID, run.id)

    assert result.status == RunStatus.CANCELLED.value


async def test_running_check_can_no_longer_be_cancelled() -> None:
    """Она уже у внешнего сервиса — отзывать нечего."""
    db = FakeDb(_page(), None)
    run = _run(RunStatus.RUNNING)
    db.store[(NormocontrolRun, run.id)] = run

    with pytest.raises(ValueError, match="no longer be cancelled"):
        await _service(db).cancel(USER_ID, run.id)


# --- отчёт ------------------------------------------------------------------


async def test_report_is_projected_from_the_stored_answer() -> None:
    """Категории разбираются из сырого ответа, а не из своей таблицы."""
    db = FakeDb(_page(), None)
    check = NormocontrolCheck(
        content_sha256="a" * 64,
        checker_version="1.4.0",
        schema_version="1",
        norms_version="gost-7.32-2017",
        raw={
            "notes": ["оценочно"],
            "categories": [
                {
                    "name": "Поля страницы",
                    "issues": [{"location": "Раздел №1", "message": "2.0 см"}],
                }
            ],
        },
        total_issues=1,
        is_clean=False,
    )
    check.id = uuid4()
    check.computed_at = datetime.now(UTC)
    db.store[(NormocontrolCheck, check.id)] = check
    run = _run(RunStatus.DONE)
    run.check_id = check.id
    run.finished_at = datetime.now(UTC)
    db.store[(NormocontrolRun, run.id)] = run

    output = await _service(db).to_output(run)

    assert output.report is not None
    assert output.report.categories[0].name == "Поля страницы"
    assert output.report.checker_version == "1.4.0"
    # Сырой ответ сохранён целиком: его можно перепроецировать позже.
    assert "categories" in output.report.raw


async def test_failed_run_carries_a_stable_code() -> None:
    db = FakeDb(_page(), None)
    run = _run(RunStatus.FAILED)
    run.error_code = FailureReason.DOCUMENT_REJECTED.value
    run.finished_at = datetime.now(UTC)
    db.store[(NormocontrolRun, run.id)] = run

    output = await _service(db).to_output(run)

    assert output.error_code == FailureReason.DOCUMENT_REJECTED
    assert output.report is None


def test_upload_resource_type_is_its_own() -> None:
    """Не `page`: документ студента не должен доставаться соседям по материалу."""
    assert RUN_RESOURCE_TYPE == "normocontrol_run"
