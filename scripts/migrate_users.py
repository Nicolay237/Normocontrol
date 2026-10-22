#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Перенос учётных записей из старой базы в новую (например, Neon → PostgreSQL Timeweb Cloud).

Запуск (в консоли приложения на Timeweb или локально):

    SOURCE_DATABASE_URL="postgresql://…старая…" DATABASE_URL="postgresql://…новая…" \
        python scripts/migrate_users.py

Логины, ФИО, хеши паролей, роли и статусы переносятся как есть — пароли у людей
не меняются. Если такой логин в новой базе уже есть (например, администратор,
созданный из ADMIN_LOGIN при первом запуске), запись обновляется данными из старой базы.
Скрипт можно запускать повторно: дублей не будет.
"""

import os
import re
import sys

from sqlalchemy import MetaData, Table, create_engine, select, insert, update

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import users, metadata  # noqa: E402

FIELDS = ("login", "name", "password_hash", "role", "active", "must_change_password",
          "session_version", "created_at", "last_login_at", "free_autofix", "registered", "subscription_until", "consent_at")


def _url(raw):
    return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", raw.strip())


def migrate(source_url, target_url, log=print):
    src = create_engine(_url(source_url), future=True)
    dst = create_engine(_url(target_url), future=True)
    metadata.create_all(dst)
    # в старой базе может не быть новых колонок — читаем таблицу такой, какая она есть
    old_users = Table("users", MetaData(), autoload_with=src)
    with src.connect() as c:
        rows = [dict(r) for r in c.execute(select(old_users)).mappings()]
    created = updated = 0
    with dst.begin() as c:
        for r in rows:
            data = {k: r[k] for k in FIELDS if k in r}
            # в базе до появления регистрации все учётки выдавал администратор — доступ бесплатный
            data.setdefault("free_autofix", True)
            data.setdefault("registered", False)
            exists = c.execute(select(users.c.id).where(users.c.login == r["login"])).first()
            if exists:
                c.execute(update(users).where(users.c.login == r["login"]).values(**data))
                updated += 1
            else:
                c.execute(insert(users).values(**data))
                created += 1
    log(f"Перенесено учётных записей: {len(rows)} (новых {created}, обновлено {updated})")
    return created, updated


if __name__ == "__main__":
    source = os.environ.get("SOURCE_DATABASE_URL")
    target = os.environ.get("DATABASE_URL")
    if not source or not target:
        sys.exit("Нужно задать SOURCE_DATABASE_URL (старая база) и DATABASE_URL (новая база).")
    if _url(source) == _url(target):
        sys.exit("Старая и новая база совпадают — переносить нечего.")
    migrate(source, target)
