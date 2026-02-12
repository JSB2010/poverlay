from __future__ import annotations

from typing import TypedDict

# Firestore collection IDs are centralized here so every API module uses the same
# top-level paths and document contracts.
FIRESTORE_COLLECTION_USERS = "users"
FIRESTORE_COLLECTION_JOBS = "jobs"
FIRESTORE_COLLECTION_MEDIA = "media"


class FirestoreUserDocument(TypedDict, total=False):
    uid: str
    email: str
    display_name: str
    notifications_enabled: bool
    created_at: str
    updated_at: str


class FirestoreJobDocument(TypedDict, total=False):
    id: str
    uid: str
    job_dir: str
    status: str
    progress: int
    message: str
    gpx_name: str
    videos: list["FirestoreJobVideoDocument"]
    settings: dict[str, object]
    created_at: str
    updated_at: str
    started_at: str
    finished_at: str
    expires_at: str
    local_artifacts_deleted_at: str


class FirestoreJobVideoDocument(TypedDict, total=False):
    input_name: str
    status: str
    progress: int
    detail: str
    error: str
    output_name: str
    output_size_bytes: int
    log_name: str
    render_profile: str
    render_profile_label: str
    source_resolution: str
    source_fps: str
    r2_object_key: str
    r2_bucket: str
    r2_etag: str
    r2_uploaded_at: str


class FirestoreMediaDocument(TypedDict, total=False):
    id: str
    uid: str
    job_id: str
    filename: str
    content_type: str
    size_bytes: int
    r2_object_key: str
    created_at: str
    updated_at: str


def _sanitize_r2_path_segment(value: str) -> str:
    return value.strip().replace("\\", "_").replace("/", "_")


def build_r2_output_object_key(user_id: str, job_id: str, filename: str) -> str:
    """
    Canonical object-key contract for rendered assets in R2.

    users/{uid}/jobs/{jobId}/outputs/{filename}
    """

    safe_user_id = _sanitize_r2_path_segment(user_id)
    safe_job_id = _sanitize_r2_path_segment(job_id)
    safe_filename = _sanitize_r2_path_segment(filename)
    return f"users/{safe_user_id}/jobs/{safe_job_id}/outputs/{safe_filename}"
