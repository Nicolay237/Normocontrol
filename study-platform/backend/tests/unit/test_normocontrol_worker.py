"""Очередь: кеш по содержимому, повторы и уборка документов."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.files.models import StoredFile
from app.normocontrol import worker
from app.normocontrol.client import (
    NormocontrolClientError,
    NormocontrolReport,
    ServiceVersion,
)
from app.normocontrol.enums import FailureReason, RunStatus
from app.normocontrol.models import NormocontrolCheck, NormocontrolRun

SHA = "a" * 64
VERSION = ServiceVersion(checker="1.4.0", schema="1", norms="gost-7.32-2017")
RAW = {
    "isClean": False,
    "totalIssues": 1,
    "notes": [],
    "categories": [
        {"name": "Поля страницы", "issues": [{"location": "№1", "message": "2.0 см"}]}
    ],
}


class FakeDb:
    def __init__(self) -> None:
        self.store: dict[tuple[type, Any], Any] = {}
        self.added: list[Any] = []
        self.cached: NormocontrolCheck | None = None
        self.scalar_results: list[Any] = []

    def add(self, item: Any) -> None:
        self.added.append(item)
        if isinstance(item, NormocontrolCheck):
            item.id = item.id or uuid4()
            self.store[(NormocontrolCheck, item.id)] = item

    async def get(self, model: type, pk: Any) -> Any:
        return self.store.get((model, pk))

    async def scalar(self, statement: Any) -> Any:
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return self.cached

    async def flush(self) -> None:
        for item in self.added:
            if isinstance(item, NormocontrolCheck) and item.id is None:
                item.id = uuid4()


class FakeClient:
    """Внешний сервис, который уже ответил — или уже отказал."""

    def __init__(self, error: NormocontrolClientError | None = None) -> None:
        self.error = error
        self.calls = 0

    async def version(self) -> ServiceVersion:
        return VERSION

    async def check(self, content, filename, version=None) -> NormocontrolReport:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return NormocontrolReport(
            raw=RAW, total_issues=1, is_clean=False, version=VERSION
        )


class FakeVersions:
    async def get(self, client) -> ServiceVersion:
        return VERSION


def _settings(**kwargs) -> Settings:
    return Settings(
        normocontrol_base_url="http://normocontrol:8080", _env_file=None, **kwargs
    )


def _stored(tmp_path) -> StoredFile:
    path = tmp_path / "ab" / "cd"
    path.mkdir(parents=True, exist_ok=True)
    (path / "doc").write_bytes(b"PK\x03\x04docx")
    stored = StoredFile(
        storage_key="ab/cd/doc",
        original_name="vkr.docx",
        content_type="application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document",
        size=13,
        sha256=SHA,
        uploaded_by=uuid4(),
    )
    stored.id = uuid4()
    stored.deleted_at = None
    return stored


def _run(stored: StoredFile, attempts: int = 1) -> NormocontrolRun:
    run = NormocontrolRun(
        page_id=uuid4(),
        user_id=uuid4(),
        status=RunStatus.RUNNING.value,
        file_id=stored.id,
        content_sha256=SHA,
        attempts=attempts,
    )
    run.id = uuid4()
    run.created_at = datetime.now(UTC)
    return run


def _prepare(tmp_path):
    db = FakeDb()
    stored = _stored(tmp_path)
    db.store[(StoredFile, stored.id)] = stored
    run = _run(stored)
    db.store[(NormocontrolRun, run.id)] = run
    return db, stored, run


async def test_result_is_stored_and_document_removed(tmp_path) -> None:
    db, stored, run = _prepare(tmp_path)
    client = FakeClient()

    await worker.process(
        cast(AsyncSession, db),
        run,
        cast(Any, client),
        cast(Any, FakeVersions()),
        _settings(files_root=tmp_path),
    )

    assert run.status == RunStatus.DONE.value
    assert run.check_id is not None
    check = db.store[(NormocontrolCheck, run.check_id)]
    # Ответ сервиса лёг в базу целиком.
    assert check.raw == RAW
    assert (check.checker_version, check.norms_version) == ("1.4.0", "gost-7.32-2017")
    # Документ был нужен только до конца проверки.
    assert stored.deleted_at is not None


async def test_same_content_is_not_checked_twice(tmp_path) -> None:
    """Один методический шаблон на весь курс считается один раз."""
    db, _, run = _prepare(tmp_path)
    cached = NormocontrolCheck(
        content_sha256=SHA,
        checker_version=VERSION.checker,
        schema_version=VERSION.schema,
        norms_version=VERSION.norms,
        raw=RAW,
        total_issues=1,
        is_clean=False,
    )
    cached.id = uuid4()
    db.cached = cached
    client = FakeClient()

    await worker.process(
        cast(AsyncSession, db),
        run,
        cast(Any, client),
        cast(Any, FakeVersions()),
        _settings(files_root=tmp_path),
    )

    assert client.calls == 0
    assert run.check_id == cached.id
    assert run.status == RunStatus.DONE.value


async def test_concurrent_result_uses_cache_winner(tmp_path) -> None:
    """Two equal reports racing to insert share the row that wins the lock."""
    db, _, run = _prepare(tmp_path)
    cached = NormocontrolCheck(
        content_sha256=SHA,
        checker_version=VERSION.checker,
        schema_version=VERSION.schema,
        norms_version=VERSION.norms,
        raw=RAW,
        total_issues=1,
        is_clean=False,
    )
    cached.id = uuid4()
    # Initial miss, advisory-lock call, then the row committed by the winner.
    db.scalar_results = [None, None, cached]
    client = FakeClient()

    await worker.process(
        cast(AsyncSession, db),
        run,
        cast(Any, client),
        cast(Any, FakeVersions()),
        _settings(files_root=tmp_path),
    )

    assert client.calls == 1
    assert run.check_id == cached.id
    assert run.status == RunStatus.DONE.value
    assert db.added == []


@pytest.mark.parametrize(
    "reason",
    [
        FailureReason.DOCUMENT_REJECTED,
        FailureReason.INCOMPATIBLE_REPORT,
        FailureReason.FILE_TOO_LARGE,
    ],
)
async def test_permanent_failure_is_not_retried(tmp_path, reason) -> None:
    """Дело в документе или в конверте — повторять нечего."""
    db, stored, run = _prepare(tmp_path)
    client = FakeClient(NormocontrolClientError(reason))

    await worker.process(
        cast(AsyncSession, db),
        run,
        cast(Any, client),
        cast(Any, FakeVersions()),
        _settings(files_root=tmp_path),
    )

    assert run.status == RunStatus.FAILED.value
    assert run.error_code == reason.value
    assert stored.deleted_at is not None


async def test_unavailable_service_returns_the_run_to_the_queue(tmp_path) -> None:
    """Сервис мог просто перезапускаться — работу теряем зря."""
    db, stored, run = _prepare(tmp_path)
    client = FakeClient(NormocontrolClientError(FailureReason.SERVICE_UNAVAILABLE))

    await worker.process(
        cast(AsyncSession, db),
        run,
        cast(Any, client),
        cast(Any, FakeVersions()),
        _settings(files_root=tmp_path),
    )

    assert run.status == RunStatus.QUEUED.value
    assert run.lease_expires_at is None
    # Документ ещё понадобится на следующей попытке.
    assert stored.deleted_at is None


async def test_retries_stop_at_the_limit(tmp_path) -> None:
    db, stored, run = _prepare(tmp_path)
    run.attempts = 3
    client = FakeClient(NormocontrolClientError(FailureReason.TIMEOUT))

    await worker.process(
        cast(AsyncSession, db),
        run,
        cast(Any, client),
        cast(Any, FakeVersions()),
        _settings(files_root=tmp_path, normocontrol_max_attempts=3),
    )

    assert run.status == RunStatus.FAILED.value
    assert run.error_code == FailureReason.TIMEOUT.value
    assert stored.deleted_at is not None


async def test_unexpected_failure_returns_run_to_queue(tmp_path) -> None:
    db, stored, run = _prepare(tmp_path)

    await worker._mark_unexpected_failure(
        cast(AsyncSession, db),
        run,
        _settings(files_root=tmp_path, normocontrol_max_attempts=3),
    )

    assert run.status == RunStatus.QUEUED.value
    assert run.lease_expires_at is None
    assert stored.deleted_at is None


async def test_unexpected_failure_stops_at_attempt_limit(tmp_path) -> None:
    db, stored, run = _prepare(tmp_path)
    run.attempts = 3

    await worker._mark_unexpected_failure(
        cast(AsyncSession, db),
        run,
        _settings(files_root=tmp_path, normocontrol_max_attempts=3),
    )

    assert run.status == RunStatus.FAILED.value
    assert run.error_code == FailureReason.PROCESSING_ERROR.value
    assert run.finished_at is not None
    assert stored.deleted_at is not None


async def test_missing_document_fails_without_calling_the_service(tmp_path) -> None:
    db, stored, run = _prepare(tmp_path)
    stored.deleted_at = datetime.now(UTC)
    client = FakeClient()

    await worker.process(
        cast(AsyncSession, db),
        run,
        cast(Any, client),
        cast(Any, FakeVersions()),
        _settings(files_root=tmp_path),
    )

    assert client.calls == 0
    assert run.status == RunStatus.FAILED.value
    assert run.error_code == FailureReason.FILE_MISSING.value


def test_queue_does_not_start_without_a_configured_service() -> None:
    assert worker.build_client(Settings(_env_file=None)) is None


def test_permanent_failures_are_the_ones_about_the_document() -> None:
    assert FailureReason.SERVICE_UNAVAILABLE not in worker.PERMANENT
    assert FailureReason.TIMEOUT not in worker.PERMANENT
    assert FailureReason.DOCUMENT_REJECTED in worker.PERMANENT
