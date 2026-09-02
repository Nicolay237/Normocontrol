from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class NormocontrolCheck(Base):
    """Результат проверки одного содержимого.

    Ключ — не файл и не пользователь, а содержимое плюс версии проверяющего.
    В курсе ходит один методический шаблон: две сотни студентов приносят почти
    одинаковые файлы, и считать одно и то же двести раз незачем.

    Отдавать чужой результат безопасно: отчёт — функция от содержимого, и у
    того, кто принёс такой же файл, оно уже есть.

    Версии входят в ключ, поэтому обновление сервиса промахивается мимо кеша
    само — инвалидировать вручную нечего, а старые отчёты остаются читаемыми
    вместе с версией, при которой их получили.
    """

    __tablename__ = "normocontrol_checks"
    __table_args__ = (
        UniqueConstraint(
            "content_sha256",
            "checker_version",
            "schema_version",
            "norms_version",
            name="uq_normocontrol_checks_content_versions",
        ),
        Index("ix_normocontrol_checks_computed_at", "computed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Версии внешнего сервиса на момент расчёта. Пустая строка — сервис их не
    #: сообщил; такой результат тоже кешируется, но отдельно от версионных.
    checker_version: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    schema_version: Mapped[str] = mapped_column(
        String(16), default="", server_default="", nullable=False
    )
    norms_version: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    #: Ответ сервиса целиком, как пришёл. Хранится сырым нарочно: когда он
    #: добавит поля, историю можно будет перепроецировать, а не пересчитывать —
    #: самих документов у нас к тому времени уже не будет.
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    #: Проекция для списков, чтобы не разбирать JSONB на каждую строку.
    total_issues: Mapped[int] = mapped_column(Integer, nullable=False)
    is_clean: Mapped[bool] = mapped_column(Boolean, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NormocontrolRun(Base):
    """Одна проверка одного пользователя. Она же строка очереди.

    Очередь живёт в той же базе, что и всё остальное: брокера в проекте нет, а
    `FOR UPDATE SKIP LOCKED` даёт и durability, и возможность однажды запустить
    несколько потребителей без смены хранилища.

    Имя, размер и хеш продублированы здесь, а не читаются через `file_id`:
    документ удаляется сразу после проверки, а история должна остаться
    читаемой.
    """

    __tablename__ = "normocontrol_runs"
    __table_args__ = (
        Index("ix_normocontrol_runs_page_user", "page_id", "user_id"),
        Index("ix_normocontrol_runs_user_created", "user_id", "created_at"),
        #: По нему потребитель выбирает следующую задачу.
        Index("ix_normocontrol_runs_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    page_id: Mapped[UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    #: SET NULL: файл исчезает после проверки, сама проверка остаётся.
    file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL")
    )
    original_name: Mapped[str | None] = mapped_column(String(512))
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    size: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    check_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normocontrol_checks.id", ondelete="SET NULL")
    )
    #: Стабильный код из FailureReason. Текст внешнего сервиса сюда не идёт.
    error_code: Mapped[str | None] = mapped_column(String(32))
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    #: До какого момента задача считается взятой в работу. Потребитель, упавший
    #: вместе с процессом, иначе оставил бы её в `running` навсегда.
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NormocontrolSettings(Base):
    """Настройки материала. Одна строка на страницу с kind='normocontrol'."""

    __tablename__ = "normocontrol_settings"

    page_id: Mapped[UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True
    )
    instructions: Mapped[str | None] = mapped_column(Text)
    #: Материал советующий: он ничего не запрещает и ни на что не влияет.
    #: Флаг оставлен на случай, когда преподаватель захочет временно закрыть
    #: приём — например, пока сервис проверок недоступен.
    accepting: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
