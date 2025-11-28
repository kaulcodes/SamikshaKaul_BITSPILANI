import requests
import tempfile
import os


def download_document(url: str) -> str:
    """
    If `url` starts with http/https, download the file to a temp path and return it.
    If not, treat `url` as a local file path and just return it unchanged.
    Download a document from a URL or return the local path if it exists.
    Raise an exception if the request fails.
    """
    # Check if it's a local file
    if os.path.exists(url):
        return url

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "").lower()
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        suffix = ".pdf"
    else:
        suffix = ".png"

    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(resp.content)

    print(f"Saved remote document to temp file: {path}", flush=True)
    return path
