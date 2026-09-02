"""wsapi actions материала нормоконтроля.

Материал советующий: он ничего не запрещает и ни на что не влияет — ни на
сдачи, ни на оценки. Это самостоятельный инструмент, которым студент
пользуется до того, как понесёт работу преподавателю.
"""

from app.folders.actions import translate_domain_error
from app.normocontrol.enums import RunStatus
from app.normocontrol.schemas import (
    NormocontrolPageInput,
    NormocontrolRunIdInput,
    NormocontrolRunOutput,
    NormocontrolSettingsInput,
    NormocontrolSettingsOutput,
    NormocontrolSubmitInput,
    NormocontrolViewOutput,
)
from app.normocontrol.service import NormocontrolService
from app.ws.api import ws_api
from app.ws.context import AppContext
from app.ws.errors import FOLDER_ERRORS

DOMAIN_ERRORS = (LookupError, PermissionError, ValueError)


def _service(ctx: AppContext) -> NormocontrolService:
    return NormocontrolService(ctx.db, ctx.access)


@ws_api.action(
    "normocontrol.open",
    input_type=NormocontrolPageInput,
    output_type=NormocontrolViewOutput,
    error_types=FOLDER_ERRORS,
    may_subscribe_to=("normocontrol.run.changed",),
)
async def normocontrol_open(
    ctx: AppContext, data: NormocontrolPageInput
) -> NormocontrolViewOutput:
    """Условие материала и доступные вызывающему проверки."""
    service = _service(ctx)
    try:
        settings = await service.get_settings(ctx.user_id, data.page_id)
        rows, reviewing_all = await service.visible_runs(ctx.user_id, data.page_id)
        runs = await service.to_outputs(rows, include_authors=reviewing_all)
        pending = await service.pending_count(ctx.user_id)
    except DOMAIN_ERRORS as exc:
        raise translate_domain_error(exc) from exc
    # The browser only installs a local callback; the server-side subscription
    # still has to be restored by an action. This is especially important after
    # a reload or reconnect while a document is already being checked.
    for row in rows:
        if row.status in (RunStatus.QUEUED.value, RunStatus.RUNNING.value):
            await ctx.subscribe("normocontrol.run.changed", str(row.id))
    return NormocontrolViewOutput(
        settings=settings,
        runs=runs,
        service_available=service.service_available(),
        pending=pending,
        reviewing_all=reviewing_all,
    )


@ws_api.action(
    "normocontrol.settings.get",
    input_type=NormocontrolPageInput,
    output_type=NormocontrolSettingsOutput,
    error_types=FOLDER_ERRORS,
)
async def normocontrol_settings_get(
    ctx: AppContext, data: NormocontrolPageInput
) -> NormocontrolSettingsOutput:
    try:
        return await _service(ctx).get_settings(ctx.user_id, data.page_id)
    except DOMAIN_ERRORS as exc:
        raise translate_domain_error(exc) from exc


@ws_api.action(
    "normocontrol.settings.set",
    input_type=NormocontrolSettingsInput,
    output_type=NormocontrolSettingsOutput,
    error_types=FOLDER_ERRORS,
)
async def normocontrol_settings_set(
    ctx: AppContext, data: NormocontrolSettingsInput
) -> NormocontrolSettingsOutput:
    try:
        return await _service(ctx).set_settings(ctx.user_id, ctx.session_id, data)
    except DOMAIN_ERRORS as exc:
        raise translate_domain_error(exc) from exc


@ws_api.action(
    "normocontrol.run.create",
    input_type=NormocontrolPageInput,
    output_type=NormocontrolRunOutput,
    error_types=FOLDER_ERRORS,
    may_subscribe_to=("normocontrol.run.changed",),
)
async def normocontrol_run_create(
    ctx: AppContext, data: NormocontrolPageInput
) -> NormocontrolRunOutput:
    """Открыть проверку. Документ грузится уже в неё — см. docs/normocontrol.md."""
    service = _service(ctx)
    try:
        run = await service.create_run(ctx.user_id, data.page_id)
        # Subscribe before the file upload and queueing: a small document may
        # finish before the following view refresh has installed a subscription.
        await ctx.subscribe("normocontrol.run.changed", str(run.id))
        return await service.to_output(run)
    except DOMAIN_ERRORS as exc:
        raise translate_domain_error(exc) from exc


@ws_api.action(
    "normocontrol.run.submit",
    input_type=NormocontrolSubmitInput,
    output_type=NormocontrolRunOutput,
    error_types=FOLDER_ERRORS,
    may_subscribe_to=("normocontrol.run.changed",),
)
async def normocontrol_run_submit(
    ctx: AppContext, data: NormocontrolSubmitInput
) -> NormocontrolRunOutput:
    """Поставить документ в очередь. Отчёт приедет sync-событием."""
    service = _service(ctx)
    try:
        run = await service.submit(
            ctx.user_id, ctx.session_id, data.run_id, data.file_id
        )
        await ctx.subscribe("normocontrol.run.changed", str(run.id))
        return await service.to_output(run)
    except DOMAIN_ERRORS as exc:
        raise translate_domain_error(exc) from exc


@ws_api.action(
    "normocontrol.run.get",
    input_type=NormocontrolRunIdInput,
    output_type=NormocontrolRunOutput,
    error_types=FOLDER_ERRORS,
    may_subscribe_to=("normocontrol.run.changed",),
)
async def normocontrol_run_get(
    ctx: AppContext, data: NormocontrolRunIdInput
) -> NormocontrolRunOutput:
    service = _service(ctx)
    try:
        run = await service.get_run(ctx.user_id, data.run_id)
        await ctx.subscribe("normocontrol.run.changed", str(run.id))
        return await service.to_output(run)
    except DOMAIN_ERRORS as exc:
        raise translate_domain_error(exc) from exc


@ws_api.action(
    "normocontrol.run.cancel",
    input_type=NormocontrolRunIdInput,
    output_type=NormocontrolRunOutput,
    error_types=FOLDER_ERRORS,
)
async def normocontrol_run_cancel(
    ctx: AppContext, data: NormocontrolRunIdInput
) -> NormocontrolRunOutput:
    """Снять свою проверку, пока её не взяли в работу."""
    service = _service(ctx)
    try:
        run = await service.cancel(ctx.user_id, data.run_id)
        return await service.to_output(run)
    except DOMAIN_ERRORS as exc:
        raise translate_domain_error(exc) from exc
