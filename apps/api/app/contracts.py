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
    status: str
    progress: int
    message: str
    created_at: str
    updated_at: str
    completed_at: str


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
