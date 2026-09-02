"""Адаптер к внешнему сервису проверок.

Здесь проходит вся граница с чужим кодом. Сервис переписывается своей командой
и будет меняться часто — договорённость касается не его внутренностей, а формы
ответа:

    { "isClean": bool, "totalIssues": int, "notes": [str],
      "categories": [ { "name": str,
                        "issues": [ { "location": str, "message": str } ] } ] }

Имена категорий и тексты замечаний — обычные данные. Новые проверки приносят
новые категории, и это нормальный ход вещей: ни перечислений в коде, ни
справочника в базе для них нет, иначе каждое обновление требовало бы миграции.

Всё, что сверх обязательных полей, сохраняется как есть и уходит наверх
нетронутым: когда сервис начнёт отдавать, скажем, привязку к странице, бэкенд
пронесёт её без единой правки.
"""

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.normocontrol.enums import FailureReason

#: Какие мажорные версии конверта мы понимаем. Ответ без версии считается
#: первой: сервис её пока не присылает, а форма у него именно такая.
SUPPORTED_SCHEMA_MAJORS = frozenset({"1"})
ASSUMED_SCHEMA_VERSION = "1"


class NormocontrolClientError(Exception):
    """Отказ, о котором есть что сказать интерфейсу."""

    def __init__(self, reason: FailureReason, detail: str = "") -> None:
        super().__init__(reason.value if not detail else f"{reason.value}: {detail}")
        self.reason = reason


@dataclass(frozen=True)
class ServiceVersion:
    checker: str = ""
    schema: str = ""
    norms: str = ""


@dataclass(frozen=True)
class NormocontrolReport:
    #: Ответ сервиса целиком. Именно он ложится в базу.
    raw: dict[str, Any]
    total_issues: int
    is_clean: bool
    version: ServiceVersion


def _major(version: str) -> str:
    return version.strip().split(".")[0] if version.strip() else ""


def validate_envelope(payload: Any) -> tuple[int, bool, str]:
    """Проверяет только то, на что мы опираемся, и ничего больше.

    Возвращает `(totalIssues, isClean, schemaVersion)`. Всё остальное в ответе
    нас не касается — в том числе поля, которых сегодня ещё нет.
    """

    if not isinstance(payload, dict):
        raise NormocontrolClientError(
            FailureReason.INCOMPATIBLE_REPORT, "not an object"
        )

    schema_version = str(payload.get("schemaVersion") or ASSUMED_SCHEMA_VERSION)
    if _major(schema_version) not in SUPPORTED_SCHEMA_MAJORS:
        # Гадать по незнакомому конверту хуже, чем честно отказаться.
        raise NormocontrolClientError(
            FailureReason.INCOMPATIBLE_REPORT, f"schema {schema_version}"
        )

    categories = payload.get("categories")
    if not isinstance(categories, list):
        raise NormocontrolClientError(
            FailureReason.INCOMPATIBLE_REPORT, "categories missing"
        )

    counted = 0
    for category in categories:
        if not isinstance(category, dict) or not isinstance(category.get("name"), str):
            raise NormocontrolClientError(
                FailureReason.INCOMPATIBLE_REPORT, "category shape"
            )
        issues = category.get("issues")
        if not isinstance(issues, list):
            raise NormocontrolClientError(
                FailureReason.INCOMPATIBLE_REPORT, "issues missing"
            )
        for issue in issues:
            if not isinstance(issue, dict) or not all(
                isinstance(issue.get(field), str) for field in ("location", "message")
            ):
                raise NormocontrolClientError(
                    FailureReason.INCOMPATIBLE_REPORT, "issue shape"
                )
            counted += 1

    total = payload.get("totalIssues")
    total_issues = total if isinstance(total, int) and total >= 0 else counted
    is_clean = payload.get("isClean")
    if not isinstance(is_clean, bool):
        is_clean = total_issues == 0
    return total_issues, is_clean, schema_version


@dataclass
class NormocontrolClient:
    """HTTP-клиент сервиса. Адрес задаёт администратор, не пользователь."""

    base_url: str
    timeout: float = 120.0
    max_bytes: int = 4 * 1024 * 1024
    transport: httpx.AsyncBaseTransport | None = None

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    async def _read(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self.max_bytes:
                raise NormocontrolClientError(
                    FailureReason.INCOMPATIBLE_REPORT, "response too large"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    async def version(self) -> ServiceVersion:
        """Версии сервиса. Их может не быть — это не отказ."""

        try:
            async with httpx.AsyncClient(
                timeout=min(self.timeout, 10.0), transport=self.transport
            ) as client:
                response = await client.get(self._url("/version"))
                if response.status_code != 200:
                    return ServiceVersion()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            return ServiceVersion()
        if not isinstance(payload, dict):
            return ServiceVersion()
        return ServiceVersion(
            checker=str(payload.get("checkerVersion") or "")[:64],
            schema=str(payload.get("schemaVersion") or "")[:16],
            norms=str(payload.get("normsVersion") or "")[:64],
        )

    async def check(
        self, content: bytes, filename: str, version: ServiceVersion | None = None
    ) -> NormocontrolReport:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self.transport
            ) as client:
                request = client.build_request(
                    "POST",
                    self._url("/api/check"),
                    files={"file": (filename, content)},
                )
                response = await client.send(request, stream=True)
                try:
                    body = await self._read(response)
                finally:
                    await response.aclose()
        except httpx.TimeoutException as exc:
            raise NormocontrolClientError(FailureReason.TIMEOUT) from exc
        except httpx.HTTPError as exc:
            raise NormocontrolClientError(FailureReason.SERVICE_UNAVAILABLE) from exc

        if response.status_code in (400, 415, 422):
            # Сервис разобрался и отказался: дело в документе, повторять
            # бессмысленно.
            raise NormocontrolClientError(FailureReason.DOCUMENT_REJECTED)
        if response.status_code == 413:
            raise NormocontrolClientError(FailureReason.FILE_TOO_LARGE)
        if response.status_code != 200:
            raise NormocontrolClientError(FailureReason.SERVICE_UNAVAILABLE)

        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise NormocontrolClientError(
                FailureReason.INCOMPATIBLE_REPORT, "not json"
            ) from exc

        total_issues, is_clean, schema_version = validate_envelope(payload)
        resolved = version or ServiceVersion()
        return NormocontrolReport(
            raw=payload,
            total_issues=total_issues,
            is_clean=is_clean,
            version=ServiceVersion(
                checker=resolved.checker,
                schema=resolved.schema or schema_version,
                norms=resolved.norms,
            ),
        )
