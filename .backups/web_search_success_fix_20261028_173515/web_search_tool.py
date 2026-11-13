"""Ferramenta de pesquisa web em tempo real (somente leitura)."""

import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
import json

from src.tools.base_tool import BaseTool

_DDG_HTML = "https://html.duckduckgo.com/html/"
_DDG_LITE = "https://lite.duckduckgo.com/lite/"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_DEFAULT_TIMEOUT = 10
_DEFAULT_MAX_RESULTS = 5
_MAX_RESULTS_CAP = 10
_SNIPPET_MAX_LEN = 400
_AWESOMEAPI_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
_CURRENCY_KW = ("dolar", "dólar", "cotacao", "cotação", "cambio", "câmbio", "usd")


def _unwrap_ddg_url(href: str) -> str:
    if not href:
        return ""
    href = unescape(href).strip()
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    if qs.get("uddg"):
        return unquote(qs["uddg"][0])
    if href.startswith("//"):
        return "https:" + href
    return href


def _clean_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


class _DDGHTMLParser(HTMLParser):
    """Extrai titulo, URL e snippet dos resultados HTML do DuckDuckGo."""

    def __init__(self) -> None:
        super().__init__()
        self.results: List[Dict[str, str]] = []
        self._current: Dict[str, str] = {}
        self._capture_title = False
        self._capture_snippet = False
        self._buf: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_d = dict(attrs)
        classes = attrs_d.get("class") or ""
        href = attrs_d.get("href") or ""

        if tag == "a" and ("result__a" in classes or "result-link" in classes):
            self._current = {
                "title": "",
                "url": _unwrap_ddg_url(href),
                "snippet": "",
            }
            self._capture_title = True
            self._capture_snippet = False
            self._buf = []
        elif "result__snippet" in classes or "result-snippet" in classes:
            self._capture_snippet = True
            self._capture_title = False
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture_title and tag == "a":
            self._current["title"] = _clean_text("".join(self._buf))
            self._capture_title = False
            self._buf = []
            url = self._current.get("url") or ""
            title = self._current.get("title") or ""
            if url and title and not any(r.get("url") == url for r in self.results):
                self.results.append(self._current)
        elif self._capture_snippet and tag in ("a", "td", "div"):
            snippet = _clean_text("".join(self._buf))
            self._capture_snippet = False
            self._buf = []
            if self.results and not self.results[-1].get("snippet"):
                self.results[-1]["snippet"] = snippet

    def handle_data(self, data: str) -> None:
        if self._capture_title or self._capture_snippet:
            self._buf.append(data)


class WebSearchTool(BaseTool):
    """Pesquisa web somente leitura, com timeout e extra??o de fontes."""

    __plugin_name__ = "web_search_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Pesquisa web em tempo real (somente leitura)"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "web", "search", "network"]
    __plugin_capabilities__ = ["web_search", "search", "internet"]
    __plugin_permissions__ = ["read", "network"]
    __plugin_requires__ = ["logger", "config"]

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.__plugin_description__,
            "capabilities": self.get_capabilities(),
            "read_only": True,
            "required_params": self.get_required_params(),
            "optional_params": self.get_optional_params(),
        }

    def get_required_params(self) -> List[str]:
        return ["query"]

    def get_optional_params(self) -> Dict[str, Any]:
        return {"max_results": _DEFAULT_MAX_RESULTS}

    def validate(self, params: Dict[str, Any]) -> bool:
        if not isinstance(params, dict):
            return False
        query = params.get("query")
        if not isinstance(query, str) or not query.strip():
            return False
        if "max_results" in params:
            try:
                value = int(params["max_results"])
            except (TypeError, ValueError):
                return False
            if value < 1:
                return False
        return True

    async def execute(
        self, params: Dict[str, Any], context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        query = str(params.get("query", "")).strip()
        try:
            max_results = int(params.get("max_results", _DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            max_results = _DEFAULT_MAX_RESULTS
        max_results = max(1, min(max_results, _MAX_RESULTS_CAP))

        timeout_sec = _DEFAULT_TIMEOUT
        try:
            timeout_sec = int(self.config.get("tools.web_search.timeout", timeout_sec))
        except Exception:
            timeout_sec = _DEFAULT_TIMEOUT

        fetched_at = datetime.now(timezone.utc).isoformat()
        last_error: Optional[str] = None
        results: List[Dict[str, str]] = []
        provider: Optional[str] = None

        currency_quote = await self._fetch_currency_quote(query, timeout_sec)

        try:
            results, provider = await self._search_ddg_html(query, max_results, timeout_sec)
        except Exception as exc:
            last_error = str(exc)
            self.logger.warning("web_search provedor HTML falhou: %s", exc)

        if not results:
            try:
                results, provider = await self._search_ddg_lite(query, max_results, timeout_sec)
            except Exception as exc:
                last_error = str(exc)
                self.logger.warning("web_search provedor lite falhou: %s", exc)

        if currency_quote:
            if not results:
                results = [currency_quote]
                provider = "awesomeapi"
            else:
                results.insert(0, currency_quote)

        payload: Dict[str, Any] = {
            "query": query,
            "results": results,
            "count": len(results),
            "provider": provider,
            "fetched_at": fetched_at,
            "sources": [item["url"] for item in results if item.get("url")],
        }
        if not results:
            payload["error"] = last_error or "Nenhum resultado encontrado"
            self.logger.warning("web_search sem resultados")
        else:
            self.logger.info(
                "web_search concluida count=%s provider=%s",
                len(results),
                provider,
            )
        return payload

    async def _fetch_currency_quote(self, query: str, timeout_sec: int):
        if not any(k in query.lower() for k in _CURRENCY_KW):
            return None
        try:
            t = aiohttp.ClientTimeout(total=min(timeout_sec, 8))
            async with aiohttp.ClientSession(timeout=t) as s:
                async with s.get(_AWESOMEAPI_URL) as r:
                    if r.status != 200:
                        return None
                    d = (await r.json()).get("USDBRL") or {}
                    bid, ask, dt = d.get("bid",""), d.get("ask",""), d.get("create_date","")
                    if not bid or not ask:
                        return None
                    self.logger.info("Cotacao USD/BRL: compra=%s venda=%s", bid, ask)
                    return {"title": "Cotacao USD/BRL em tempo real",
                            "url": "https://economia.awesomeapi.com.br",
                            "snippet": f"Cotacao do dolar comercial em {dt}: compra R$ {bid}, venda R$ {ask}. Fonte: AwesomeAPI."}
        except Exception as e:
            self.logger.warning("Cotacao AwesomeAPI falhou: %s", e)
            return None

    async def _search_ddg_html(
        self, query: str, max_results: int, timeout_sec: int
    ) -> Tuple[List[Dict[str, str]], str]:
        html = await self._post_form(
            _DDG_HTML,
            {"q": query, "kl": "br-pt"},
            timeout_sec,
        )
        parser = _DDGHTMLParser()
        parser.feed(html)
        results = self._normalize_results(parser.results, max_results)
        if not results:
            results = self._regex_extract(html, max_results)
        if not results:
            raise RuntimeError("HTML DuckDuckGo nao retornou resultados interpretaveis")
        return results, "duckduckgo_html"

    async def _search_ddg_lite(
        self, query: str, max_results: int, timeout_sec: int
    ) -> Tuple[List[Dict[str, str]], str]:
        html = await self._post_form(
            _DDG_LITE,
            {"q": query, "kl": "br-pt"},
            timeout_sec,
        )
        parser = _DDGHTMLParser()
        parser.feed(html)
        results = self._normalize_results(parser.results, max_results)
        if not results:
            results = self._regex_extract(html, max_results)
        if not results:
            raise RuntimeError("Lite DuckDuckGo nao retornou resultados interpretaveis")
        return results, "duckduckgo_lite"

    def _normalize_results(
        self, raw: List[Dict[str, str]], max_results: int
    ) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        seen = set()
        for item in raw:
            url = (item.get("url") or "").strip()
            title = _clean_text(item.get("title") or "")
            snippet = _clean_text(item.get("snippet") or "")
            if snippet and len(snippet) > _SNIPPET_MAX_LEN:
                snippet = snippet[:_SNIPPET_MAX_LEN].rstrip() + "..."
            if not url or not title:
                continue
            if not url.startswith("http://") and not url.startswith("https://"):
                continue
            host = (urlparse(url).netloc or "").lower()
            if "duckduckgo.com" in host:
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append({"title": title, "url": url, "snippet": snippet})
            if len(out) >= max_results:
                break
        return out

    def _regex_extract(self, html: str, max_results: int) -> List[Dict[str, str]]:
        raw: List[Dict[str, str]] = []
        patterns = (
            r'<a[^>]*class="[^"]*(?:result__a|result-link)[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*(?:result__a|result-link)[^"]*"[^>]*>(.*?)</a>',
        )
        for pattern in patterns:
            for match in re.finditer(pattern, html, flags=re.IGNORECASE | re.DOTALL):
                raw.append({
                    "title": re.sub(r"<[^>]+>", "", match.group(2)),
                    "url": _unwrap_ddg_url(match.group(1)),
                    "snippet": "",
                })
        return self._normalize_results(raw, max_results)

    async def _post_form(
        self, url: str, data: Dict[str, str], timeout_sec: int
    ) -> str:
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://duckduckgo.com/",
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(url, data=data, allow_redirects=True) as resp:
                if resp.status != 200:
                    raise RuntimeError("HTTP %s em %s" % (resp.status, url))
                text = await resp.text(errors="replace")
                if not text.strip():
                    raise RuntimeError("Resposta vazia de %s" % url)
                return text
