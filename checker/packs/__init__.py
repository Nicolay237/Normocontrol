# -*- coding: utf-8 -*-
"""
Дополнительные проверки («пакеты») — требования конкретного вуза сверх ГОСТ.

Сами правила живут в коде (модуль на пакет), а кому какой пакет доступен и с какими
настройками — хранится в базе (auth.py: таблицы check_packs и user_packs) и меняется
администратором в /admin. Настройки пакета — JSON; значения по умолчанию — DEFAULTS модуля.
"""

import json
from dataclasses import dataclass
from typing import Callable

from . import pgups


@dataclass(frozen=True)
class Pack:
    key: str
    title: str          # полное название для админки и отчёта
    short: str          # коротко, для чипа на странице проверки
    description: str
    profiles: tuple     # к каким типам работ применяется
    defaults: dict
    check: Callable     # check(checker, items, settings)


PACKS = {
    p.key: p for p in (
        Pack(
            key="pgups",
            title="ПГУПС: титульный лист, задание и начало работы",
            short="ПГУПС",
            description="Титульный лист (Приложение Ж), задание на ВКР (Приложение К) и порядок начальных "
                        "разделов по СМК РД 02.01.18-2021 «Порядок проведения ГИА».",
            profiles=("vkr",),
            defaults=pgups.DEFAULTS,
            check=pgups.check,
        ),
    )
}


def settings_for(key, raw=None):
    """Настройки пакета: значения по умолчанию, поверх — сохранённые в базе (JSON)."""
    merged = dict(PACKS[key].defaults)
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (ValueError, TypeError):
            data = {}
        merged.update({k: v for k, v in data.items() if k in merged})
    return merged


def run_packs(checker, items, packs):
    """packs — [(key, settings_json)] пакетов, доступных пользователю."""
    applied = []
    for key, raw in packs:
        pack = PACKS.get(key)
        if not pack:
            continue
        if checker.n["key"] not in pack.profiles:
            continue
        pack.check(checker, items, settings_for(key, raw))
        applied.append(pack)
    return applied
