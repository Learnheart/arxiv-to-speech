"""
Unit tests for utils/downloader.py
Covers: normalize_download_url(), _is_private_ip(), download_file()
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from utils.downloader import (
    normalize_download_url,
    _is_private_ip,
    download_file,
    DownloadError,
)


# ══════════════════════════════════════════════════════════
# TC-URL: normalize_download_url()
# ══════════════════════════════════════════════════════════

class TestNormalizeDownloadUrl:

    # ── TC-URL-001: Google Drive sharing URL ──
    def test_google_drive_file_view(self):
        url = "https://drive.google.com/file/d/1ABCdef123/view"
        result = normalize_download_url(url)
        assert "uc?export=download" in result
        assert "1ABCdef123" in result

    def test_google_drive_file_edit(self):
        url = "https://drive.google.com/file/d/abc_123-XYZ/edit"
        result = normalize_download_url(url)
        assert "uc?export=download" in result
        assert "abc_123-XYZ" in result

    # ── TC-URL-002: Dropbox URL ──
    def test_dropbox_dl_0_to_1(self):
        url = "https://www.dropbox.com/s/abc123/file.pdf?dl=0"
        result = normalize_download_url(url)
        assert "dl=1" in result
        assert "dl.dropboxusercontent.com" in result

    # ── TC-URL-003: OneDrive URL ──
    def test_onedrive_redir_to_download(self):
        url = "https://onedrive.live.com/redir?resid=abc123"
        result = normalize_download_url(url)
        assert "download" in result

    # ── TC-URL-004: Regular URL unchanged ──
    def test_regular_url_unchanged(self):
        url = "https://example.com/papers/doc.pdf"
        result = normalize_download_url(url)
        assert result == url

    # ── TC-URL-005: 1drv.ms short URL ──
    def test_1drv_ms_url(self):
        url = "https://1drv.ms/redir?something=abc"
        result = normalize_download_url(url)
        assert "download" in result


# ══════════════════════════════════════════════════════════
# TC-SSRF: _is_private_ip()
# ══════════════════════════════════════════════════════════

class TestIsPrivateIp:

    def test_localhost(self):
        assert _is_private_ip("127.0.0.1") is True

    def test_private_10_network(self):
        assert _is_private_ip("10.0.0.1") is True

    def test_private_172_network(self):
        assert _is_private_ip("172.16.0.1") is True

    def test_private_192_network(self):
        assert _is_private_ip("192.168.1.1") is True

    def test_public_ip(self):
        assert _is_private_ip("8.8.8.8") is False

    def test_hostname_not_ip(self):
        assert _is_private_ip("example.com") is False

    def test_ipv6_loopback(self):
        assert _is_private_ip("::1") is True

    def test_empty_string(self):
        assert _is_private_ip("") is False


# ══════════════════════════════════════════════════════════
# TC-DL: download_file()
# ══════════════════════════════════════════════════════════

class TestDownloadFile:

    # ── TC-DL-001: HTTP URL rejected ──
    @pytest.mark.asyncio
    async def test_http_rejected(self):
        with pytest.raises(DownloadError, match="HTTPS"):
            await download_file("http://example.com/file.pdf")

    # ── TC-DL-002: Private IP rejected (SSRF) ──
    @pytest.mark.asyncio
    async def test_private_ip_rejected(self):
        with pytest.raises(DownloadError):
            await download_file("https://192.168.1.1/file.pdf")

    @pytest.mark.asyncio
    async def test_localhost_rejected(self):
        with pytest.raises(DownloadError):
            await download_file("https://127.0.0.1/secret.pdf")

    # ── TC-DL-003: Successful download ──
    @pytest.mark.asyncio
    async def test_successful_download(self):
        mock_head_resp = MagicMock()
        mock_head_resp.headers = {"content-length": "100"}

        mock_get_resp = MagicMock()
        mock_get_resp.content = b"%PDF-1.4 test content"
        mock_get_resp.headers = {"content-disposition": 'attachment; filename="test.pdf"'}
        mock_get_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_head_resp)
        mock_client.get = AsyncMock(return_value=mock_get_resp)

        async def aenter(*args):
            return mock_client

        async def aexit(*args):
            return False

        with patch("utils.downloader.httpx.AsyncClient") as MockClient, \
             patch("utils.downloader.httpx.Timeout", return_value=MagicMock()):
            cm = MagicMock()
            cm.__aenter__ = aenter
            cm.__aexit__ = aexit
            MockClient.return_value = cm

            file_bytes, filename = await download_file("https://example.com/test.pdf")
            assert file_bytes == b"%PDF-1.4 test content"
            assert filename == "test.pdf"

    # ── TC-DL-004: File too large (HEAD check) ──
    @pytest.mark.asyncio
    async def test_file_too_large_head_check(self):
        mock_head_resp = MagicMock()
        mock_head_resp.headers = {"content-length": str(300 * 1024 * 1024)}

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_head_resp)

        async def aenter(*args):
            return mock_client

        async def aexit(*args):
            return False

        with patch("utils.downloader.httpx.AsyncClient") as MockClient, \
             patch("utils.downloader.httpx.Timeout", return_value=MagicMock()):
            cm = MagicMock()
            cm.__aenter__ = aenter
            cm.__aexit__ = aexit
            MockClient.return_value = cm

            with pytest.raises(DownloadError, match="qua lon"):
                await download_file("https://example.com/huge.pdf")

    # ── TC-DL-005: Filename from URL path ──
    @pytest.mark.asyncio
    async def test_filename_from_url_path(self):
        mock_head_resp = MagicMock()
        mock_head_resp.headers = {}

        mock_get_resp = MagicMock()
        mock_get_resp.content = b"data"
        mock_get_resp.headers = {}
        mock_get_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_head_resp)
        mock_client.get = AsyncMock(return_value=mock_get_resp)

        async def aenter(*args):
            return mock_client

        async def aexit(*args):
            return False

        with patch("utils.downloader.httpx.AsyncClient") as MockClient, \
             patch("utils.downloader.httpx.Timeout", return_value=MagicMock()):
            cm = MagicMock()
            cm.__aenter__ = aenter
            cm.__aexit__ = aexit
            MockClient.return_value = cm

            _, filename = await download_file("https://example.com/path/to/paper.pdf")
            assert filename == "paper.pdf"

    # ── TC-DL-006: Empty scheme rejected ──
    @pytest.mark.asyncio
    async def test_no_scheme_rejected(self):
        with pytest.raises(DownloadError):
            await download_file("ftp://example.com/file.pdf")
