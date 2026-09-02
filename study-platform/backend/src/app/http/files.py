from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.access.enums import ResourceType, Role
from app.access.service import AccessService
from app.config import get_settings
from app.files.models import FileAttachment, StoredFile
from app.files.storage import LocalFileStorage
from app.http.dependencies import CurrentSession, Database
from app.labs.models import SUBMISSION_RESOURCE_TYPE
from app.labs.service import LabService
from app.normocontrol.enums import RUN_RESOURCE_TYPE
from app.normocontrol.service import NormocontrolService
from app.users.models import User

router = APIRouter(tags=["files"])
READ_ROLES = {Role.OWNER, Role.EDITOR, Role.CONTROLLER, Role.STUDENT}
EDIT_ROLES = {Role.OWNER, Role.EDITOR}
PREVIEW_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


def _storage() -> LocalFileStorage:
    settings = get_settings()
    return LocalFileStorage(settings.files_root, settings.max_upload_size)


async def _require_resource_access(
    db: Database,
    user_id: UUID,
    resource_type: str,
    resource_id: UUID,
    roles: set[Role],
) -> None:
    try:
        kind = ResourceType(resource_type)
    except ValueError as exc:
        raise HTTPException(400, "Unsupported resource type") from exc
    try:
        await AccessService(db).require_at_least(user_id, kind, resource_id, roles)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied") from exc


@router.post("/upload")
async def upload_file(
    db: Database,
    session: CurrentSession,
    upload: UploadFile,
    resource_type: Annotated[str, Form()],
    resource_id: Annotated[UUID, Form()],
    behavior: Annotated[str, Form()] = "download",
) -> dict[str, object]:
    if behavior not in {"download", "preview"}:
        raise HTTPException(400, "Invalid file behavior")
    if resource_type == SUBMISSION_RESOURCE_TYPE:
        # Обычная проверка требует owner/editor, а сдаёт работу студент —
        # через неё он не смог бы приложить файл вообще. Здесь правило другое:
        # свой собственный черновик, ещё не отправленный на проверку.
        service = LabService(db, AccessService(db))
        if not await service.may_upload_to(session.user_id, resource_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    elif resource_type == RUN_RESOURCE_TYPE:
        # То же самое у нормоконтроля: документ кладёт студент, и только в
        # свою ещё не отправленную проверку.
        checks = NormocontrolService(db, AccessService(db))
        if not await checks.may_upload_to(session.user_id, resource_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    else:
        await _require_resource_access(
            db, session.user_id, resource_type, resource_id, EDIT_ROLES
        )
    file_id = uuid4()
    storage = _storage()
    try:
        stored = await storage.save(file_id, upload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    item = StoredFile(
        id=file_id,
        storage_key=stored.storage_key,
        original_name=Path(upload.filename or "file").name[:512],
        content_type=(upload.content_type or "application/octet-stream")[:256],
        size=stored.size,
        sha256=stored.sha256,
        uploaded_by=session.user_id,
    )
    db.add(item)
    try:
        # FileAttachment only carries the parent's UUID and has no ORM relationship
        # to StoredFile, so the unit of work cannot infer their insert order.
        await db.flush()
        db.add(
            FileAttachment(
                file_id=file_id,
                resource_type=resource_type,
                resource_id=resource_id,
                behavior=behavior,
            )
        )
        await db.commit()
    except BaseException:
        try:
            await db.rollback()
        finally:
            await storage.delete(stored.storage_key)
        raise
    return {
        "id": item.id,
        "original_name": item.original_name,
        "content_type": item.content_type,
        "size": item.size,
        "sha256": item.sha256,
    }


async def _download(
    file_id: UUID,
    db: Database,
    session: CurrentSession,
    *,
    preview: bool,
) -> FileResponse:
    item = await db.scalar(
        select(StoredFile).where(
            StoredFile.id == file_id, StoredFile.deleted_at.is_(None)
        )
    )
    if item is None:
        raise HTTPException(404, "File not found")
    attachments = list(
        await db.scalars(
            select(FileAttachment).where(FileAttachment.file_id == file_id)
        )
    )
    allowed = False
    for attachment in attachments:
        # Сдача лабораторной работы — не ресурс с ACL, и правило у неё своё:
        # автор или тот, кто вправе оценивать. Через обычную проверку файл
        # скачал бы любой студент курса, потому что READ_ROLES включает
        # `student` на странице задания.
        if attachment.resource_type == SUBMISSION_RESOURCE_TYPE:
            service = LabService(db, AccessService(db))
            if await service.may_read_submission_file(
                session.user_id, attachment.resource_id
            ):
                allowed = True
                break
            continue
        # Проверяемый документ — черновик студента, и правило у него своё:
        # автор либо тот, кто ведёт материал.
        if attachment.resource_type == RUN_RESOURCE_TYPE:
            checks = NormocontrolService(db, AccessService(db))
            if await checks.may_read_run_file(
                session.user_id, attachment.resource_id
            ):
                allowed = True
                break
            continue
        try:
            await _require_resource_access(
                db,
                session.user_id,
                attachment.resource_type,
                attachment.resource_id,
                READ_ROLES,
            )
            allowed = True
            break
        except HTTPException as exc:
            if exc.status_code not in {403, 404}:
                raise
    if not allowed:
        raise HTTPException(403, "Access denied")
    path = _storage().path_for(item.storage_key)
    if not path.is_file():
        raise HTTPException(404, "Stored object not found")
    inline = preview and item.content_type in PREVIEW_TYPES
    return FileResponse(
        path,
        media_type=item.content_type,
        filename=None if inline else item.original_name,
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID, db: Database, session: CurrentSession
) -> FileResponse:
    return await _download(file_id, db, session, preview=False)


@router.head("/{file_id}/download")
async def head_file(
    file_id: UUID, db: Database, session: CurrentSession
) -> FileResponse:
    return await _download(file_id, db, session, preview=False)


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: UUID, db: Database, session: CurrentSession
) -> FileResponse:
    return await _download(file_id, db, session, preview=True)


async def _avatar(file_id: UUID, db: Database) -> FileResponse:
    item = await db.scalar(
        select(StoredFile)
        .join(User, User.avatar_id == StoredFile.id)
        .where(StoredFile.id == file_id, StoredFile.deleted_at.is_(None))
    )
    if item is None:
        raise HTTPException(404, "Avatar not found")
    path = _storage().path_for(item.storage_key)
    if not path.is_file():
        raise HTTPException(404, "Stored object not found")
    return FileResponse(
        path,
        media_type=item.content_type,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{file_id}/avatar")
async def get_avatar(file_id: UUID, db: Database) -> FileResponse:
    return await _avatar(file_id, db)


@router.head("/{file_id}/avatar")
async def head_avatar(file_id: UUID, db: Database) -> FileResponse:
    return await _avatar(file_id, db)
