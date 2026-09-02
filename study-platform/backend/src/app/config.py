from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://platform:platform@localhost:5432/platform"
    database_null_pool: bool = False

    files_root: Path = Path("/data/files")
    max_upload_size: int = 1024 * 1024 * 1024
    max_avatar_size: int = 512 * 1024

    access_token_ttl_seconds: int = 3600
    session_ttl_seconds: int = 60 * 60 * 24 * 30

    ws_heartbeat_seconds: int = 20
    ws_action_timeout_seconds: int = 30
    ws_max_message_size: int = 1024 * 1024
    ws_allowed_origins: list[str] = Field(default_factory=list)
    ws_actions_per_minute: int = 240
    max_chat_message_length: int = 10_000
    max_block_data_size: int = 256 * 1024
    max_page_input_event_batch: int = 100
    max_attempt_event_batch: int = 100
    max_event_payload_size: int = 64 * 1024
    max_import_records: int = 50_000

    block_lock_ttl_seconds: int = 60
    block_lock_heartbeat_seconds: int = 10

    revision_checkpoint_event_count: int = 100
    background_cleanup_seconds: int = 60

    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str | None = None

    #: Ключ authenticated encryption для токенов source control. Base64 от 32
    #: байт. Без него подключение репозиториев не работает — см.
    #: app/source_control/crypto.py.
    source_control_encryption_key: str | None = None
    #: Куда разрешено возвращать браузер после OAuth callback. Список точных
    #: адресов: сам callback ничего не берёт из query, кроме state.
    source_control_oauth_return_urls: list[str] = Field(default_factory=list)
    #: Точный redirect_uri, зарегистрированный в OAuth-приложении. Пусто —
    #: адрес собирается из входящего запроса, что верно только за прокси,
    #: который проставляет X-Forwarded-*.
    source_control_oauth_callback_url: str | None = None
    source_control_oauth_state_ttl_seconds: int = 600
    source_control_http_timeout_seconds: float = 10.0
    source_control_max_response_bytes: int = 2 * 1024 * 1024
    source_control_max_page_size: int = 100
    source_control_max_redirects: int = 3
    #: Необязательный bootstrap публичных инстансов. Пусто — инстансы заводит
    #: администратор через system.source_control.instances.create.
    source_control_github_client_id: str | None = None
    source_control_github_client_secret: str | None = None
    source_control_gitlab_client_id: str | None = None
    source_control_gitlab_client_secret: str | None = None

    #: Внутренний адрес сервиса нормоконтроля. Пусто — материал показывает,
    #: что проверка сейчас недоступна, и не принимает файлы. Сервис поднимается
    #: соседним контейнером без выхода в сеть, наружу не публикуется.
    normocontrol_base_url: str | None = None
    #: Проверка стостраничной работы занимает секунды и десятки секунд, поэтому
    #: таймаут щедрый — но конечный.
    normocontrol_timeout_seconds: float = 180.0
    normocontrol_max_file_size: int = 20 * 1024 * 1024
    normocontrol_max_report_bytes: int = 4 * 1024 * 1024
    normocontrol_allowed_extensions: list[str] = Field(
        default_factory=lambda: [".docx", ".pdf"]
    )
    #: Сколько проверок платформа ведёт одновременно. Ограничение не наше — на
    #: той стороне gunicorn с несколькими воркерами, и заваливать его незачем.
    normocontrol_concurrency: int = 2
    #: Одна выполняющаяся работа на пользователя: иначе человек с двумя
    #: десятками файлов займёт очередь целиком.
    normocontrol_user_concurrency: int = 1
    #: Сколько работ пользователь может держать в очереди. Понятный отказ лучше
    #: растущего ожидания.
    normocontrol_user_queue_limit: int = 5
    normocontrol_poll_seconds: float = 2.0
    #: Работа, взятая упавшим потребителем, вернётся в очередь через это время.
    normocontrol_lease_seconds: int = 600
    normocontrol_max_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
