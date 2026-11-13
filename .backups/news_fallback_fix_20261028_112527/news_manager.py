"""Gerenciador de Notícias da EVA."""

import asyncio
import json
import re  # <-- ADICIONADO
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import aiohttp

from src.kernel.events import EventBus
from src.core.event_types import EventType

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    feedparser = None


class NewsManager:
    """
    Gerenciador de Notícias da EVA.
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._running = False
        self._llm_manager = None
        
        self._categories = {
            "mundo": ["world", "global", "international", "onu", "guerra"],
            "brasil": ["brasil", "política", "congresso", "governo"],
            "campinas": ["campinas", "região", "metropolitana", "sumaré"],
            "tecnologia": ["tech", "technology", "ia", "programação", "software"],
            "economia": ["economy", "finance", "negócios", "mercado", "dólar"],
            "esportes": ["sports", "futebol", "olímpico", "campeonato"],
            "ciencia": ["science", "research", "descoberta", "nasa", "espacial"],
            "cultura": ["culture", "arts", "entretenimento", "cinema", "música"],
            "trabalhista": ["trabalhista", "trabalho", "lei", "direitos", "clt"]
        }
        
        # Fontes RSS em português
        self._rss_feeds = {
            "mundo": "https://www.bbc.com/portuguese/index.xml",
            "brasil": "https://g1.globo.com/rss/g1/",
            "tecnologia": "https://canaltech.com.br/feed/",
            "ciencia": "https://revistagalileu.globo.com/rss/",
            "economia": "https://www.infomoney.com.br/feed/",
            "esportes": "https://globoesporte.globo.com/rss/",
            "cultura": "https://www1.folha.uol.com.br/rss/ilustrada.xml",
            "campinas": "https://correio.rac.com.br/feed/"
        }
        
        self._user_preferences: Dict[str, List[str]] = {}
        self._last_briefing: Dict[str, str] = {}
        
        self.logger.info("📰 [NewsManager] Inicializado")
    
    async def initialize(self) -> None:
        self.logger.info("📰 [NewsManager] Inicializando...")
        self._running = True
        await self._load_preferences()
        
        if not FEEDPARSER_AVAILABLE:
            self.logger.warning("📰 [NewsManager] feedparser não disponível. Instale: pip install feedparser")
        
        self.logger.info("📰 [NewsManager] Inicializado")
    
    async def get_news(self, user_id: str, categories: List[str] = None, limit: int = 3) -> Dict[str, Any]:
        self.logger.info(f"📰 [NewsManager] Buscando notícias para {user_id}")
        
        if not categories:
            categories = self._user_preferences.get(user_id, ["mundo", "brasil", "tecnologia"])
        
        result = {}
        
        for category in categories:
            if category in self._categories:
                news = await self._fetch_category(category, limit)
                if news:
                    result[category] = news
        
        return result
    
    async def _fetch_category(self, category: str, limit: int = 3) -> List[Dict[str, Any]]:
        news = await self._fetch_from_api(category, limit)
        
        if not news and FEEDPARSER_AVAILABLE:
            news = await self._fetch_from_rss(category, limit)
        
        if not news:
            news = self._get_fallback_news(category, limit)
        
        return news
    
    async def _fetch_from_api(self, category: str, limit: int = 3) -> List[Dict[str, Any]]:
        try:
            api_key = self.config.get("news.api_key", "")
            if not api_key:
                return []
            
            keywords = self._categories.get(category, [category])
            query = " OR ".join(keywords[:3])
            
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "language": "pt",
                "pageSize": limit,
                "apiKey": api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get("articles", [])
                        
                        return [{
                            "title": self._clean_text(a.get("title", "Sem título")),
                            "description": self._clean_text(a.get("description", "")),
                            "content": self._clean_text(a.get("content", "")),
                            "source": a.get("source", {}).get("name", "Desconhecido"),
                            "url": a.get("url", ""),
                            "published": a.get("publishedAt", ""),
                            "category": category
                        } for a in articles if a.get("title")]
        
        except Exception as e:
            self.logger.error(f"Erro na API: {e}")
        
        return []
    
    async def _fetch_from_rss(self, category: str, limit: int = 3) -> List[Dict[str, Any]]:
        if not FEEDPARSER_AVAILABLE:
            return []
        
        feed_url = self._rss_feeds.get(category)
        if not feed_url:
            return []
        
        try:
            feed = feedparser.parse(feed_url)
            articles = feed.entries[:limit]
            
            return [{
                "title": self._clean_text(a.get("title", "Sem título")),
                "description": self._clean_text(a.get("description", "")),
                "content": self._clean_text(a.get("summary", "")),
                "source": a.get("source", {}).get("title", "RSS"),
                "url": a.get("link", ""),
                "published": a.get("published", ""),
                "category": category
            } for a in articles if a.get("title")]
            
        except Exception as e:
            self.logger.error(f"Erro no RSS: {e}")
            return []
    
    def _clean_text(self, text: str) -> str:
        """Limpa o texto removendo caracteres especiais e quebras."""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove múltiplos espaços e quebras
        text = re.sub(r'\s+', ' ', text)
        
        # Remove caracteres especiais que atrapalham a fala
        text = re.sub(r'[=]{3,}', '', text)  # Remove =====
        text = re.sub(r'[_-]{3,}', '', text)  # Remove ___ ou ---
        text = re.sub(r'[""``\']', '', text)  # Remove aspas
        
        # Remove URLs
        text = re.sub(r'http[s]?://\S+', '', text)
        
        return text.strip()
    
    def _get_fallback_news(self, category: str, limit: int = 3) -> List[Dict[str, Any]]:
        import random
        
        fallback_titles = {
            "mundo": ["ONU discute novas metas climáticas", "Conflito no Oriente Médio se intensifica", "G20 anuncia pacote econômico"],
            "brasil": ["Congresso aprova nova lei", "Inflação tem leve queda", "Governo anuncia programa social"],
            "tecnologia": ["Nova IA revoluciona mercado", "Apple lança novo dispositivo", "Cibersegurança em alta"],
            "campinas": ["Nova obra na região", "Campinas recebe evento internacional", "Prefeitura anuncia projeto"],
            "economia": ["Dólar fecha em baixa", "Bolsa de Valores sobe", "Juros mantidos"],
            "esportes": ["Brasil vence amistoso", "Campeonato tem novo líder", "Atleta brasileiro quebra recorde"],
            "ciencia": ["Cientistas descobrem novo planeta", "Vacina contra câncer avança", "Buraco negro é fotografado"],
            "cultura": ["Novo filme bate recorde", "Museu recebe exposição", "Livro ganha prêmio internacional"],
            "trabalhista": ["Nova regra trabalhista é aprovada", "Salário mínimo tem reajuste", "Empresas adotam home office"]
        }
        
        titles = fallback_titles.get(category, ["Notícia importante", "Atualização do dia"])
        
        news = []
        for i in range(min(limit, len(titles))):
            news.append({
                "title": self._clean_text(titles[i] if i < len(titles) else f"Notícia {i+1}"),
                "description": self._clean_text(f"Resumo da notícia sobre {category} - atualização importante."),
                "content": self._clean_text(f"Conteúdo completo da notícia sobre {category}."),
                "source": "Fonte simulada",
                "url": "#",
                "published": datetime.now().isoformat(),
                "category": category,
                "fallback": True
            })
        
        return news
    
    def _format_briefing(self, news: Dict[str, Any]) -> str:
        """Formata o briefing sem caracteres especiais."""
        parts = []
        parts.append(f"📰 BRIEFING DO DIA {datetime.now().strftime('%d/%m/%Y')}")
        parts.append("")
        
        total_news = 0
        for category, articles in news.items():
            if articles:
                parts.append(f"📌 {category.upper()}:")
                for i, article in enumerate(articles[:3], 1):
                    title = article.get('title', 'Sem título')
                    desc = article.get('description', '')[:150]
                    parts.append(f"  {i}. {title}")
                    if desc:
                        parts.append(f"     {desc}")
                    parts.append("")
                    total_news += 1
        
        if total_news == 0:
            parts.append("⚠️ Não encontrei notícias no momento.")
        
        parts.append("💡 Diga 'mais detalhes' para aprofundar.")
        
        return "\n".join(parts)
    
    async def daily_briefing(self, user_id: str, categories: List[str] = None) -> str:
        if not categories:
            categories = self._user_preferences.get(user_id, ["mundo", "brasil", "tecnologia"])
        
        news = await self.get_news(user_id, categories)
        
        # Formata sem caracteres especiais
        result = self._format_briefing(news)
        self._last_briefing[user_id] = result
        
        return result
    
    async def set_user_preferences(self, user_id: str, categories: List[str]) -> None:
        valid_categories = list(self._categories.keys())
        valid = [c for c in categories if c in valid_categories]
        
        if not valid:
            valid = ["mundo", "brasil", "tecnologia"]
        
        self._user_preferences[user_id] = valid
        await self._save_preferences()
        
        self.logger.info(f"📰 Preferências de {user_id}: {valid}")
    
    async def _load_preferences(self) -> None:
        try:
            data_path = Path(self.config.get("paths.data", "./data"))
            prefs_path = data_path / "news" / "preferences.json"
            
            if prefs_path.exists():
                with open(prefs_path, "r", encoding="utf-8") as f:
                    self._user_preferences = json.load(f)
        except Exception as e:
            self.logger.warning(f"Erro ao carregar preferências: {e}")
    
    async def _save_preferences(self) -> None:
        try:
            data_path = Path(self.config.get("paths.data", "./data"))
            prefs_path = data_path / "news" / "preferences.json"
            prefs_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(prefs_path, "w", encoding="utf-8") as f:
                json.dump(self._user_preferences, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Erro ao salvar preferências: {e}")
    
    async def shutdown(self) -> None:
        self.logger.info("📰 [NewsManager] Desligando...")
        self._running = False
        await self._save_preferences()
        self.logger.info("📰 [NewsManager] Desligado")
    
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "categories": len(self._categories),
            "users_preferences": len(self._user_preferences),
            "feedparser_available": FEEDPARSER_AVAILABLE
        }