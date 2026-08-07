"""Controlled collector for one user-specified public HTML page."""
import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Awaitable, Callable
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx


COLLECTOR_NAME = "single_public_url"
USER_AGENT = "ResearchMate/0.1 (+local single-page import)"
MAX_REDIRECTS = 3
MAX_HTML_BYTES = 1_000_000
MAX_ROBOTS_BYTES = 256_000
MAX_EXTRACTED_CHARS = 200_000
REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class CollectedPage:
    title: str
    content_text: str
    source_url: str
    source_facts: dict


class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
        "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5",
        "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
        "section", "table", "td", "th", "tr", "ul",
    }
    SKIP_TAGS = {"script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if not self._skip_depth and tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if not self._skip_depth and tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.text_parts.append(data)


def extract_html(html: str) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()[:300]
    lines = []
    for raw_line in "".join(parser.text_parts).splitlines():
        line = re.sub(r"[\t\f\v ]+", " ", raw_line).strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return title, "\n".join(lines)[:MAX_EXTRACTED_CHARS]


def validate_url_shape(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        port = parsed.port
    except (ValueError, TypeError) as exc:
        raise ValueError("URL 格式无效") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("仅支持完整的 http/https URL")
    if parsed.username or parsed.password:
        raise ValueError("URL 不能包含认证信息")
    if port not in {None, 80, 443}:
        raise ValueError("单 URL 导入仅允许标准 HTTP/HTTPS 端口")
    if parsed.hostname.lower().rstrip(".") in {"localhost"} or parsed.hostname.lower().endswith(".localhost"):
        raise ValueError("不能访问本机、私有或保留网络地址")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, ""))


async def _resolve_host(host: str, port: int) -> list[str]:
    try:
        ascii_host = host.encode("idna").decode("ascii")
        records = await asyncio.to_thread(
            socket.getaddrinfo, ascii_host, port, 0, socket.SOCK_STREAM
        )
    except (OSError, UnicodeError) as exc:
        raise ValueError("无法解析 URL 主机") from exc
    return list(dict.fromkeys(record[4][0] for record in records))


async def validate_public_url(
    url: str,
    *,
    resolver: Callable[[str, int], Awaitable[list[str]]] = _resolve_host,
) -> str:
    normalized = validate_url_shape(url)
    parsed = urlparse(normalized)
    addresses = await resolver(
        parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80)
    )
    if not addresses:
        raise ValueError("URL 主机没有可用地址")
    try:
        if any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError("不能访问本机、私有或保留网络地址")
    except ValueError as exc:
        if "不能访问" in str(exc):
            raise
        raise ValueError("URL 主机返回了无效地址") from exc
    return normalized


class SinglePublicURLCollector:
    name = COLLECTOR_NAME

    def __init__(self, *, resolver=_resolve_host, transport=None):
        self.resolver = resolver
        self.transport = transport

    async def collect(self, url: str) -> CollectedPage:
        current = await validate_public_url(url, resolver=self.resolver)
        checked_origins: set[str] = set()
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            for redirect_count in range(MAX_REDIRECTS + 1):
                parsed = urlparse(current)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                if origin not in checked_origins:
                    await self._check_robots(client, current)
                    checked_origins.add(origin)
                status, headers, body, peer = await self._read_response(
                    client, current, MAX_HTML_BYTES
                )
                self._validate_peer(peer)
                if status in {301, 302, 303, 307, 308}:
                    location = headers.get("location")
                    if not location or redirect_count == MAX_REDIRECTS:
                        raise RuntimeError("页面重定向无效或超过 3 次限制")
                    current = await validate_public_url(
                        urljoin(current, location), resolver=self.resolver
                    )
                    continue
                if status in {401, 403}:
                    raise RuntimeError("页面需要认证或拒绝访问")
                if status < 200 or status >= 300:
                    raise RuntimeError(f"页面返回 HTTP {status}")
                content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise RuntimeError("仅支持公开 HTML 页面，不下载附件或其他内容")
                encoding = self._charset(headers.get("content-type", ""))
                title, text = extract_html(body.decode(encoding, errors="replace"))
                if not text:
                    raise RuntimeError("页面未提取到可用正文")
                return CollectedPage(
                    title=title or urlparse(current).hostname or "网页资料",
                    content_text=text,
                    source_url=current,
                    source_facts={
                        "collector": self.name,
                        "http_status": status,
                        "content_type": content_type,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
        raise RuntimeError("页面导入失败")

    async def _check_robots(self, client: httpx.AsyncClient, page_url: str) -> None:
        parsed = urlparse(page_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots_url = await validate_public_url(robots_url, resolver=self.resolver)
        status, _, body, peer = await self._read_response(client, robots_url, MAX_ROBOTS_BYTES)
        self._validate_peer(peer)
        if status == 404:
            return
        if status in {401, 403}:
            raise RuntimeError("来源的 robots 策略不允许读取")
        if status < 200 or status >= 300:
            raise RuntimeError(f"无法确认来源 robots 策略（HTTP {status}）")
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(body.decode("utf-8", errors="replace").splitlines())
        if not parser.can_fetch(USER_AGENT, page_url):
            raise RuntimeError("来源的 robots 策略不允许读取该页面")

    async def _read_response(
        self, client: httpx.AsyncClient, url: str, limit: int
    ) -> tuple[int, httpx.Headers, bytes, str | None]:
        chunks = bytearray()
        async with client.stream("GET", url) as response:
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > limit:
                    raise RuntimeError("响应内容超过允许大小")
            stream = response.extensions.get("network_stream")
            server_addr = stream.get_extra_info("server_addr") if stream else None
            peer = server_addr[0] if isinstance(server_addr, tuple) and server_addr else None
            return response.status_code, response.headers, bytes(chunks), peer

    def _validate_peer(self, peer: str | None) -> None:
        if self.transport is not None and peer is None:
            return
        try:
            if peer is None or not ipaddress.ip_address(peer).is_global:
                raise RuntimeError("连接目标不是公开网络地址")
        except ValueError as exc:
            raise RuntimeError("无法验证连接目标地址") from exc

    @staticmethod
    def _charset(content_type: str) -> str:
        match = re.search(r"charset=([^;\s]+)", content_type, re.IGNORECASE)
        return match.group(1).strip('"\'') if match else "utf-8"
