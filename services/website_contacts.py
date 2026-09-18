import asyncio
import ipaddress
import re
import socket
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from services.config import settings


USER_AGENT = "PoiFinderContactBot/1.0"
CONTACT_LINK_WORDS = ("联系", "商务", "招商", "采购", "contact")
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
LABELED_PHONE_PATTERN = re.compile(
    r"(?:联系电话|客服电话|咨询电话|服务热线|商务电话|电话|热线)\s*[：:]?\s*"
    r"((?:\+?86[-\s]?)?(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}(?:[-转]\d{1,6})?))"
)


class ContactPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.mailtos: list[str] = []
        self.telephones: list[str] = []
        self.text_parts: list[str] = []
        self._href = ""
        self._anchor_text: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
            return
        if tag != "a":
            return
        self._href = dict(attrs).get("href") or ""
        self._anchor_text = []
        if self._href.lower().startswith("mailto:"):
            self.mailtos.append(self._href[7:].split("?", 1)[0])
        elif self._href.lower().startswith("tel:"):
            self.telephones.append(self._href[4:].split("?", 1)[0])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if tag == "a" and self._href:
            self.links.append((self._href, "".join(self._anchor_text).strip()))
            self._href = ""
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        value = data.strip()
        if value:
            self.text_parts.append(value)
            if self._href:
                self._anchor_text.append(value)


def normalize_website(value: Any) -> str | None:
    website = str(value or "").strip()
    if not website:
        return None
    scheme_match = re.match(r"^([a-z][a-z0-9+.-]*):", website, re.I)
    if scheme_match and scheme_match.group(1).lower() not in {"http", "https"}:
        return None
    if not re.match(r"^https?://", website, re.I):
        website = f"https://{website}"
    parsed = urlparse(website)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    return website


async def _is_public_host(hostname: str) -> bool:
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo, hostname, None, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        return False
    addresses = {record[4][0] for record in records}
    return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)


async def _fetch_text(client: httpx.AsyncClient, url: str) -> tuple[str, str] | None:
    current = url
    for _ in range(4):
        parsed = urlparse(current)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if not await _is_public_host(parsed.hostname):
            return None
        async with client.stream(
            "GET", current, headers={"User-Agent": USER_AGENT}, follow_redirects=False
        ) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    return None
                current = urljoin(current, location)
                continue
            if response.status_code != 200:
                return None
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "text/plain" not in content_type:
                return None
            declared_size = response.headers.get("content-length")
            if declared_size and declared_size.isdigit() and int(declared_size) > settings.website_max_bytes:
                return None
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > settings.website_max_bytes:
                    return None
            encoding = response.encoding or "utf-8"
            return current, bytes(body).decode(encoding, errors="replace")
    return None


async def _load_robots(
    client: httpx.AsyncClient, website: str
) -> RobotFileParser | None:
    parsed = urlparse(website)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    result = await _fetch_text(client, robots_url)
    if result is None:
        return None
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(result[1].splitlines())
    return parser


def _unique(values: list[str], limit: int = 5) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = re.sub(r"\s+", "", unescape(value)).strip(";,，；。")
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _valid_phones(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in _unique(values, limit=20):
        digits = re.sub(r"\D", "", value)
        if 7 <= len(digits) <= 17 and len(set(digits)) > 1:
            result.append(value)
        if len(result) >= 5:
            break
    return result


def _valid_emails(values: list[str]) -> list[str]:
    return [value.lower() for value in _unique(values) if EMAIL_PATTERN.fullmatch(value)]


def extract_contacts(html: str) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    parser = ContactPageParser()
    parser.feed(html)
    visible_text = " ".join(parser.text_parts)
    emails = parser.mailtos + EMAIL_PATTERN.findall(visible_text)
    phones = parser.telephones + LABELED_PHONE_PATTERN.findall(visible_text)
    return _valid_phones(phones), _valid_emails(emails), parser.links


def _contact_links(base_url: str, links: list[tuple[str, str]]) -> list[str]:
    base = urlparse(base_url)
    result: list[str] = []
    for href, text in links:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.hostname != base.hostname:
            continue
        label = f"{text} {parsed.path}".lower()
        if any(word in label for word in CONTACT_LINK_WORDS):
            clean_url = absolute.split("#", 1)[0]
            if clean_url not in result:
                result.append(clean_url)
        if len(result) >= max(settings.website_max_pages - 1, 0):
            break
    return result


async def enrich_from_official_website(
    client: httpx.AsyncClient, item: dict[str, Any]
) -> int:
    website = normalize_website(item.get("website"))
    if not website or (item.get("phone") and item.get("email")):
        return 0
    robots = await _load_robots(client, website)
    if robots is not None and not robots.can_fetch(USER_AGENT, website):
        return 0
    await asyncio.sleep(settings.website_request_interval)

    pending = [website]
    visited: set[str] = set()
    phones: list[str] = []
    emails: list[str] = []
    source_url = website
    while pending and len(visited) < settings.website_max_pages:
        url = pending.pop(0)
        if url in visited or (robots is not None and not robots.can_fetch(USER_AGENT, url)):
            continue
        visited.add(url)
        fetched = await _fetch_text(client, url)
        if fetched is None:
            continue
        final_url, html = fetched
        page_phones, page_emails, links = extract_contacts(html)
        if page_phones or page_emails:
            source_url = final_url
        phones.extend(page_phones)
        emails.extend(page_emails)
        pending.extend(link for link in _contact_links(final_url, links) if link not in visited)
        if pending and len(visited) < settings.website_max_pages:
            await asyncio.sleep(settings.website_request_interval)

    sources = item.setdefault("contact_sources", {})
    updated = 0
    if not item.get("phone") and phones:
        item["phone"] = "；".join(_unique(phones))
        sources["phone"] = "official_website"
        updated += 1
    if not item.get("email") and emails:
        item["email"] = "；".join(_unique(emails))
        sources["email"] = "official_website"
        updated += 1
    raw = item.get("raw")
    if updated and isinstance(raw, dict):
        raw["_contact_source_url"] = source_url
    return updated


async def enrich_items_from_websites(
    client: httpx.AsyncClient, items: list[dict[str, Any]]
) -> int:
    if not settings.website_enrichment_enabled:
        return 0
    updated = 0
    for item in items:
        try:
            updated += await enrich_from_official_website(client, item)
        except (httpx.HTTPError, UnicodeError, ValueError):
            continue
    return updated
