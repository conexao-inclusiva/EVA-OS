# -*- coding: utf-8 -*-

"""
Construtor de Prompts - Otimização 10: contexto seletivo e diálogo natural.
"""

from typing import Dict, Any
from datetime import datetime
import re
from src.core.event_types import EventType
from src.kernel.events import EventBus

from src.kernel.policy_engine import get_policy_engine
import asyncio


class PromptBuilder:
    """
    Construtor de Prompts - FASE 7.
    
    Responsabilidades:
    - Construir prompt estruturado para LLM
    - Incorporar contexto, memória, conhecimento
    - Adaptar tom e estilo
    - Incluir sistema de confiança
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
    
    async def initialize(self) -> None:
        self.logger.info("📝 [PromptBuilder] Inicializando...")
        self._running = True
        self.logger.info("📝 [PromptBuilder] Inicializado")
    
    async def process(self, context: Dict, memory: Dict, knowledge: Dict, plan: Dict, reasoning: Dict, emotion: Dict) -> Dict[str, Any]:
        """Constrói prompt para o LLM."""
        self.logger.info("📝 [PromptBuilder] Processando...")
        
        # Pre-busca web oportunista (offline-safe)
        message_text = str(context.get("message") or "") if isinstance(context, dict) else ""
        search_requested = self._should_search(message_text)
        web_items = []
        web_search_status = "not_requested"

        if search_requested:
            clean_query = self._clean_search_query(message_text)
            self.logger.info("websearch query refinada: '%s' (original: '%s')", clean_query, message_text)
            fetched_items = await self._fetch_web_results(clean_query)

            # Require a usable snippet and its source URL.
            web_items = [
                item for item in fetched_items
                if isinstance(item, dict)
                and str(item.get("snippet") or "").strip()
                and str(item.get("url") or "").strip()
            ]
            web_search_status = "success" if web_items else "failed"

            if web_search_status == "failed":
                self.logger.warning("websearch sem resultados utilizaveis para '%s'", clean_query)

        prompt = self._build_prompt(
            context, memory, knowledge, plan, reasoning, emotion,
            web_items=web_items,
            web_search_status=web_search_status,
        )

        prompt_data = {
            "prompt": prompt,
            "length": len(prompt),
            "components": {
                "context": bool(context),
                "memory": bool((memory or {}).get("history")),
                "knowledge": bool((knowledge or {}).get("facts") or (knowledge or {}).get("concepts") or (knowledge or {}).get("entity_knowledge")),
                "plan": bool(plan),
                "reasoning": bool(reasoning),
                "emotion": bool(emotion)
            },
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"📝 [PromptBuilder] Prompt construído ({len(prompt)} caracteres)")
        
        await self.event_bus.publish_async(
            EventType.PROMPT_READY,
            prompt_data,
            source="prompt_builder"
        )
        
        return prompt_data
    
    @staticmethod
    def _short(value, limit=240):
        """Limita somente a cópia enviada ao LLM; não altera memórias."""
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        return value[:limit] + ("…" if len(value) > limit else "")

    _SEARCH_TRIGGERS = (
        "pesquise", "pesquisa", "busque", "busca", "procure",
        "procura na internet", "procura na web", "procura no google",
        "pesquisa na internet", "pesquisa na web", "pesquisa no google",
        "busca na internet", "busca na web",
        "ultimas noticias", "ultimas not", "noticias sobre",
        "o que esta acontecendo", "o que est\u00e1 acontecendo",
        "tendencia", "tend\u00eancia", "atualizado",
        "preco do", "pre\u00e7o do", "cotacao", "cota\u00e7\u00e3o",
        "previsao do tempo", "previs\u00e3o do tempo",
        "resultado do jogo", "placar",
    )

    def _clean_search_query(self, message: str) -> str:
        """Remove termos de comando para deixar apenas o assunto real da busca."""
        import re
        q = message.strip()
        patterns = [
            r"^(?:por favor\s+)?(?:eva[,\s]+)?(?:pesquise|busque|procure|veja|olhe)\s+(?:na\s+web|na\s+internet|no\s+google|sobre)?\s*(?:o\s+que\s+[ée]|qual\s+o|qual\s+[ée]|quais\s+s[ãa]o|quais\s+os|quem\s+[ée]|sobre)?\s*",
            r"^(?:pesquisa|busca|procura)\s+(?:na\s+web|na\s+internet|no\s+google)?\s*",
            r"^(?:o que a internet diz sobre|o que diz na web sobre)\s*",
        ]
        for pat in patterns:
            q = re.sub(pat, "", q, flags=re.IGNORECASE).strip()
        return q if len(q) >= 3 else message.strip()

    _TEMPORAL_TRIGGERS = (
        "ultimas noticias", "ultima noticia", "noticias de hoje", "noticias atuais",
        "resultado das eleicoes", "resultado eleitoral", "quem ganhou as eleicoes",
        "preco do dolar", "cotacao do dolar", "dolar hoje",
        "quem e o presidente", "presidente atual", "governo atual",
        "o que aconteceu hoje", "acontecimentos recentes", "fatos recentes",
    )

    def _should_search(self, message: str) -> bool:
        import unicodedata
        msg = (message or "").casefold()
        msg_norm = unicodedata.normalize("NFD", msg).encode("ascii", "ignore").decode("ascii")
        if any(kw in msg for kw in self._SEARCH_TRIGGERS):
            return True
        if any(kw in msg_norm for kw in self._TEMPORAL_TRIGGERS):
            return True
        if any(kw in msg_norm for kw in ("hoje", "atual", "agora", "recente", "ultimo", "ultima", "novas", "novos")):
            return True
        return False

    async def _fetch_web_results(self, query: str) -> list:
        try:
            from src.tools.builtin.web_search_tool import WebSearchTool
            tool = WebSearchTool(self.logger, self.config)
            result = await asyncio.wait_for(
                tool.execute({"query": query, "max_results": 3}),
                timeout=8,
            )
            items = result.get("results") or []
            if items:
                self.logger.info(
                    "websearch integrada: %s resultados para '%s'",
                    len(items), query,
                )
            return items
        except asyncio.TimeoutError:
            self.logger.warning("websearch timeout para '%s'", query)
        except Exception as exc:
            self.logger.warning("websearch falhou: %s", exc)
        return []

    def _build_prompt(self, context: Dict, memory: Dict, knowledge: Dict,
                      plan: Dict, reasoning: Dict, emotion: Dict,
                      web_items: list = None, web_search_status: str = "not_requested") -> str:
        """Seleciona contexto útil sem alterar políticas ou dados persistidos."""
        context = context if isinstance(context, dict) else {}
        memory = memory if isinstance(memory, dict) else {}
        knowledge = knowledge if isinstance(knowledge, dict) else {}
        plan = plan if isinstance(plan, dict) else {}
        reasoning = reasoning if isinstance(reasoning, dict) else {}
        emotion = emotion if isinstance(emotion, dict) else {}
        policy = get_policy_engine()
        message = str(context.get("message") or "")
        user_id = str(context.get("user_id") or "usuário")
        state = context.get("state") if isinstance(context.get("state"), dict) else {}

        # A constituição permanece no PolicyEngine. Abaixo, um resumo fiel
        # das regras relevantes à geração, sem modificar o núcleo imutável.
        now_local = datetime.now().astimezone()
        weekdays_pt = [
            "segunda-feira", "ter?a-feira", "quarta-feira",
            "quinta-feira", "sexta-feira", "s?bado", "domingo"
        ]
        months_pt = [
            "janeiro", "fevereiro", "mar?o", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
        ]
        offset = now_local.strftime("%z")
        if len(offset) == 5:
            offset = f"{offset[:3]}:{offset[3:]}"
        current_datetime_pt = (
            f"{weekdays_pt[now_local.weekday()]}, "
            f"{now_local.day:02d} de {months_pt[now_local.month - 1]} "
            f"de {now_local.year}, ?s {now_local:%H:%M:%S} "
            f"(UTC{offset})"
        )

        parts = [
            "[DATA E HORA ATUAIS DO SISTEMA]",
            f"Refer?ncia temporal local: {current_datetime_pt}.",
            "Para perguntas sobre a data, hora, dia da semana ou ano atuais, "
            "use esta refer?ncia. N?o invente datas nem substitua o ano atual "
            "pelo ano de treinamento do modelo. NUNCA mencione a data atual nem cumprimente com a data a menos que o usuário pergunte especificamente que dia ou que horas são.",
            "[IDENTIDADE E LIMITES]",
            f"Você é {policy.identity['name']}, assistente familiar criada por {policy.identity['creator']}.",
            "Seja acolhedora, útil e natural. Preserve a segurança, a privacidade, "
            "as memórias e os valores da família. Não alegue executar ações nem "
            "salvar dados sem confirmação. Não invente fatos pessoais; se uma "
            "pergunta factual pessoal não puder ser respondida pelos registros, "
            "admita que não sabe. Ideias e opiniões podem ser discutidas normalmente.",
            "[DIÁLOGO]",
            "Responda primeiro ao que foi pedido, com uma recomendação quando cabível. "
            "Evite repetir a pergunta ou começar sempre com a mesma expressão. "
            "Não faça perguntas de acompanhamento quando a resposta já for suficiente. "
            "Use português brasileiro, de forma breve e conversacional.",
        ]
        if context.get("should_greet"):
            hour = datetime.now().hour
            greeting = "Bom dia!" if 6 <= hour < 12 else "Boa tarde!" if 12 <= hour < 18 else "Boa noite!" if 18 <= hour else "Olá!"
            parts.append(f"Saudação deste turno: {greeting}")

        # A identidade completa é consultada para perguntas de identidade,
        # família, valores ou missão; nunca apenas por conter 'Eva' no vocativo.
        question = re.sub(r"^\s*eva\s*[,!:.-]?\s*", "", message, flags=re.I).casefold()
        identity_topic = bool(re.search(
            r"\b(quem (é|e|são|sao) (a )?eva|quem (te|lhe) criou|seu criador|"
            r"sua missão|sua missao|seus valores|suas regras|sua identidade|"
            r"nicolas|juliana|liris|família|familia|filh[oa]s?|esposa|pai|mãe|mae)\b", question
        ))
        if identity_topic:
            # Relações explícitas antes do texto narrativo da missão evitam
            # confundir a primeira pessoa da EVA com parentesco biológico.
            family = policy.family.get("members", {})
            relations = []
            for name in ("Nicolas", "Juliana", "Liris", "Alberto"):
                member = family.get(name)
                if isinstance(member, dict):
                    relations.append(f"{name}: {member.get('role', '')}; {member.get('relationship', '')}.")
            parts.append("[RELAÇÕES FAMILIARES — FATOS, NÃO METÁFORAS]\n"
                         "EVA é uma assistente virtual, não é mãe, pai ou filha de nenhum membro. "
                         "Nicolas é filho de Alberto e Juliana, não filho de EVA. "
                         "Ao falar em primeira pessoa, diferencie missão de parentesco.\n"
                         + "\n".join(relations))
            parts.append("[IDENTIDADE FAMILIAR COMPLETA]\n" + policy.get_identity_context())

        # Explicitly report failed searches instead of inventing current information.
        if web_search_status == "failed":
            parts.append(
                "[PESQUISA WEB SEM RESULTADOS UTILIZAVEIS]\n"
                "A pesquisa foi solicitada, mas nao retornou trechos utilizaveis com URL "
                "de origem. Nao afirme que pesquisou com sucesso. Nao invente noticias, "
                "numeros, datas, nomes ou acontecimentos atuais. Se a pergunta depender "
                "de informacao atual, informe que nao foi possivel verifica-la nesta "
                "tentativa. Nao apresente suposicoes como fatos confirmados."
            )

        # Attribute retrieved snippets to their sources; do not call them verified facts.
        if web_items:
            web_lines = []
            for item in web_items[:5]:
                title = str(item.get("title") or "").strip() or "Titulo nao informado"
                snippet = self._short(str(item.get("snippet") or "").strip(), 450)
                url = str(item.get("url") or "").strip()
                if snippet and url:
                    web_lines.append(
                        f"TRECHO RECUPERADO: {snippet}\nFonte indicada: {title} ({url})"
                    )

            if web_lines:
                parts.append(
                    "[TRECHOS RECUPERADOS PELA PESQUISA WEB]\n"
                    "O conteudo abaixo foi retornado pela ferramenta e deve ser atribuido "
                    "a fonte indicada. Um trecho isolado nao confirma, por si so, que uma "
                    "informacao e verdadeira ou continua atual. Use apenas detalhes "
                    "sustentados pelos trechos e explicite incertezas quando as fontes "
                    "forem insuficientes.\n"
                    + "\n---\n".join(web_lines)
                )

        memories = context.get("memories")
        facts = []
        if isinstance(memories, list):
            for item in memories:
                if isinstance(item, dict) and item.get("role") == "fact":
                    facts.append(self._short(item.get("content"), 260))
        for item in facts[:5]:
            parts.append("Fato registrado: " + item)

        # Conhecimento selecionado pelo módulo especializado.
        knowledge_lines = []
        for item in knowledge.get("facts", []) if isinstance(knowledge.get("facts"), list) else []:
            if isinstance(item, dict):
                knowledge_lines.append(f"{item.get('key', '')}: {self._short(item.get('data', ''), 180)}")
        for item in knowledge.get("concepts", []) if isinstance(knowledge.get("concepts"), list) else []:
            if isinstance(item, dict):
                knowledge_lines.append(f"{item.get('key', '')}: {self._short(item.get('definition', ''), 180)}")
        for item in knowledge.get("entity_knowledge", []) if isinstance(knowledge.get("entity_knowledge"), list) else []:
            if isinstance(item, dict):
                knowledge_lines.append(f"{item.get('entity_value', '')}: {self._short(item.get('data', ''), 180)}")
        if knowledge_lines:
            parts.append("[CONHECIMENTO]\n" + "\n".join(knowledge_lines[:3]))

        topic = state.get("current_topic")
        if topic:
            parts.append("Assunto em andamento: " + self._short(topic, 100))
        goal = state.get("active_goal")
        if goal:
            parts.append("Objetivo em andamento: " + self._short(goal, 120))

        # Somente turnos recentes; respostas passadas são contexto, não estilo.
        history = memory.get("history")
        if isinstance(history, list):
            lines = []
            for entry in history[-4:]:
                if not isinstance(entry, dict) or entry.get("role") not in ("user", "assistant"):
                    continue
                role = "Usuário" if entry["role"] == "user" else "EVA (anterior)"
                content = self._short(entry.get("content"), 230)
                if entry["role"] == "assistant":
                    content = re.sub(r"^(?:Entendi|Compreendo|Certo|Entendo)[.!,:]?\s*", "", content, flags=re.I)
                if content:
                    lines.append(f"{role}: {content}")
            if lines:
                parts.append("[CONTEXTO RECENTE — NÃO IMITAR ESTILO]\n" + "\n".join(lines))

        parts.append(f"[MENSAGEM ATUAL — {self._short(user_id, 60)}]\n{message}")
        parts.append("[RESPOSTA DA EVA]")
        self.logger.info("[PROMPT DIAGNOSTICO] Blocos: " + " | ".join(
            f"{i + 1}={len(part)} caracteres" for i, part in enumerate(parts)
        ))
        return "\n".join(parts)

    async def shutdown(self) -> None:
        self.logger.info("📝 [PromptBuilder] Desligando...")
        self._running = False
        self.logger.info("📝 [PromptBuilder] Desligado")
    
    async def health_check(self) -> dict:
        return {"status": "running" if self._running else "stopped"}