"""Материал нормоконтроля: очередь проверок и кеш результатов.

Сама проверка живёт во внешнем сервисе; здесь только очередь, история и
результаты.

Результат ключуется содержимым документа и версиями сервиса, а не файлом и не
пользователем: по курсу ходит один методический шаблон, и считать одно и то же
сотни раз незачем. Версии в ключе заодно решают вопрос обновлений — новый
чекер промахивается мимо кеша сам, а старые отчёты остаются читаемыми вместе с
версией, при которой их получили.

Ответ сервиса хранится сырым (`raw`). Он будет дорабатываться и приносить
новые поля; сохранив ответ целиком, историю можно будет перепроецировать, а не
пересчитывать — самих документов к тому времени уже не будет, они удаляются
сразу после проверки.

Очередь — обычная таблица: брокера в проекте нет, а `FOR UPDATE SKIP LOCKED`
переживает перезапуск и не потребует переезда, если потребителей однажды
станет несколько.

Revision ID: 0023_normocontrol
Revises: 0022_lab_git_commit_author
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_normocontrol"
down_revision = "0022_lab_git_commit_author"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()

    if "normocontrol_checks" not in tables:
        op.create_table(
            "normocontrol_checks",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("content_sha256", sa.String(64), nullable=False),
            # Пустая строка, а не NULL: значение входит в уникальный ключ, а
            # NULL в нём не сравнивается сам с собой и ломал бы дедупликацию.
            sa.Column(
                "checker_version", sa.String(64), nullable=False, server_default=""
            ),
            sa.Column(
                "schema_version", sa.String(16), nullable=False, server_default=""
            ),
            sa.Column(
                "norms_version", sa.String(64), nullable=False, server_default=""
            ),
            sa.Column(
                "raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False
            ),
            sa.Column("total_issues", sa.Integer(), nullable=False),
            sa.Column("is_clean", sa.Boolean(), nullable=False),
            sa.Column(
                "computed_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "content_sha256",
                "checker_version",
                "schema_version",
                "norms_version",
                name="uq_normocontrol_checks_content_versions",
            ),
        )
        op.create_index(
            "ix_normocontrol_checks_computed_at",
            "normocontrol_checks",
            ["computed_at"],
        )

    if "normocontrol_runs" not in tables:
        op.create_table(
            "normocontrol_runs",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "page_id",
                sa.Uuid(),
                sa.ForeignKey("pages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            # SET NULL: документ удаляется сразу после проверки, сама проверка
            # остаётся в истории.
            sa.Column(
                "file_id",
                sa.Uuid(),
                sa.ForeignKey("files.id", ondelete="SET NULL"),
            ),
            sa.Column("original_name", sa.String(512)),
            sa.Column("content_sha256", sa.String(64)),
            sa.Column("size", sa.Integer()),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column(
                "check_id",
                sa.Uuid(),
                sa.ForeignKey("normocontrol_checks.id", ondelete="SET NULL"),
            ),
            sa.Column("error_code", sa.String(32)),
            sa.Column(
                "attempts", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("queued_at", sa.DateTime(timezone=True)),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
        )
        op.create_index(
            "ix_normocontrol_runs_page_user",
            "normocontrol_runs",
            ["page_id", "user_id"],
        )
        op.create_index(
            "ix_normocontrol_runs_user_created",
            "normocontrol_runs",
            ["user_id", "created_at"],
        )
        # По нему потребитель выбирает следующую задачу.
        op.create_index(
            "ix_normocontrol_runs_status_created",
            "normocontrol_runs",
            ["status", "created_at"],
        )

    if "normocontrol_settings" not in tables:
        op.create_table(
            "normocontrol_settings",
            sa.Column(
                "page_id",
                sa.Uuid(),
                sa.ForeignKey("pages.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("instructions", sa.Text()),
            sa.Column(
                "accepting", sa.Boolean(), nullable=False, server_default="true"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )


def downgrade() -> None:
    tables = _tables()
    if "normocontrol_settings" in tables:
        op.drop_table("normocontrol_settings")
    if "normocontrol_runs" in tables:
        for index in (
            "ix_normocontrol_runs_status_created",
            "ix_normocontrol_runs_user_created",
            "ix_normocontrol_runs_page_user",
        ):
            op.drop_index(index, table_name="normocontrol_runs")
        op.drop_table("normocontrol_runs")
    if "normocontrol_checks" in tables:
        op.drop_index(
            "ix_normocontrol_checks_computed_at", table_name="normocontrol_checks"
        )
        op.drop_table("normocontrol_checks")
