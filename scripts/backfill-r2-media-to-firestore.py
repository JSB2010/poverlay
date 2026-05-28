#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_EXTENSIONS = (".mp4",)


@dataclass(frozen=True)
class R2MediaObject:
    uid: str
    job_id: str
    output_name: str
    object_key: str
    size_bytes: int
    etag: str | None
    last_modified: datetime | None


def _read_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_title(output_name: str) -> str:
    stem = Path(output_name).stem
    for suffix in ("-overlay", "_overlay"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem or output_name


def _video_id_for_key(object_key: str) -> str:
    return hashlib.sha1(object_key.encode("utf-8")).hexdigest()[:20]


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _firebase_private_key() -> str:
    raw = os.environ.get("FIREBASE_ADMIN_PRIVATE_KEY", "").strip()
    if raw:
        return raw.replace("\\n", "\n")

    raw_base64 = os.environ.get("FIREBASE_ADMIN_PRIVATE_KEY_BASE64", "").strip()
    if raw_base64:
        return base64.b64decode(raw_base64).decode("utf-8")

    path = os.environ.get("FIREBASE_ADMIN_PRIVATE_KEY_PATH", "").strip()
    if path:
        return Path(path).expanduser().read_text()

    return ""


def _firebase_service_account_payload() -> dict[str, Any] | None:
    raw_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "").strip()
    if raw_json:
        payload = json.loads(raw_json)
        if not isinstance(payload, dict):
            raise RuntimeError("FIREBASE_CREDENTIALS_JSON must be a JSON object")
        return payload

    client_email = os.environ.get("FIREBASE_ADMIN_CLIENT_EMAIL", "").strip()
    private_key = _firebase_private_key()
    if client_email and private_key:
        project_id = (
            os.environ.get("FIRESTORE_PROJECT_ID", "").strip()
            or os.environ.get("FIREBASE_PROJECT_ID", "").strip()
        )
        return {
            "type": "service_account",
            "project_id": project_id,
            "client_email": client_email,
            "private_key": private_key,
            "token_uri": "https://oauth2.googleapis.com/token",
        }

    return None


def _firestore_client() -> Any:
    from google.cloud import firestore
    from google.oauth2 import service_account

    project_id = (
        os.environ.get("FIRESTORE_PROJECT_ID", "").strip()
        or os.environ.get("FIREBASE_PROJECT_ID", "").strip()
    )
    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "(default)").strip() or "(default)"

    kwargs: dict[str, Any] = {}
    if project_id:
        kwargs["project"] = project_id

    payload = _firebase_service_account_payload()
    credentials_path = (
        os.environ.get("FIREBASE_CREDENTIALS_PATH", "").strip()
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    )
    if payload is not None:
        kwargs["credentials"] = service_account.Credentials.from_service_account_info(payload)
    elif credentials_path:
        kwargs["credentials"] = service_account.Credentials.from_service_account_file(credentials_path)

    try:
        return firestore.Client(database=database_id, **kwargs)
    except TypeError:
        return firestore.Client(**kwargs)


def _r2_client() -> Any:
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        aws_access_key_id=_required_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_required_env("R2_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("R2_REGION", "auto").strip() or "auto",
        endpoint_url=_required_env("R2_ENDPOINT"),
        config=BotoConfig(signature_version="s3v4"),
    )


def _parse_media_object(raw: dict[str, Any], *, extensions: tuple[str, ...]) -> R2MediaObject | None:
    key = str(raw.get("Key") or "")
    parts = key.split("/")
    if len(parts) < 6:
        return None
    if parts[0] != "users" or parts[2] != "jobs" or parts[4] != "outputs":
        return None

    output_name = "/".join(parts[5:]).strip()
    if not output_name or not output_name.lower().endswith(extensions):
        return None

    etag = raw.get("ETag")
    return R2MediaObject(
        uid=parts[1],
        job_id=parts[3],
        output_name=output_name,
        object_key=key,
        size_bytes=int(raw.get("Size") or 0),
        etag=etag.strip('"') if isinstance(etag, str) else None,
        last_modified=raw.get("LastModified") if isinstance(raw.get("LastModified"), datetime) else None,
    )


def _list_r2_media_objects(
    *,
    bucket: str,
    prefix: str,
    uid: str | None,
    extensions: tuple[str, ...],
    limit: int | None,
) -> list[R2MediaObject]:
    client = _r2_client()
    paginator = client.get_paginator("list_objects_v2")
    media: list[R2MediaObject] = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for raw in page.get("Contents", []):
            item = _parse_media_object(raw, extensions=extensions)
            if item is None:
                continue
            if uid and item.uid != uid:
                continue
            media.append(item)
            if limit is not None and len(media) >= limit:
                return media

    return media


def _job_document(uid: str, job_id: str, objects: list[R2MediaObject]) -> dict[str, Any]:
    now = _utc_now()
    uploaded_times = [item.last_modified for item in objects if item.last_modified is not None]
    created_at = _iso(min(uploaded_times)) if uploaded_times else now
    finished_at = _iso(max(uploaded_times)) if uploaded_times else now

    videos = []
    for item in sorted(objects, key=lambda value: value.output_name.lower()):
        uploaded_at = _iso(item.last_modified) or now
        videos.append(
            {
                "id": _video_id_for_key(item.object_key),
                "title": _safe_title(item.output_name),
                "input_name": "",
                "status": "completed",
                "progress": 100,
                "detail": "Backfilled from R2",
                "error": None,
                "output_name": item.output_name,
                "output_size_bytes": item.size_bytes,
                "log_name": None,
                "render_profile": None,
                "render_profile_label": None,
                "source_resolution": None,
                "source_fps": None,
                "source_duration_seconds": None,
                "output_resolution": None,
                "output_fps": None,
                "output_duration_seconds": None,
                "output_codec": None,
                "render_elapsed_seconds": None,
                "wall_x_realtime": None,
                "r2_object_key": item.object_key,
                "r2_bucket": _required_env("R2_BUCKET"),
                "r2_etag": item.etag,
                "r2_uploaded_at": uploaded_at,
            }
        )

    return {
        "id": job_id,
        "uid": uid,
        "job_dir": "",
        "status": "completed",
        "created_at": created_at,
        "updated_at": now,
        "expires_at": None,
        "started_at": None,
        "finished_at": finished_at,
        "local_artifacts_deleted_at": now,
        "progress": 100,
        "message": "Backfilled from existing R2 objects",
        "gpx_name": "",
        "videos": videos,
        "settings": {},
        "backfilled_from_r2": True,
        "backfilled_at": now,
    }


def _merge_missing_videos(existing: dict[str, Any], backfill: dict[str, Any]) -> dict[str, Any] | None:
    existing_videos = existing.get("videos")
    if not isinstance(existing_videos, list):
        existing_videos = []

    known_keys = {
        str(video.get("r2_object_key") or "")
        for video in existing_videos
        if isinstance(video, dict)
    }
    missing = [
        deepcopy(video)
        for video in backfill["videos"]
        if str(video.get("r2_object_key") or "") not in known_keys
    ]
    if not missing:
        return None

    merged = deepcopy(existing)
    merged["videos"] = [*existing_videos, *missing]
    merged["updated_at"] = _utc_now()
    merged["backfilled_from_r2"] = True
    merged["backfilled_at"] = merged["updated_at"]
    merged.setdefault("uid", backfill["uid"])
    merged.setdefault("id", backfill["id"])
    return merged


def _print_sample(media: list[R2MediaObject], *, max_items: int) -> None:
    if not media:
        return
    print("Sample objects:")
    for item in media[:max_items]:
        print(f"  uid={item.uid} job={item.job_id} output={item.output_name} size={item.size_bytes}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Firestore job metadata from existing R2 rendered outputs.")
    parser.add_argument("--apply", action="store_true", help="Write Firestore documents. Default is dry-run only.")
    parser.add_argument("--uid", help="Only backfill one Firebase UID.")
    parser.add_argument("--prefix", default="users/", help="R2 key prefix to scan.")
    parser.add_argument("--limit", type=int, help="Maximum media objects to scan.")
    parser.add_argument("--merge-existing", action="store_true", help="Append missing R2 videos to existing job documents.")
    parser.add_argument("--sample", type=int, default=10, help="Number of discovered objects to print.")
    parser.add_argument(
        "--extensions",
        default=",".join(DEFAULT_EXTENSIONS),
        help="Comma-separated output extensions to include.",
    )
    args = parser.parse_args()

    if not _read_bool("FIRESTORE_ENABLED", False):
        raise RuntimeError("FIRESTORE_ENABLED must be true")
    if not _read_bool("R2_UPLOAD_ENABLED", False):
        raise RuntimeError("R2_UPLOAD_ENABLED must be true")

    bucket = _required_env("R2_BUCKET")
    collection_name = os.environ.get("FIRESTORE_COLLECTION_JOBS", "jobs").strip() or "jobs"
    extensions = tuple(part.strip().lower() for part in args.extensions.split(",") if part.strip())
    if not extensions:
        raise RuntimeError("--extensions cannot be empty")

    media = _list_r2_media_objects(
        bucket=bucket,
        prefix=args.prefix,
        uid=args.uid,
        extensions=extensions,
        limit=args.limit,
    )
    grouped: dict[tuple[str, str], list[R2MediaObject]] = defaultdict(list)
    for item in media:
        grouped[(item.uid, item.job_id)].append(item)

    print(f"R2 bucket: {bucket}")
    print(f"Firestore jobs collection: {collection_name}")
    print(f"Mode: {'apply' if args.apply else 'dry-run'}")
    print(f"Discovered media objects: {len(media)}")
    print(f"Discovered user/job groups: {len(grouped)}")
    _print_sample(media, max_items=max(args.sample, 0))

    if not grouped:
        return 0

    db = _firestore_client()
    jobs_collection = db.collection(collection_name)

    creates = 0
    merges = 0
    skips_existing = 0
    unchanged_existing = 0

    for (uid, job_id), objects in sorted(grouped.items()):
        backfill = _job_document(uid, job_id, objects)
        doc_ref = jobs_collection.document(job_id)
        snapshot = doc_ref.get()
        if snapshot.exists:
            existing = snapshot.to_dict() or {}
            if args.merge_existing:
                merged = _merge_missing_videos(existing, backfill)
                if merged is None:
                    unchanged_existing += 1
                    continue
                merges += 1
                if args.apply:
                    doc_ref.set(merged)
            else:
                skips_existing += 1
            continue

        creates += 1
        if args.apply:
            doc_ref.set(backfill)

    print("Plan summary:")
    print(f"  creates: {creates}")
    print(f"  merges: {merges}")
    print(f"  existing skipped: {skips_existing}")
    print(f"  existing unchanged: {unchanged_existing}")
    if not args.apply:
        print("Dry-run only. Re-run with --apply to write Firestore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
