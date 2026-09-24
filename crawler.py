import asyncio
import aiohttp
import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, Set
from urllib.parse import urljoin, urlparse, urldefrag
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SKIP_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".mp4", ".mp3", ".wav", ".zip", ".tar", ".gz", ".exe",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
}

SKIP_PATTERNS = re.compile(
    r"(login|logout|signin|signup|register|auth|account|admin|wp-admin|"
    r"wp-login|\.php\?.*action=|/feed/|/rss|/sitemap\.xml|/robots\.txt|"
    r"#|javascript:|mailto:|tel:)",
    re.IGNORECASE,
)


@dataclass
class CrawledPage:
    url: str
    title: str
    content: str
    links: list[str]
    content_hash: str
    status_code: int = 200


@dataclass
class CrawlConfig:
    max_pages: int = 100
    delay: float = 0.3
    timeout: int = 20
    max_concurrent: int = 5
    allowed_path_prefix: Optional[str] = None
    use_playwright: bool = False
    headers: dict = field(default_factory=lambda: {
        "User-Agent": "RAGBot/1.0 (Educational Crawler; contact@example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })


class WebCrawler:
    def __init__(self, config: CrawlConfig):
        self.config = config
        self._visited: Set[str] = set()
        self._queued: Set[str] = set()
        self._semaphore = asyncio.Semaphore(config.max_concurrent)

    def _normalize_url(self, url: str) -> Optional[str]:
        """Clean and normalize a URL."""
        url, _ = urldefrag(url)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        path = parsed.path.rstrip("/") or "/"
        return parsed._replace(path=path, query=parsed.query).geturl()

    def _should_skip(self, url: str, base_domain: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc != base_domain:
            return True
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in SKIP_EXTENSIONS):
            return True
        if SKIP_PATTERNS.search(url):
            return True
        if self.config.allowed_path_prefix:
            if not parsed.path.startswith(self.config.allowed_path_prefix):
                return True
        return False

    def _extract_content(self, html: str, url: str) -> tuple[str, str, list[str]]:
        """Extract title, clean text, and links from HTML."""
        soup = BeautifulSoup(html, "lxml")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Title
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
        if not title and soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # Main content — prefer semantic containers
        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find(id=re.compile(r"content|main|article", re.I)) or
            soup.find(class_=re.compile(r"content|main|article|post", re.I)) or
            soup.find("body") or
            soup
        )

        # Extract structured text
        lines = []
        for elem in main.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th",
             "dt", "dd", "blockquote", "pre", "code"]
        ):
            text = elem.get_text(" ", strip=True)
            if len(text) > 20:
                tag = elem.name
                if tag in ("h1", "h2", "h3"):
                    lines.append(f"\n## {text}\n")
                elif tag in ("h4", "h5", "h6"):
                    lines.append(f"\n### {text}\n")
                elif tag in ("pre", "code"):
                    lines.append(f"```\n{text}\n```")
                else:
                    lines.append(text)

        content = "\n".join(lines)
        content = re.sub(r"\n{3,}", "\n\n", content).strip()

        # Collect links
        base_parsed = urlparse(url)
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href:
                continue
            absolute = urljoin(url, href)
            normalized = self._normalize_url(absolute)
            if normalized:
                links.append(normalized)

        return title, content, links

    async def _fetch_page(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[CrawledPage]:
        async with self._semaphore:
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    allow_redirects=True,
                    ssl=False,
                ) as resp:
                    if resp.status != 200:
                        return None
                    content_type = resp.headers.get("Content-Type", "")
                    if "text/html" not in content_type:
                        return None
                    html = await resp.text(errors="replace")

                title, content, links = self._extract_content(html, str(resp.url))
                if len(content) < 100:
                    return None

                content_hash = hashlib.md5(content.encode()).hexdigest()
                return CrawledPage(
                    url=str(resp.url),
                    title=title,
                    content=content,
                    links=links,
                    content_hash=content_hash,
                    status_code=resp.status,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout: {url}")
            except Exception as e:
                logger.warning(f"Error fetching {url}: {e}")
            return None

    async def crawl(self, start_url: str) -> AsyncGenerator[CrawledPage, None]:
        """Async generator yielding crawled pages."""
        start_url = self._normalize_url(start_url)
        if not start_url:
            return

        base_domain = urlparse(start_url).netloc
        queue = asyncio.Queue()
        await queue.put(start_url)
        self._queued.add(start_url)

        connector = aiohttp.TCPConnector(limit=self.config.max_concurrent, ssl=False)
        async with aiohttp.ClientSession(
            headers=self.config.headers, connector=connector
        ) as session:
            while not queue.empty() and len(self._visited) < self.config.max_pages:
                # Process in batches
                batch = []
                while not queue.empty() and len(batch) < self.config.max_concurrent:
                    url = await queue.get()
                    if url not in self._visited:
                        batch.append(url)
                        self._visited.add(url)

                if not batch:
                    break

                tasks = [self._fetch_page(session, url) for url in batch]
                results = await asyncio.gather(*tasks)

                for page in results:
                    if page is None:
                        continue

                    yield page

                    # Enqueue new links
                    for link in page.links:
                        norm = self._normalize_url(link)
                        if (
                            norm and
                            norm not in self._visited and
                            norm not in self._queued and
                            not self._should_skip(norm, base_domain) and
                            len(self._queued) < self.config.max_pages * 2
                        ):
                            self._queued.add(norm)
                            await queue.put(norm)

                if self.config.delay > 0:
                    await asyncio.sleep(self.config.delay)

    @property
    def pages_visited(self) -> int:
        return len(self._visited)
