import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from sqlalchemy import delete, func, select, update
from wsapi.runtime.context import PendingSyncEvent

from app.blocks.leases import block_lease_manager
from app.blocks.models import PageBlock
from app.bootstrap import bootstrap_system
from app.config import get_settings
from app.files.models import StoredFile
from app.files.storage import LocalFileStorage
from app.infrastructure.database import (
    check_database,
    engine,
    session_factory,
)
from app.normocontrol.worker import run_queue as run_normocontrol_queue
from app.pages.models import Page, PageRevision
from app.pages.schemas import BlockOutput, PageOutput
from app.source_control.models import SourceControlOAuthState
from app.tests.models import TestAttempt
from app.tests.schemas import AttemptOutput
from app.users.models import AuthSession, TakeoverChallenge
from app.ws.api import ws_api


async def cleanup_expired_sessions() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(settings.background_cleanup_seconds)
        now = datetime.now(UTC)
        async with session_factory() as db:
            expired_session_ids = list(
                await db.scalars(
                    update(AuthSession)
                    .where(
                        AuthSession.revoked_at.is_(None),
                        AuthSession.expires_at <= now,
                    )
                    .values(revoked_at=now, revoke_reason="expired")
                    .returning(AuthSession.id)
                )
            )
            await db.execute(
                delete(TakeoverChallenge).where(TakeoverChallenge.expires_at <= now)
            )
            # Просроченный OAuth state бесполезен: повторно он всё равно не
            # пройдёт, а таблица иначе растёт от каждой брошенной попытки.
            await db.execute(
                delete(SourceControlOAuthState).where(
                    SourceControlOAuthState.expires_at <= now
                )
            )
            expired_attempt_ids = list(
                await db.scalars(
                    update(TestAttempt)
                    .where(
                        TestAttempt.status.in_(("created", "in_progress")),
                        TestAttempt.expires_at.is_not(None),
                        TestAttempt.expires_at <= now,
                    )
                    .values(status="expired", submitted_at=now)
                    .returning(TestAttempt.id)
                )
            )
            await db.commit()
            expired_attempts = list(
                await db.scalars(
                    select(TestAttempt).where(TestAttempt.id.in_(expired_attempt_ids))
                )
            )
            known_storage_keys = set(
                await db.scalars(
                    select(StoredFile.storage_key).where(
                        StoredFile.deleted_at.is_(None)
                    )
                )
            )

        expired_session_keys = {str(item) for item in expired_session_ids}
        for connection in ws_api.connection_manager.all():
            if connection.state.get("session_id") in expired_session_keys:
                with suppress(Exception):
                    await ws_api.disconnect(connection, "session_expired", code=1008)

        for attempt in expired_attempts:
            await ws_api.sync_publisher.publish(
                PendingSyncEvent(
                    scope="test.attempt.state_changed",
                    scope_id=str(attempt.id),
                    data=AttemptOutput.model_validate(attempt),
                    caused_by=None,
                )
            )

        expired_block_ids = await block_lease_manager.cleanup_expired()
        if expired_block_ids:
            async with session_factory() as db:
                block_page_rows = await db.execute(
                    select(PageBlock.id, PageBlock.page_id).where(
                        PageBlock.id.in_(expired_block_ids)
                    )
                )
                block_pages: dict[UUID, UUID] = {
                    block_id: page_id for block_id, page_id in block_page_rows
                }
            for block_id in expired_block_ids:
                page_id = block_pages.get(block_id)
                if page_id is not None:
                    await ws_api.sync_publisher.publish(
                        PendingSyncEvent(
                            scope="page.block.lock_changed",
                            scope_id=str(page_id),
                            data={"block_id": block_id, "lease": None},
                            caused_by=None,
                        )
                    )

        await LocalFileStorage(
            settings.files_root, settings.max_upload_size
        ).cleanup_orphans(known_storage_keys)


async def create_checkpoint_revisions() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(settings.background_cleanup_seconds)
        async with session_factory() as db:
            pages = list(
                await db.scalars(
                    select(Page).where(
                        Page.deleted_at.is_(None),
                        Page.draft_head_sequence
                        >= settings.revision_checkpoint_event_count,
                    )
                )
            )
            for page in pages:
                latest_sequence = int(
                    await db.scalar(
                        select(
                            func.coalesce(func.max(PageRevision.event_sequence), 0)
                        ).where(PageRevision.page_id == page.id)
                    )
                    or 0
                )
                if (
                    page.draft_head_sequence - latest_sequence
                    < settings.revision_checkpoint_event_count
                ):
                    continue
                blocks = list(
                    await db.scalars(
                        select(PageBlock)
                        .where(
                            PageBlock.page_id == page.id,
                            PageBlock.deleted_at.is_(None),
                        )
                        .order_by(PageBlock.zone, PageBlock.order_key, PageBlock.id)
                    )
                )
                revision = PageRevision(
                    page_id=page.id,
                    event_sequence=page.draft_head_sequence,
                    kind="checkpoint",
                    snapshot={
                        "page": PageOutput.model_validate(page).model_dump(mode="json"),
                        "blocks": [
                            BlockOutput.model_validate(block).model_dump(
                                mode="json", exclude={"computed_data"}
                            )
                            for block in blocks
                        ],
                    },
                    created_by=page.created_by,
                )
                db.add(revision)
                await db.flush()
                page.latest_revision_id = revision.id
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await check_database()
    settings.files_root.mkdir(parents=True, exist_ok=True)
    async with session_factory() as db:
        await bootstrap_system(db, settings)
    if settings.environment == "development":
        ws_api.generate_client("src/app/ws/generated/api.js")

    cleanup_task = asyncio.create_task(cleanup_expired_sessions())
    revision_task = asyncio.create_task(create_checkpoint_revisions())
    # Очередь нормоконтроля: работа здесь ожидающая, разбор документа идёт во
    # внешнем сервисе, поэтому event loop она не занимает.
    normocontrol_task = asyncio.create_task(run_normocontrol_queue())
    app.state.cleanup_task = cleanup_task
    app.state.revision_task = revision_task
    app.state.normocontrol_task = normocontrol_task
    try:
        yield
    finally:
        for connection in ws_api.connection_manager.all():
            with suppress(Exception):
                await connection.enqueue(
                    {
                        "v": ws_api.protocol_version,
                        "type": "sync",
                        "scope": "server.shutdown",
                        "scope_id": "server",
                        "event_id": str(uuid4()),
                        "sequence": 0,
                        "caused_by": None,
                        "data": {"reason": "server.shutdown"},
                    }
                )
        await asyncio.sleep(0)
        # A peer can finish its close handshake between ``all()`` above and
        # ``close_all()``.  Shutdown must still cancel tasks and dispose the
        # database pool when that race occurs.
        with suppress(Exception):
            await ws_api.connection_manager.close_all(reason="server.shutdown")
        cleanup_task.cancel()
        revision_task.cancel()
        normocontrol_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        with suppress(asyncio.CancelledError):
            await revision_task
        with suppress(asyncio.CancelledError):
            await normocontrol_task
        await engine.dispose()
