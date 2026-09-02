from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.access.enums import Role


class PageAuthorOutput(BaseModel):
    """Автор страницы — тот, кто её создал.

    Едет вместе со страницей, а не отдельным запросом, потому что запросить
    его читателю нечем: `system.users.get` требует прав администратора, и
    студент, открывший лекцию, получил бы отказ. Здесь же доступ уже проверен —
    страницу ему открыть можно, значит, и имя её автора он видеть вправе.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    avatar_id: UUID | None = None


class PageOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    folder_id: UUID
    kind: str
    name: str
    description: str | None
    icon_name: str | None
    order_key: str
    draft_head_sequence: int
    latest_revision_id: UUID | None
    published_revision_id: UUID | None
    created_by: UUID | None = None
    # Заполняется только там, где автора успели прочитать (page.open). В
    # остальных местах остаётся пустым — со значением по умолчанию, иначе
    # model_validate(page) в снимках ревизий требовал бы того, чего у модели нет.
    author: PageAuthorOutput | None = None


class BlockOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_id: UUID
    block_type: str
    schema_version: int
    zone: str
    order_key: str
    ownership: str
    data: Any
    block_version: int
    computed_data: dict[str, Any] | None = None


class PageOpenInput(BaseModel):
    page_id: UUID


class PageResourceOutput(BaseModel):
    file_id: UUID
    original_name: str
    content_type: str
    size: int
    sha256: str
    behavior: Literal["download", "preview"]


class PageOpenOutput(BaseModel):
    page: PageOutput
    effective_role: Role
    blocks: list[BlockOutput]
    resources: list[PageResourceOutput] = Field(default_factory=list)


class PageCreateInput(BaseModel):
    folder_id: UUID
    kind: Literal["document", "lecture", "resource", "lab", "normocontrol"] = (
        "document"
    )
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4096)
    icon_name: str | None = Field(default=None, max_length=128)
    order_key: str | None = Field(default=None, max_length=512)


class PageUpdateInput(BaseModel):
    page_id: UUID
    # Перенос в другую папку. Отдельного действия для этого нет и не нужно:
    # для автора это такая же правка свойств страницы, как переименование.
    folder_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4096)
    icon_name: str | None = Field(default=None, max_length=128)
    order_key: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def require_change(self) -> "PageUpdateInput":
        if not self.model_fields_set - {"page_id"}:
            raise ValueError("At least one field must be changed")
        return self


class PageDeleteInput(BaseModel):
    page_id: UUID


class PageRestoreInput(BaseModel):
    page_id: UUID


class PageDeleteOutput(BaseModel):
    page_id: UUID
    deleted: bool


class BlockDeleteOutput(BaseModel):
    block_id: UUID
    deleted: bool


class BlockCreateInput(BaseModel):
    page_id: UUID
    block_type: str = Field(min_length=1)
    zone: str = Field(default="content", min_length=1)
    order_key: str | None = Field(default=None, max_length=512)
    data: Any = Field(default_factory=dict)


class BlockUpdateInput(BaseModel):
    block_id: UUID
    lease_id: UUID
    expected_block_version: int = Field(ge=1)
    data: Any


class BlockMoveInput(BaseModel):
    block_id: UUID
    lease_id: UUID
    expected_block_version: int = Field(ge=1)
    zone: str = Field(min_length=1)
    order_key: str = Field(max_length=512)


class BlockDeleteInput(BaseModel):
    block_id: UUID
    lease_id: UUID
    expected_block_version: int = Field(ge=1)


class BlockOpInput(BaseModel):
    """Одна правка внутри транзакции.

    `block_id` обязателен и для создания: id блока придумывает клиент. Это не
    прихоть — без него блок не существует до ответа сервера, и всё, что человек
    успел сделать за этот круг, некуда отнести. Заодно повтор транзакции,
    пережившей обрыв связи, не создаёт второй блок: id тот же.
    """

    op: Literal["create", "update", "delete", "move", "retype"]
    block_id: UUID
    block_type: str | None = Field(default=None, min_length=1)
    data: Any = None
    zone: str | None = Field(default=None, min_length=1)
    order_key: str | None = Field(default=None, max_length=512)
    expected_block_version: int | None = Field(default=None, ge=1)


class PageTransactionInput(BaseModel):
    """Пачка правок, применяемая целиком или не применяемая вовсе.

    Клиент собирает в транзакцию то, что для автора является одним действием:
    разделение строки по Enter — это правка одного блока и создание другого, и
    увидеть половину такого действия нельзя. По отдельности они и уходили —
    каждая своим запросом, — поэтому сбой посередине оставлял страницу
    наполовину изменённой.

    Блокировки берутся здесь же: отдельного `lease_id` на входе нет. Клиенту
    больше не нужно ходить за блокировкой перед каждой записью, а значит и
    терять её между двумя запросами больше негде.
    """

    page_id: UUID
    ops: list[BlockOpInput] = Field(min_length=1, max_length=200)


class PageTransactionOutput(BaseModel):
    blocks: list["BlockOutput"]
    deleted: list[UUID]


class BlockTypeChangeInput(BaseModel):
    block_id: UUID
    lease_id: UUID
    expected_block_version: int = Field(ge=1)
    block_type: str = Field(min_length=1)
    data: Any = Field(default_factory=dict)


class RevisionCreateInput(BaseModel):
    page_id: UUID
    name: str | None = Field(default=None, max_length=256)


class RevisionListInput(BaseModel):
    page_id: UUID


class RevisionGetInput(BaseModel):
    revision_id: UUID


class RevisionRestoreInput(BaseModel):
    revision_id: UUID


class RevisionOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_id: UUID
    event_sequence: int
    kind: str
    name: str | None
    snapshot: dict[str, Any]
    created_by: UUID
    created_at: datetime


class RevisionListOutput(BaseModel):
    revisions: list[RevisionOutput]


class PagePublishInput(BaseModel):
    page_id: UUID


class PageChanged(BaseModel):
    page_id: UUID


class BlockChanged(BaseModel):
    page_id: UUID
    block: BlockOutput | None = None
    block_id: UUID
    event_type: str


class BlockLockInput(BaseModel):
    block_id: UUID


class BlockLeaseInput(BaseModel):
    block_id: UUID
    lease_id: UUID


class BlockLockSwitchInput(BaseModel):
    current_block_id: UUID
    current_lease_id: UUID
    next_block_id: UUID


class BlockLeaseOutput(BaseModel):
    block_id: UUID
    lease_id: UUID
    user_id: UUID
    session_id: UUID
    expires_at: datetime


class BlockLockChanged(BaseModel):
    block_id: UUID
    lease: BlockLeaseOutput | None


PageGroupSetInput = Annotated[list[UUID], Field(min_length=1, max_length=32)]


class PageAccessListInput(BaseModel):
    page_id: UUID


class PageAccessSetInput(BaseModel):
    page_id: UUID
    role: Role
    group_sets: list[PageGroupSetInput] = Field(min_length=1, max_length=100)


class PageAccessRemoveInput(BaseModel):
    page_id: UUID
    role: Role


class PageAccessGroupOutput(BaseModel):
    id: UUID
    name: str


class PageRoleGroupConditionsOutput(BaseModel):
    role: Role
    group_sets: list[list[PageAccessGroupOutput]]


class PageAccessOutput(BaseModel):
    page_id: UUID
    roles: list[PageRoleGroupConditionsOutput]


class PageOwnerTransferInput(BaseModel):
    page_id: UUID
    target_group_id: UUID
