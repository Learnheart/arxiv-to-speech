"""
D2S Pipeline — URL download with streaming, redirect following, and URL normalization.
"""
import re
from ipaddress import ip_address
from urllib.parse import urlparse, parse_qs, urlencode

import httpx

from config import URL_DOWNLOAD_CONFIG
from logger import logger


class DownloadError(Exception):
    pass


def normalize_download_url(url: str) -> str:
    """Convert sharing URLs (Google Drive, Dropbox, OneDrive) to direct download URLs."""
    parsed = urlparse(url)

    # Google Drive: /file/d/{id}/view → direct download
    if "drive.google.com" in parsed.netloc:
        match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"

    # Dropbox: dl=0 → dl=1
    if "dropbox.com" in parsed.netloc:
        return url.replace("dl=0", "dl=1").replace(
            "www.dropbox.com", "dl.dropboxusercontent.com"
        )

    # OneDrive
    if "onedrive.live.com" in parsed.netloc or "1drv.ms" in parsed.netloc:
        return url.replace("redir", "download")

    return url


def _is_private_ip(hostname: str) -> bool:
    """Block private/loopback IPs to prevent SSRF."""
    try:
        ip = ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_reserved
    except ValueError:
        return False


async def download_file(url: str) -> tuple[bytes, str]:
    """
    Download file from URL.
    Returns (file_bytes, detected_filename).
    Raises DownloadError on failure.
    """
    parsed = urlparse(url)

    # HTTPS only
    if parsed.scheme != "https":
        raise DownloadError("Chi ho tro HTTPS URLs.")

    # SSRF check
    if _is_private_ip(parsed.hostname or ""):
        raise DownloadError("Khong cho phep truy cap dia chi IP noi bo.")

    download_url = normalize_download_url(url)
    cfg = URL_DOWNLOAD_CONFIG

    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=cfg["max_redirects"],
        timeout=httpx.Timeout(connect=cfg["connect_timeout"], read=cfg["download_timeout"]),
        headers={"User-Agent": cfg["user_agent"]},
    ) as client:
        # HEAD check first
        try:
            head_resp = await client.head(download_url)
            content_length = int(head_resp.headers.get("content-length", 0))
            if content_length > cfg["max_file_size"]:
                raise DownloadError(
                    f"File qua lon ({content_length / 1024 / 1024:.1f}MB). "
                    f"Gioi han {cfg['max_file_size'] / 1024 / 1024:.0f}MB."
                )
        except httpx.HTTPError as e:
            logger.warning("HEAD request failed for %s: %s. Proceeding with GET.", url, e)

        # Stream download
        try:
            resp = await client.get(download_url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise DownloadError(f"Khong the tai file: {e}")

        file_bytes = resp.content
        if len(file_bytes) > cfg["max_file_size"]:
            raise DownloadError("File qua lon sau khi tai.")

        # Detect filename
        content_disp = resp.headers.get("content-disposition", "")
        filename = "downloaded_file"
        if "filename=" in content_disp:
            match = re.search(r'filename="?([^";\n]+)"?', content_disp)
            if match:
                filename = match.group(1).strip()
        else:
            # Extract from URL path
            path = parsed.path.rstrip("/")
            if path:
                filename = path.split("/")[-1]

        logger.info("Downloaded %s (%d bytes) as %s", url, len(file_bytes), filename)
        return file_bytes, filename
