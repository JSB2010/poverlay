from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from app.contracts import (
    FIRESTORE_COLLECTION_JOBS,
    FIRESTORE_COLLECTION_MEDIA,
    FIRESTORE_COLLECTION_USERS,
)

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}


def _read_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _BOOL_TRUE:
        return True
    if normalized in _BOOL_FALSE:
        return False
    raise RuntimeError(f"Invalid boolean for {name}: {raw!r}. Use one of: true/false, 1/0, yes/no, on/off.")


def _read_float(name: str, default: float, minimum: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid numeric value for {name}: {raw!r}.") from exc
    if value < minimum:
        raise RuntimeError(f"Invalid value for {name}: {value}. Must be >= {minimum}.")
    return value


def _read_int(name: str, default: int, minimum: int) -> int:
    value = int(_read_float(name, float(default), float(minimum)))
    if value < minimum:
        raise RuntimeError(f"Invalid value for {name}: {value}. Must be >= {minimum}.")
    return value


def _read_optional(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _read_required(name: str, value: str | None, errors: list[str]) -> str | None:
    if value:
        return value
    errors.append(f"{name} is required for the enabled integration.")
    return None


def _read_cors_origins() -> tuple[str, ...]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = tuple(origin.strip() for origin in raw.split(",") if origin.strip())
    if not origins:
        raise RuntimeError("CORS_ORIGINS cannot be empty.")
    return origins


@dataclass(frozen=True)
class FirebaseConfig:
    auth_enabled: bool
    project_id: str | None
    credentials_json: str | None
    credentials_path: str | None
    admin_client_email: str | None
    admin_private_key: str | None
    admin_private_key_base64: str | None
    admin_private_key_path: Path | None
    web_api_key: str | None
    web_auth_domain: str | None
    web_project_id: str | None
    web_app_id: str | None
    web_messaging_sender_id: str | None
    web_storage_bucket: str | None


@dataclass(frozen=True)
class FirestoreConfig:
    enabled: bool
    project_id: str | None
    database_id: str
    users_collection: str
    jobs_collection: str
    media_collection: str


@dataclass(frozen=True)
class R2Config:
    upload_enabled: bool
    account_id: str | None
    access_key_id: str | None
    secret_access_key: str | None
    bucket: str | None
    region: str
    endpoint: str | None
    public_base_url: str | None


@dataclass(frozen=True)
class BrevoConfig:
    notifications_enabled: bool
    api_key: str | None
    sender_email: str | None
    sender_name: str
    template_render_complete_id: str | None


@dataclass(frozen=True)
class ApiRuntimeConfig:
    data_dir: Path
    gopro_dashboard_bin: str
    ffprobe_bin: str
    overlay_font_path: str
    cors_origins: tuple[str, ...]
    job_cleanup_enabled: bool
    job_cleanup_interval_seconds: int
    job_output_retention_hours: float
    delete_inputs_on_complete: bool
    delete_work_on_complete: bool
    api_base_url: str
    web_base_url: str
    firebase: FirebaseConfig
    firestore: FirestoreConfig
    r2: R2Config
    brevo: BrevoConfig


def load_runtime_config(*, repo_root: Path, service_root: Path) -> ApiRuntimeConfig:
    data_dir = Path(os.environ.get("POVERLAY_DATA_DIR", str(repo_root / "data"))).expanduser()

    local_dashboard_bin = repo_root / "scripts" / "gopro-dashboard-local.sh"
    dashboard_default = local_dashboard_bin if local_dashboard_bin.exists() else (repo_root / ".venv" / "bin" / "gopro-dashboard.py")

    firebase_project_id = _read_optional("FIREBASE_PROJECT_ID")
    firebase_admin_client_email = _read_optional("FIREBASE_ADMIN_CLIENT_EMAIL")
    firebase_admin_private_key = _read_optional("FIREBASE_ADMIN_PRIVATE_KEY")
    if firebase_admin_private_key:
        firebase_admin_private_key = firebase_admin_private_key.replace("\\n", "\n")

    firebase_admin_private_key_base64 = _read_optional("FIREBASE_ADMIN_PRIVATE_KEY_BASE64")
    firebase_admin_private_key_path_raw = _read_optional("FIREBASE_ADMIN_PRIVATE_KEY_PATH")
    firebase_admin_private_key_path = Path(firebase_admin_private_key_path_raw).expanduser() if firebase_admin_private_key_path_raw else None

    firebase = FirebaseConfig(
        auth_enabled=_read_bool("FIREBASE_AUTH_ENABLED", False),
        project_id=firebase_project_id,
        credentials_json=_read_optional("FIREBASE_CREDENTIALS_JSON"),
        credentials_path=_read_optional("FIREBASE_CREDENTIALS_PATH") or _read_optional("GOOGLE_APPLICATION_CREDENTIALS"),
        admin_client_email=firebase_admin_client_email,
        admin_private_key=firebase_admin_private_key,
        admin_private_key_base64=firebase_admin_private_key_base64,
        admin_private_key_path=firebase_admin_private_key_path,
        web_api_key=_read_optional("NEXT_PUBLIC_FIREBASE_API_KEY"),
        web_auth_domain=_read_optional("NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN"),
        web_project_id=_read_optional("NEXT_PUBLIC_FIREBASE_PROJECT_ID"),
        web_app_id=_read_optional("NEXT_PUBLIC_FIREBASE_APP_ID"),
        web_messaging_sender_id=_read_optional("NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID"),
        web_storage_bucket=_read_optional("NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET"),
    )

    firestore = FirestoreConfig(
        enabled=_read_bool("FIRESTORE_ENABLED", False),
        project_id=_read_optional("FIRESTORE_PROJECT_ID") or firebase_project_id,
        database_id=os.environ.get("FIRESTORE_DATABASE_ID", "(default)"),
        users_collection=os.environ.get("FIRESTORE_COLLECTION_USERS", FIRESTORE_COLLECTION_USERS),
        jobs_collection=os.environ.get("FIRESTORE_COLLECTION_JOBS", FIRESTORE_COLLECTION_JOBS),
        media_collection=os.environ.get("FIRESTORE_COLLECTION_MEDIA", FIRESTORE_COLLECTION_MEDIA),
    )

    r2_account_id = _read_optional("R2_ACCOUNT_ID")
    r2_endpoint = _read_optional("R2_ENDPOINT")
    if not r2_endpoint and r2_account_id:
        r2_endpoint = f"https://{r2_account_id}.r2.cloudflarestorage.com"

    r2 = R2Config(
        upload_enabled=_read_bool("R2_UPLOAD_ENABLED", False),
        account_id=r2_account_id,
        access_key_id=_read_optional("R2_ACCESS_KEY_ID"),
        secret_access_key=_read_optional("R2_SECRET_ACCESS_KEY"),
        bucket=_read_optional("R2_BUCKET"),
        region=os.environ.get("R2_REGION", "auto"),
        endpoint=r2_endpoint,
        public_base_url=_read_optional("R2_PUBLIC_BASE_URL"),
    )

    brevo = BrevoConfig(
        notifications_enabled=_read_bool("BREVO_NOTIFICATIONS_ENABLED", False),
        api_key=_read_optional("BREVO_API_KEY"),
        sender_email=_read_optional("BREVO_SENDER_EMAIL"),
        sender_name=os.environ.get("BREVO_SENDER_NAME", "POVerlay"),
        template_render_complete_id=_read_optional("BREVO_TEMPLATE_RENDER_COMPLETE_ID"),
    )

    config = ApiRuntimeConfig(
        data_dir=data_dir,
        gopro_dashboard_bin=os.environ.get("GOPRO_DASHBOARD_BIN", str(dashboard_default)),
        ffprobe_bin=os.environ.get("FFPROBE_BIN", "ffprobe"),
        overlay_font_path=os.environ.get("OVERLAY_FONT_PATH", str(service_root / "app" / "static" / "fonts" / "Orbitron-Bold.ttf")),
        cors_origins=_read_cors_origins(),
        job_cleanup_enabled=_read_bool("JOB_CLEANUP_ENABLED", True),
        job_cleanup_interval_seconds=_read_int("JOB_CLEANUP_INTERVAL_SECONDS", 900, 60),
        job_output_retention_hours=_read_float("JOB_OUTPUT_RETENTION_HOURS", 24.0, 1.0),
        delete_inputs_on_complete=_read_bool("DELETE_INPUTS_ON_COMPLETE", True),
        delete_work_on_complete=_read_bool("DELETE_WORK_ON_COMPLETE", True),
        api_base_url=os.environ.get("API_BASE_URL", "http://127.0.0.1:8787"),
        web_base_url=os.environ.get("WEB_BASE_URL", "http://127.0.0.1:3000"),
        firebase=firebase,
        firestore=firestore,
        r2=r2,
        brevo=brevo,
    )

    _validate_runtime_config(config)
    return config


def _validate_runtime_config(config: ApiRuntimeConfig) -> None:
    errors: list[str] = []

    if config.firebase.auth_enabled:
        _read_required("FIREBASE_PROJECT_ID", config.firebase.project_id, errors)

        has_admin_key = bool(
            config.firebase.credentials_json
            or config.firebase.credentials_path
            or (
                config.firebase.admin_client_email
                and (
                    config.firebase.admin_private_key
                    or config.firebase.admin_private_key_base64
                    or config.firebase.admin_private_key_path
                )
            )
        )
        if not has_admin_key:
            errors.append(
                "One Firebase admin credential source is required when FIREBASE_AUTH_ENABLED=true: "
                "FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH (or GOOGLE_APPLICATION_CREDENTIALS) "
                "or FIREBASE_ADMIN_CLIENT_EMAIL + one private key source."
            )

        has_partial_admin_fields = bool(
            config.firebase.admin_private_key or config.firebase.admin_private_key_base64 or config.firebase.admin_private_key_path
        )
        if has_partial_admin_fields and not config.firebase.admin_client_email:
            errors.append("FIREBASE_ADMIN_CLIENT_EMAIL is required when using FIREBASE_ADMIN_PRIVATE_KEY* values.")

        if config.firebase.admin_private_key_path and not config.firebase.admin_private_key_path.is_file():
            errors.append(f"FIREBASE_ADMIN_PRIVATE_KEY_PATH file not found: {config.firebase.admin_private_key_path}")
        if config.firebase.credentials_path and not Path(config.firebase.credentials_path).expanduser().is_file():
            errors.append(f"FIREBASE_CREDENTIALS_PATH file not found: {config.firebase.credentials_path}")

    if config.firestore.enabled:
        _read_required("FIRESTORE_PROJECT_ID or FIREBASE_PROJECT_ID", config.firestore.project_id, errors)

    if config.r2.upload_enabled:
        _read_required("R2_ACCOUNT_ID", config.r2.account_id, errors)
        _read_required("R2_ACCESS_KEY_ID", config.r2.access_key_id, errors)
        _read_required("R2_SECRET_ACCESS_KEY", config.r2.secret_access_key, errors)
        _read_required("R2_BUCKET", config.r2.bucket, errors)
        _read_required("R2_ENDPOINT", config.r2.endpoint, errors)

    if config.brevo.notifications_enabled:
        _read_required("BREVO_API_KEY", config.brevo.api_key, errors)
        _read_required("BREVO_SENDER_EMAIL", config.brevo.sender_email, errors)

    for key, value in (("WEB_BASE_URL", config.web_base_url), ("API_BASE_URL", config.api_base_url)):
        if not value.startswith(("http://", "https://")):
            errors.append(f"{key} must start with http:// or https:// (received {value!r}).")

    if errors:
        details = "\n".join(f"- {item}" for item in errors)
        raise RuntimeError(
            "Invalid environment configuration:\n"
            f"{details}\n"
            "Copy root .env.example to .env and provide the required values for enabled integrations."
        )
