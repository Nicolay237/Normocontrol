from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.normocontrol.enums import FailureReason, RunStatus


class NormocontrolSettingsInput(BaseModel):
    page_id: UUID
    instructions: str | None = Field(default=None, max_length=8000)
    accepting: bool = True


class NormocontrolSettingsOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_id: UUID
    instructions: str | None
    accepting: bool
    #: Настраивал ли преподаватель материал. Как у лабораторных: подставленные
    #: умолчания нельзя выдавать за чей-то выбор.
    configured: bool = True
    #: Что принимает сервис и до какого размера — берётся из настроек
    #: платформы, чтобы интерфейс не хранил это у себя.
    allowed_extensions: list[str]
    max_file_size: int


class NormocontrolIssueOutput(BaseModel):
    location: str
    message: str


class NormocontrolCategoryOutput(BaseModel):
    name: str
    issues: list[NormocontrolIssueOutput]


class NormocontrolReportOutput(BaseModel):
    """Отчёт в том виде, в каком его отдал сервис.

    `categories` разобраны для удобства интерфейса, но рядом лежит `raw` —
    ответ целиком. Когда сервис начнёт присылать больше данных, они приедут в
    `raw` без единой правки бэкенда.
    """

    total_issues: int
    is_clean: bool
    notes: list[str]
    categories: list[NormocontrolCategoryOutput]
    raw: dict[str, Any]
    checker_version: str
    schema_version: str
    norms_version: str
    computed_at: datetime


class NormocontrolAuthorOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    avatar_id: UUID | None = None


class NormocontrolRunOutput(BaseModel):
    id: UUID
    page_id: UUID
    user_id: UUID
    status: RunStatus
    original_name: str | None
    size: int | None
    #: Место в очереди среди ожидающих; null, когда работа уже не в очереди.
    queue_position: int | None = None
    error_code: FailureReason | None = None
    created_at: datetime
    finished_at: datetime | None
    #: Заполняется только у завершённой удачно проверки.
    report: NormocontrolReportOutput | None = None
    #: Автор нужен проверяющим в общей истории; студенту его можно не дублировать.
    author: NormocontrolAuthorOutput | None = None


class NormocontrolPageInput(BaseModel):
    page_id: UUID


class NormocontrolRunIdInput(BaseModel):
    run_id: UUID


class NormocontrolSubmitInput(BaseModel):
    run_id: UUID
    #: Файл, уже загруженный через POST /files/upload с
    #: resource_type=normocontrol_run и resource_id этого прогона.
    file_id: UUID


class NormocontrolViewOutput(BaseModel):
    """Что видит студент: условие материала и собственные проверки."""

    settings: NormocontrolSettingsOutput
    #: От новой к старой.
    runs: list[NormocontrolRunOutput]
    #: Доступен ли сейчас сам сервис проверок.
    service_available: bool
    #: Сколько работ этого пользователя ещё ждут очереди.
    pending: int
    #: True означает, что runs содержит историю всех пользователей материала.
    reviewing_all: bool = False
