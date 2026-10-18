"""Private Supabase object API; credentials and object URLs stay server-side."""

import os
from urllib.parse import quote, urlsplit

import httpx

from .errors import StorageUnavailable


def bucket():
    return os.getenv("SUPABASE_STORAGE_BUCKET", "cci-private-documents")


def request(method, path, **kwargs):
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    parsed = urlsplit(url)
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".supabase.co")
        or parsed.path
        or parsed.username
        or parsed.password
        or parsed.query
        or not key
    ):
        raise StorageUnavailable("Private document storage is not configured.")
    try:
        response = httpx.request(
            method,
            url + "/storage/v1/" + path,
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key,
                **kwargs.pop("headers", {}),
            },
            timeout=30,
            follow_redirects=False,
            **kwargs,
        )
        response.raise_for_status()
        return response
    except httpx.HTTPError:
        raise StorageUnavailable(
            "Private document storage is temporarily unavailable."
        ) from None


def verify_private_bucket():
    info = request("GET", "bucket/" + quote(bucket(), safe="")).json()
    if info.get("public") is not False:
        raise StorageUnavailable("The document bucket must be private.")


def upload(path, content):
    request(
        "POST",
        "object/" + quote(bucket(), safe="") + "/" + quote(path, safe="/"),
        content=content,
        headers={"Content-Type": "application/pdf", "x-upsert": "false"},
    )


def download(path):
    return request(
        "GET",
        "object/authenticated/"
        + quote(bucket(), safe="")
        + "/"
        + quote(path, safe="/"),
    ).content


def delete(path):
    request("DELETE", "object/" + quote(bucket(), safe=""), json={"prefixes": [path]})
