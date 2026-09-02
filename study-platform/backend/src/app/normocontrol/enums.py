from enum import StrEnum

#: Ресурс, к которому привязывается загруженный документ. Свой, а не `page`:
#: вложение страницы скачал бы любой, у кого есть доступ к материалу, — та же
#: причина, что и у сдач лабораторных.
RUN_RESOURCE_TYPE = "normocontrol_run"


class RunStatus(StrEnum):
    """Состояние одной проверки.

    `draft` существует потому, что файл привязывается к ресурсу в момент
    загрузки: цель привязки должна появиться раньше самого файла.
    """

    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: Из этих состояний работа уже не сдвинется сама.
TERMINAL_STATUSES = frozenset(
    {RunStatus.DONE, RunStatus.FAILED, RunStatus.CANCELLED}
)


class FailureReason(StrEnum):
    """Стабильные коды отказа.

    Текст внешнего сервиса наружу не идёт: он меняется вместе с его версиями,
    а интерфейсу нужно на что-то опираться.
    """

    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    FILE_MISSING = "file_missing"
    #: Документ не разобрался — испорчен или защищён паролем.
    DOCUMENT_REJECTED = "document_rejected"
    #: Сервис не ответил вовремя.
    TIMEOUT = "timeout"
    #: Сервис недоступен или ответил ошибкой.
    SERVICE_UNAVAILABLE = "service_unavailable"
    #: Ответ пришёл, но не той формы, которую мы понимаем.
    INCOMPATIBLE_REPORT = "incompatible_report"
    #: Неожиданная ошибка внутри обработчика после всех автоматических повторов.
    PROCESSING_ERROR = "processing_error"
