"""Source URL policy. Collection is allowlisted unless explicitly opted in."""
import re
import ipaddress
from urllib.parse import urlparse

from config import get as config_get


def validate_source_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False, "URL 格式无效"

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False, "仅支持完整的 http/https URL"
    if parsed.username or parsed.password:
        return False, "来源 URL 不能包含认证信息"

    host = parsed.hostname.lower().rstrip(".")
    if host == "arxiv.org" or host.endswith(".arxiv.org"):
        if re.fullmatch(r"/list/[\w.-]+(?:/(?:recent|new|pastweek))?/?", parsed.path):
            return True, ""
        return False, "当前支持 arXiv 分类列表 URL，例如 /list/cs.AI/recent"

    if config_get("crawler", "enable_generic_fetch"):
        if host == "localhost" or host.endswith(".localhost"):
            return False, "通用来源不能访问本机地址"
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return False, "通用来源不能访问私有或保留网络地址"
        except ValueError:
            pass
        return True, ""

    return False, "当前仅默认支持 arXiv；通用网页抓取因可靠性和访问风险已关闭"
