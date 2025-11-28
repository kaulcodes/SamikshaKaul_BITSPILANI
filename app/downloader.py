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

    # Add headers to mimic a browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Download error for URL {url}: {e}", flush=True)
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}", flush=True)
            print(f"Response body: {e.response.text}", flush=True)
        raise e

    import urllib.parse
    import mimetypes
    
    # Parse URL to get the path without query parameters
    parsed_url = urllib.parse.urlparse(url)
    path_url = parsed_url.path.lower()

    content_type = resp.headers.get("Content-Type", "").lower()
    
    # 1. Try to guess extension from Content-Type
    guessed_ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
    
    # 2. Determine suffix
    if "pdf" in content_type or path_url.endswith(".pdf"):
        suffix = ".pdf"
    elif guessed_ext:
        suffix = guessed_ext
    elif "." in path_url:
        # 3. Fallback to URL extension
        suffix = os.path.splitext(path_url)[1]
    else:
        # 4. Final fallback
        suffix = ".png"

    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(resp.content)

    print(f"Saved remote document to temp file: {path} (detected type: {suffix})", flush=True)
    return path
