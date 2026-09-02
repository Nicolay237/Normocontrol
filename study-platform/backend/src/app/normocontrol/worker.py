"""Потребитель очереди проверок.

Тяжёлый разбор документа идёт во внешнем сервисе, поэтому здесь работа
исключительно ожидающая — HTTP-запрос с таймаутом. Отдельный процесс ради
этого не нужен: задача живёт рядом с остальными фоновыми задачами приложения
и event loop не занимает.

Очередь при этом взята из базы через `FOR UPDATE SKIP LOCKED`, а не из памяти.
Это стоит одного запроса, но переживает перезапуск и не придётся переделывать,
если потребителей однажды станет несколько.
"""

import asyncio
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID

import aiofiles
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from wsapi.runtime.context import PendingSyncEvent

from app.access.service import AccessService
from app.config import Settings, get_settings
from app.files.models import StoredFile
from app.files.storage import LocalFileStorage
from app.infrastructure.database import session_factory
from app.normocontrol.client import (
    NormocontrolClient,
    NormocontrolClientError,
    ServiceVersion,
)
from app.normocontrol.enums import FailureReason, RunStatus
from app.normocontrol.models import NormocontrolCheck, NormocontrolRun
from app.normocontrol.service import NormocontrolService
from app.ws.api import ws_api

logger = logging.getLogger("app.normocontrol")

#: Насколько долго держим версию сервиса, не переспрашивая. Она меняется при
#: выкатке, а не между двумя документами.
VERSION_TTL_SECONDS = 60.0

#: Отказы, которые повторять бессмысленно: дело в самом документе.
PERMANENT = frozenset(
    {
        FailureReason.DOCUMENT_REJECTED,
        FailureReason.UNSUPPORTED_FORMAT,
        FailureReason.FILE_TOO_LARGE,
        FailureReason.FILE_MISSING,
        FailureReason.INCOMPATIBLE_REPORT,
    }
)


class _VersionCache:
    def __init__(self) -> None:
        self._value = ServiceVersion()
        self._at = -VERSION_TTL_SECONDS

    async def get(self, client: NormocontrolClient) -> ServiceVersion:
        if monotonic() - self._at >= VERSION_TTL_SECONDS:
            self._value = await client.version()
            self._at = monotonic()
        return self._value


def build_client(settings: Settings) -> NormocontrolClient | None:
    if not settings.normocontrol_base_url:
        return None
    return NormocontrolClient(
        base_url=settings.normocontrol_base_url,
        timeout=settings.normocontrol_timeout_seconds,
        max_bytes=settings.normocontrol_max_report_bytes,
    )


async def reclaim_stale(db: AsyncSession, settings: Settings) -> None:
    """Возвращает в очередь работы, взятые упавшим процессом."""

    await db.execute(
        update(NormocontrolRun)
        .where(
            NormocontrolRun.status == RunStatus.RUNNING.value,
            NormocontrolRun.lease_expires_at.is_not(None),
            NormocontrolRun.lease_expires_at <= datetime.now(UTC),
        )
        .values(status=RunStatus.QUEUED.value, lease_expires_at=None)
    )


async def claim_next(
    db: AsyncSession, settings: Settings
) -> NormocontrolRun | None:
    """Берёт следующую работу, соблюдая очередь по одному на пользователя.

    Без этого условия человек, приславший два десятка файлов, занял бы всю
    очередь, и остальные ждали бы его.
    """

    # Алиас один на оба условия: два вызова `.alias()` дали бы две разные
    # таблицы, и подзапрос считал бы не то.
    busy = NormocontrolRun.__table__.alias("busy")
    running_for_user = (
        select(func.count())
        .select_from(busy)
        .where(
            busy.c.user_id == NormocontrolRun.user_id,
            busy.c.status == RunStatus.RUNNING.value,
        )
        .scalar_subquery()
    )
    run = await db.scalar(
        select(NormocontrolRun)
        .where(
            NormocontrolRun.status == RunStatus.QUEUED.value,
            running_for_user < settings.normocontrol_user_concurrency,
        )
        .order_by(NormocontrolRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True, of=NormocontrolRun)
    )
    if run is None:
        return None
    run.status = RunStatus.RUNNING.value
    run.started_at = datetime.now(UTC)
    run.attempts += 1
    run.lease_expires_at = datetime.now(UTC) + timedelta(
        seconds=settings.normocontrol_lease_seconds
    )
    await db.flush()
    return run


async def _read_document(
    db: AsyncSession, run: NormocontrolRun, settings: Settings
) -> tuple[bytes, str]:
    if run.file_id is None:
        raise NormocontrolClientError(FailureReason.FILE_MISSING)
    stored = await db.get(StoredFile, run.file_id)
    if stored is None or stored.deleted_at is not None:
        raise NormocontrolClientError(FailureReason.FILE_MISSING)
    storage = LocalFileStorage(settings.files_root, settings.max_upload_size)
    path = storage.path_for(stored.storage_key)
    if not path.is_file():
        raise NormocontrolClientError(FailureReason.FILE_MISSING)
    async with aiofiles.open(path, "rb") as handle:
        return await handle.read(), stored.original_name


async def _cached_check(
    db: AsyncSession, sha256: str, version: ServiceVersion
) -> NormocontrolCheck | None:
    check: NormocontrolCheck | None = await db.scalar(
        select(NormocontrolCheck).where(
            NormocontrolCheck.content_sha256 == sha256,
            NormocontrolCheck.checker_version == version.checker,
            NormocontrolCheck.schema_version == version.schema,
            NormocontrolCheck.norms_version == version.norms,
        )
    )
    return check


async def _lock_check_key(
    db: AsyncSession, sha256: str, version: ServiceVersion
) -> None:
    """Serialize the final cache lookup and insert for identical results.

    The document check itself stays concurrent. Only the tiny database section
    after the external service has replied is locked, and PostgreSQL releases
    the transaction-scoped advisory lock on commit or rollback.
    """

    key = "\0".join((sha256, version.checker, version.schema, version.norms))
    # PostgreSQL text values cannot contain NUL. Hash the unambiguous local
    # key first and pass only the resulting signed int64 to the advisory lock.
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], signed=True)
    await db.scalar(select(func.pg_advisory_xact_lock(lock_id)))


async def _drop_document(db: AsyncSession, run: NormocontrolRun) -> None:
    """Документ нужен был только до конца проверки.

    Отчёт остаётся, файл — нет: это черновики студентов, они и так у них есть,
    а диск копить их незачем. Само хранилище подчищает фоновая уборка.
    """

    if run.file_id is None:
        return
    stored = await db.get(StoredFile, run.file_id)
    if stored is not None and stored.deleted_at is None:
        stored.deleted_at = datetime.now(UTC)


async def process(
    db: AsyncSession,
    run: NormocontrolRun,
    client: NormocontrolClient,
    versions: _VersionCache,
    settings: Settings,
) -> None:
    now = datetime.now(UTC)
    try:
        content, filename = await _read_document(db, run, settings)
        version = await versions.get(client)

        check = None
        if run.content_sha256:
            # Один методический шаблон ходит по всему курсу: одинаковое
            # содержимое считаем один раз.
            check = await _cached_check(db, run.content_sha256, version)

        if check is None:
            report = await client.check(content, filename, version)
            content_sha256 = run.content_sha256 or ""
            await _lock_check_key(db, content_sha256, report.version)
            # Another worker may have finished the same document while this
            # one was waiting for the external service or the advisory lock.
            check = await _cached_check(db, content_sha256, report.version)
            if check is None:
                check = NormocontrolCheck(
                    content_sha256=content_sha256,
                    checker_version=report.version.checker,
                    schema_version=report.version.schema,
                    norms_version=report.version.norms,
                    raw=report.raw,
                    total_issues=report.total_issues,
                    is_clean=report.is_clean,
                )
                db.add(check)
                await db.flush()

        run.check_id = check.id
        run.status = RunStatus.DONE.value
        run.error_code = None
        run.finished_at = now
        run.lease_expires_at = None
        await _drop_document(db, run)
    except NormocontrolClientError as exc:
        retryable = exc.reason not in PERMANENT
        if retryable and run.attempts < settings.normocontrol_max_attempts:
            # Вернуть в очередь: сервис мог просто перезапускаться.
            run.status = RunStatus.QUEUED.value
            run.lease_expires_at = None
            return
        run.status = RunStatus.FAILED.value
        run.error_code = exc.reason.value
        run.finished_at = now
        run.lease_expires_at = None
        await _drop_document(db, run)


async def _publish(db: AsyncSession, run_id: UUID) -> None:
    run = await db.get(NormocontrolRun, run_id)
    if run is None:
        return
    service = NormocontrolService(db, AccessService(db))
    await ws_api.sync_publisher.publish(
        PendingSyncEvent(
            scope="normocontrol.run.changed",
            scope_id=str(run.id),
            data=await service.to_output(run),
            caused_by=None,
        )
    )


async def _mark_unexpected_failure(
    db: AsyncSession,
    run: NormocontrolRun,
    settings: Settings,
) -> None:
    """Move a claimed run out of ``running`` after an unexpected exception."""

    run.lease_expires_at = None
    if run.attempts < settings.normocontrol_max_attempts:
        run.status = RunStatus.QUEUED.value
        return

    run.status = RunStatus.FAILED.value
    run.error_code = FailureReason.PROCESSING_ERROR.value
    run.finished_at = datetime.now(UTC)
    await _drop_document(db, run)


async def _recover_unexpected(run_id: UUID, settings: Settings) -> None:
    """Recover state in a fresh transaction after the failed one rolled back."""

    async with session_factory() as db:
        run = await db.get(NormocontrolRun, run_id)
        if run is None or run.status != RunStatus.RUNNING.value:
            return
        await _mark_unexpected_failure(db, run, settings)
        await db.commit()


async def run_queue() -> None:
    """Фоновая задача приложения. Живёт рядом с остальными в lifespan."""

    settings = get_settings()
    client = build_client(settings)
    if client is None:
        logger.info("normocontrol: адрес сервиса не задан, очередь не запускается")
        return

    versions = _VersionCache()
    semaphore = asyncio.Semaphore(settings.normocontrol_concurrency)

    async def handle_one() -> bool:
        async with semaphore:
            async with session_factory() as db:
                await reclaim_stale(db, settings)
                run = await claim_next(db, settings)
                if run is None:
                    await db.commit()
                    return False
                run_id = run.id
                await db.commit()

            try:
                async with session_factory() as db:
                    claimed = await db.get(NormocontrolRun, run_id)
                    if claimed is None:
                        return True
                    await process(db, claimed, client, versions, settings)
                    await db.commit()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A failed transaction must never strand a visible job in
                # `running`. Retry it in a clean transaction, then surface a
                # stable terminal error if the attempt budget is exhausted.
                logger.exception("normocontrol: сбой обработки задания %s", run_id)
                await _recover_unexpected(run_id, settings)

            async with session_factory() as db:
                await _publish(db, run_id)
            return True

    while True:
        try:
            worked = await handle_one()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Очередь не должна умирать от одной неудачной итерации.
            logger.exception("normocontrol: сбой обработки очереди")
            worked = False
        if not worked:
            await asyncio.sleep(settings.normocontrol_poll_seconds)
