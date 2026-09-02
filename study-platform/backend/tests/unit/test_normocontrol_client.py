"""Граница с внешним сервисом: что мы обязаны пережить без правок."""

import json

import httpx
import pytest

from app.normocontrol.client import (
    NormocontrolClient,
    NormocontrolClientError,
    validate_envelope,
)
from app.normocontrol.enums import FailureReason

REPORT = {
    "filename": "vkr.docx",
    "generatedAt": "2026-09-02T08:16:15+00:00",
    "isClean": False,
    "totalIssues": 2,
    "notes": ["PDF не хранит структуру абзацев."],
    "categories": [
        {
            "name": "Поля страницы",
            "issues": [{"location": "Раздел №1", "message": "левое поле 2.0 см"}],
        },
        {
            "name": "Кегль шрифта",
            "issues": [{"location": "Абзац 12", "message": "12 pt вместо 14 pt"}],
        },
    ],
}


def _client(handler, **kwargs) -> NormocontrolClient:
    return NormocontrolClient(
        base_url="http://normocontrol:8080",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def _ok(payload):
    return lambda request: httpx.Response(200, json=payload)


# --- конверт ----------------------------------------------------------------


def test_envelope_of_the_current_service_is_accepted() -> None:
    total, is_clean, schema = validate_envelope(REPORT)

    assert (total, is_clean, schema) == (2, False, "1")


def test_unknown_categories_need_no_code_change() -> None:
    """Углубление проверок — это новые категории, и они должны проезжать сами."""
    payload = {
        **REPORT,
        "totalIssues": 3,
        "categories": [
            *REPORT["categories"],
            {
                "name": "Оформление формул",
                "issues": [{"location": "с. 14", "message": "формула без номера"}],
            },
        ],
    }

    total, _, _ = validate_envelope(payload)

    assert total == 3


def test_extra_fields_are_not_a_reason_to_refuse() -> None:
    """Новые необязательные поля обязаны проезжать без адаптации."""
    payload = {
        **REPORT,
        "durationMs": 1234,
        "totalIssues": 1,
        "categories": [
            {
                "name": "Поля страницы",
                "issues": [
                    {
                        "location": "Раздел №1",
                        "message": "левое поле 2.0 см",
                        "severity": "warning",
                        "anchor": {"page": 3, "paragraph": 17},
                    }
                ],
            }
        ],
    }

    total, _, _ = validate_envelope(payload)

    assert total == 1


def test_totals_are_recomputed_when_the_service_omits_them() -> None:
    payload = {"categories": REPORT["categories"]}

    total, is_clean, _ = validate_envelope(payload)

    assert (total, is_clean) == (2, False)


def test_clean_document_is_reported_as_clean() -> None:
    total, is_clean, _ = validate_envelope({"categories": [], "notes": []})

    assert (total, is_clean) == (0, True)


@pytest.mark.parametrize(
    "payload",
    [
        {"categories": "не список"},
        {"categories": [{"issues": []}]},
        {"categories": [{"name": "Поля", "issues": [{"message": "без location"}]}]},
        "не объект",
    ],
)
def test_broken_envelope_is_refused(payload) -> None:
    """Ломается только структура конверта, и тогда мы честно отказываемся."""
    with pytest.raises(NormocontrolClientError) as info:
        validate_envelope(payload)

    assert info.value.reason == FailureReason.INCOMPATIBLE_REPORT


def test_unknown_major_schema_is_refused_instead_of_guessed() -> None:
    with pytest.raises(NormocontrolClientError) as info:
        validate_envelope({**REPORT, "schemaVersion": "2.0"})

    assert info.value.reason == FailureReason.INCOMPATIBLE_REPORT


def test_minor_schema_bump_still_passes() -> None:
    total, _, schema = validate_envelope({**REPORT, "schemaVersion": "1.4"})

    assert (total, schema) == (2, "1.4")


# --- транспорт --------------------------------------------------------------


async def test_report_is_stored_verbatim() -> None:
    """Ответ уходит в базу целиком: перепроецировать дешевле, чем пересчитать."""
    report = await _client(_ok(REPORT)).check(b"docx", "vkr.docx")

    assert report.raw == REPORT
    assert report.total_issues == 2
    assert report.is_clean is False


async def test_version_is_optional() -> None:
    """Сегодня сервис `/version` не отдаёт — это не повод падать."""
    version = await _client(lambda request: httpx.Response(404)).version()

    assert (version.checker, version.schema, version.norms) == ("", "", "")


async def test_version_is_used_when_present() -> None:
    payload = {
        "checkerVersion": "1.4.0",
        "schemaVersion": "1",
        "normsVersion": "gost-7.32-2017",
    }

    version = await _client(_ok(payload)).version()

    assert version.checker == "1.4.0"
    assert version.norms == "gost-7.32-2017"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, FailureReason.DOCUMENT_REJECTED),
        (422, FailureReason.DOCUMENT_REJECTED),
        (413, FailureReason.FILE_TOO_LARGE),
        (500, FailureReason.SERVICE_UNAVAILABLE),
        (502, FailureReason.SERVICE_UNAVAILABLE),
    ],
)
async def test_service_status_becomes_a_stable_code(status, expected) -> None:
    def handler(request):
        return httpx.Response(status, json={"error": "внутренний текст"})

    with pytest.raises(NormocontrolClientError) as info:
        await _client(handler).check(b"x", "x.docx")

    # Текст сервиса наружу не идёт: он меняется вместе с его версиями.
    assert info.value.reason == expected


async def test_timeout_becomes_a_stable_code() -> None:
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(NormocontrolClientError) as info:
        await _client(handler).check(b"x", "x.docx")

    assert info.value.reason == FailureReason.TIMEOUT


async def test_unreachable_service_becomes_a_stable_code() -> None:
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(NormocontrolClientError) as info:
        await _client(handler).check(b"x", "x.docx")

    assert info.value.reason == FailureReason.SERVICE_UNAVAILABLE


async def test_oversized_report_is_refused() -> None:
    def handler(request):
        return httpx.Response(200, content=b"x" * 5000)

    with pytest.raises(NormocontrolClientError) as info:
        await _client(handler, max_bytes=1024).check(b"x", "x.docx")

    assert info.value.reason == FailureReason.INCOMPATIBLE_REPORT


async def test_non_json_answer_is_refused() -> None:
    def handler(request):
        return httpx.Response(200, content=b"<html>oops</html>")

    with pytest.raises(NormocontrolClientError) as info:
        await _client(handler).check(b"x", "x.docx")

    assert info.value.reason == FailureReason.INCOMPATIBLE_REPORT


async def test_document_is_sent_as_multipart_file() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content_type"] = request.headers.get("content-type", "")
        seen["body"] = request.content
        return httpx.Response(200, json=REPORT)

    await _client(handler).check(b"PK\x03\x04docx", "ВКР Хонина.docx")

    assert seen["content_type"].startswith("multipart/form-data")
    assert b"PK\x03\x04docx" in seen["body"]
    assert json.dumps("file") not in seen["content_type"]
