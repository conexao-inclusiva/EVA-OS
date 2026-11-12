"""Gerenciador de aprendizado da EVA."""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from src.kernel.events import Event, EventBus
from src.learning.pattern_extractor import PatternExtractor
from src.learning.knowledge_extractor import KnowledgeExtractor
from src.learning.behavior_analyzer import BehaviorAnalyzer
from src.learning.feedback_loop import FeedbackLoop
from src.learning.skill_learner import SkillLearner
from src.learning.anomaly_detector import AnomalyDetector
from src.learning.improvement_suggester import ImprovementSuggester


class LearningManager:
    """
    Gerenciador de aprendizado da EVA.
    
    Responsabilidades:
    - Extrair padrões de interações
    - Extrair conhecimento de conversas
    - Analisar comportamentos
    - Loop de feedback
    - Aprender novas habilidades
    - Detectar anomalias
    - Sugerir melhorias
    - Estudar autonomamente tópicos de sobrevivência básica e medicina básica
    """
    
    __plugin_name__ = "learning_manager"
    __plugin_version__ = "1.1.0"
    __plugin_description__ = "Gerenciador de aprendizado da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["core", "learning", "intelligence", "autonomous_study"]
    __plugin_capabilities__ = ["learning", "pattern_extraction", "feedback", "autonomous_study"]
    __plugin_requires__ = ["event_bus", "logger", "config", "memory_manager", "knowledge_manager"]
    
    def __init__(self, event_bus: EventBus, logger, config, memory_manager, knowledge_manager):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self.memory_manager = memory_manager
        self.knowledge_manager = knowledge_manager
        
        # Componentes
        self.pattern_extractor = PatternExtractor(self)
        self.knowledge_extractor = KnowledgeExtractor(self)
        self.behavior_analyzer = BehaviorAnalyzer(self)
        self.feedback_loop = FeedbackLoop(self)
        self.skill_learner = SkillLearner(self)
        self.anomaly_detector = AnomalyDetector(self)
        self.improvement_suggester = ImprovementSuggester(self)
        
        # Estado
        self._running = False
        self._learning_task: Optional[asyncio.Task] = None
        self._learning_interval = 300  # 5 minutos
        
        # Histórico de aprendizado
        self._learning_history: List[Dict[str, Any]] = []
        self._patterns: List[Dict[str, Any]] = []
        self._insights: List[Dict[str, Any]] = []
        
        # Tópicos de estudo autônomo
        self.survival_topics = [
            "técnicas de purificação de água",
            "obtenção de fogo em situações de emergência",
            "abrigos improvisados",
            "sinais de socorro e orientação sem bússola",
            "kits de sobrevivência básica"
        ]
        self.medicine_topics = [
            "primeiros socorros para cortes e hemorragias",
            "tratamento de queimaduras leves e graves",
            "RCP (Ressuscitação Cardiopulmonar) básica",
            "imobilização de fraturas e entorses",
            "identificação e tratamento de reações alérgicas graves"
        ]
        self._studied_records: List[Dict[str, Any]] = []
        
        # Registra listeners
        self._register_listeners()
        
        self.logger.info("LearningManager inicializado com suporte a estudo autônomo")
    
    def _register_listeners(self) -> None:
        """Registra ouvintes de eventos."""
        self.event_bus.subscribe("learning.analyze", self._on_analyze)
        self.event_bus.subscribe("learning.extract_patterns", self._on_extract_patterns)
        self.event_bus.subscribe("learning.feedback", self._on_feedback)
        self.event_bus.subscribe("learning.suggest", self._on_suggest)
        self.event_bus.subscribe("learning.get_insights", self._on_get_insights)
        
        # Eventos automáticos
        self.event_bus.subscribe("user.message", self._on_user_message)
        self.event_bus.subscribe("plan.completed", self._on_plan_completed)
        self.event_bus.subscribe("task.completed", self._on_task_completed)
        self.event_bus.subscribe("agent.response", self._on_agent_response)
        
        # Evento de gatilho de tempo ocioso / estudo autônomo
        self.event_bus.subscribe("system.idle", self._on_system_idle)
        self.event_bus.subscribe("learning.autonomous_study", self._on_autonomous_study_event)
    
    async def initialize(self) -> None:
        """Inicializa o LearningManager."""
        self.logger.info("LearningManager inicializando...")
        
        # Carrega histórico
        await self._load_history()
        
        self._running = True
        
        # Inicia aprendizado automático
        self._learning_task = asyncio.create_task(self._auto_learn())
        
        self.logger.info("LearningManager inicializado")
    
    async def start(self) -> None:
        """Inicia o LearningManager."""
        self.logger.info("LearningManager iniciando...")
        self.logger.info("LearningManager pronto")
    
    async def shutdown(self) -> None:
        """Desliga o LearningManager."""
        self.logger.info("LearningManager desligando...")
        
        self._running = False
        
        if self._learning_task:
            self._learning_task.cancel()
            try:
                await self._learning_task
            except asyncio.CancelledError:
                pass
        
        await self._save_history()
        
        self.logger.info("LearningManager desligado")
    
    # ===== COMANDOS =====
    
    async def _on_analyze(self, event: Event) -> None:
        """Analisa interações."""
        payload = event.payload
        request_id = payload.get("request_id")
        
        result = await self.analyze()
        
        await self.event_bus.publish_async(
            "learning.analysis_result",
            {
                "result": result,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="learning_manager"
        )
    
    async def _on_extract_patterns(self, event: Event) -> None:
        """Extrai padrões."""
        payload = event.payload
        limit = payload.get("limit", 50)
        request_id = payload.get("request_id")
        
        patterns = await self.pattern_extractor.extract(limit)
        
        await self.event_bus.publish_async(
            "learning.patterns",
            {
                "patterns": patterns,
                "count": len(patterns),
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="learning_manager"
        )
    
    async def _on_feedback(self, event: Event) -> None:
        """Processa feedback."""
        payload = event.payload
        feedback_type = payload.get("type", "general")
        content = payload.get("content", {})
        
        await self.feedback_loop.process(feedback_type, content)
        
        await self.event_bus.publish_async(
            "learning.feedback_processed",
            {
                "type": feedback_type,
                "success": True,
                "timestamp": datetime.now().isoformat()
            },
            source="learning_manager"
        )
    
    async def _on_suggest(self, event: Event) -> None:
        """Sugere melhorias."""
        payload = event.payload
        request_id = payload.get("request_id")
        
        suggestions = await self.improvement_suggester.suggest()
        
        await self.event_bus.publish_async(
            "learning.suggestions",
            {
                "suggestions": suggestions,
                "count": len(suggestions),
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="learning_manager"
        )
    
    async def _on_get_insights(self, event: Event) -> None:
        """Retorna insights."""
        payload = event.payload
        request_id = payload.get("request_id")
        limit = payload.get("limit", 10)
        
        insights = self._insights[-limit:]
        
        await self.event_bus.publish_async(
            "learning.insights",
            {
                "insights": insights,
                "count": len(insights),
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="learning_manager"
        )
    
    # ===== MÉTODOS DE ESTUDO AUTÔNOMO =====
    
    async def study_survival_basics(self) -> Dict[str, Any]:
        """Estuda tópicos de sobrevivência básica e registra na base de conhecimento."""
        import random
        topic = random.choice(self.survival_topics)
        self.logger.info(f"[AutonomousStudy] Estudando sobrevivência básica: {topic}")
        
        content = f"Estudo autônomo sobre sobrevivência básica focado em: {topic}. Diretrizes essenciais para garantir segurança e tomada de decisão em cenários críticos."
        
        # Adiciona na base de conhecimento se disponível
        if self.knowledge_manager is not None and hasattr(self.knowledge_manager, "add_concept"):
            try:
                if hasattr(self.knowledge_manager, "graph") and self.knowledge_manager.graph:
                    self.knowledge_manager.graph.add_node(
                        concept=f"survival_{topic.replace(' ', '_')}",
                        description=content,
                        category="survival_basics",
                        confidence=0.9,
                        source="autonomous_study"
                    )
            except Exception as e:
                self.logger.warning(f"Não foi possível salvar conceito no KnowledgeManager: {e}")
                
        record = {
            "category": "survival_basics",
            "topic": topic,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self._studied_records.append(record)
        return record

    async def study_basic_medicine(self) -> Dict[str, Any]:
        """Estuda tópicos de medicina básica e primeiros socorros."""
        import random
        topic = random.choice(self.medicine_topics)
        self.logger.info(f"[AutonomousStudy] Estudando medicina básica: {topic}")
        
        content = f"Estudo autônomo sobre medicina básica focado em: {topic}. Protocolo de primeiros socorros para suporte a emergências e preservação da vida."
        
        if self.knowledge_manager is not None and hasattr(self.knowledge_manager, "add_concept"):
            try:
                if hasattr(self.knowledge_manager, "graph") and self.knowledge_manager.graph:
                    self.knowledge_manager.graph.add_node(
                        concept=f"medicine_{topic.replace(' ', '_')}",
                        description=content,
                        category="basic_medicine",
                        confidence=0.9,
                        source="autonomous_study"
                    )
            except Exception as e:
                self.logger.warning(f"Não foi possível salvar conceito no KnowledgeManager: {e}")
                
        record = {
            "category": "basic_medicine",
            "topic": topic,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self._studied_records.append(record)
        return record

    async def trigger_idle_study(self) -> Dict[str, Any]:
        """Executa um ciclo de estudo autônomo durante tempo ocioso."""
        import random
        choice = random.choice(["survival", "medicine"])
        if choice == "survival":
            return await self.study_survival_basics()
        else:
            return await self.study_basic_medicine()

    async def check_keyword_trigger(self, text: str) -> Optional[Dict[str, Any]]:
        """Verifica se a mensagem contém palavras-chave de sobrevivência ou medicina para estudo imediato."""
        if not isinstance(text, str):
            return None
        text_lower = text.casefold()
        
        survival_keywords = ["sobrevivencia", "sobreviver", "abrigos", "fogo", "agua", "fome", "selva", "emergencia"]
        medicine_keywords = ["medicina", "medico", "socorros", "ferimento", "cortes", "sangramento", "queimadura", "rcp", "fractura", "alergia"]
        
        triggered = None
        for kw in survival_keywords:
            if kw in text_lower:
                triggered = await self.study_survival_basics()
                break
        if not triggered:
            for kw in medicine_keywords:
                if kw in text_lower:
                    triggered = await self.study_basic_medicine()
                    break
        return triggered

    async def _on_system_idle(self, event: Event) -> None:
        """Handler para o gatilho de sistema ocioso."""
        self.logger.info("[AutonomousStudy] Sistema ocioso detectado. Iniciando rotina de estudo autônomo...")
        await self.trigger_idle_study()

    async def _on_autonomous_study_event(self, event: Event) -> None:
        """Handler para evento explícito de estudo autônomo."""
        payload = event.payload or {}
        category = payload.get("category")
        if category == "survival_basics":
            await self.study_survival_basics()
        elif category == "basic_medicine":
            await self.study_basic_medicine()
        else:
            await self.trigger_idle_study()

    # ===== EVENTOS AUTOMÁTICOS =====
    
    async def _on_user_message(self, event: Event) -> None:
        """Processa mensagem do usuário."""
        payload = event.payload
        text = payload.get("text", "")
        user = payload.get("user", "unknown")
        
        # Extrai conhecimento da mensagem
        await self.knowledge_extractor.extract_from_text(text, source=f"user_{user}")
        
        # Analisa padrões
        await self.pattern_extractor.process_message(text, user)
        
        # Intercepta palavras-chave para estudo autônomo imediato (sobrevivência / medicina)
        await self.check_keyword_trigger(text)
    
    async def _on_plan_completed(self, event: Event) -> None:
        """Processa conclusão de plano."""
        payload = event.payload
        plan_id = payload.get("plan_id")
        result = payload.get("result", {})
        
        # Aprende com o plano
        await self.skill_learner.learn_from_plan(plan_id, result)
        
        # Extrai conhecimento
        if result.get("knowledge"):
            await self.knowledge_extractor.extract_from_dict(
                result.get("knowledge"),
                source=f"plan_{plan_id}"
            )
    
    async def _on_task_completed(self, event: Event) -> None:
        """Processa conclusão de tarefa."""
        payload = event.payload
        task_id = payload.get("task_id")
        result = payload.get("result", {})
        
        # Atualiza padrões
        await self.pattern_extractor.process_task(task_id, result)
    
    async def _on_agent_response(self, event: Event) -> None:
        """Processa resposta de agente."""
        payload = event.payload
        agent = payload.get("agent", "unknown")
        response = payload.get("result", {})
        
        # Feedback loop
        if response.get("success") is not None:
            await self.feedback_loop.process_agent_response(agent, response)
    
    # ===== APRENDIZADO AUTOMÁTICO =====
    
    async def _auto_learn(self) -> None:
        """Loop de aprendizado automático."""
        while self._running:
            try:
                await asyncio.sleep(self._learning_interval)
                
                if self._running:
                    await self.analyze()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro no aprendizado automático: {e}")
    
    # ===== MÉTODOS PRINCIPAIS =====
    
    async def analyze(self) -> Dict[str, Any]:
        """
        Executa análise completa de aprendizado.
        """
        self.logger.info("Iniciando análise de aprendizado...")
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "patterns": [],
            "knowledge": [],
            "insights": [],
            "anomalies": [],
            "suggestions": []
        }
        
        # 1. Extrai padrões
        patterns = await self.pattern_extractor.extract(limit=20)
        result["patterns"] = patterns
        
        # 2. Extrai conhecimento
        knowledge = await self.knowledge_extractor.extract(limit=10)
        result["knowledge"] = knowledge
        
        # 3. Analisa comportamento
        behavior = await self.behavior_analyzer.analyze()
        result["behavior"] = behavior
        
        # 4. Detecta anomalias
        anomalies = await self.anomaly_detector.detect()
        result["anomalies"] = anomalies
        
        # 5. Gera insights
        insights = await self._generate_insights(result)
        result["insights"] = insights
        self._insights.extend(insights)
        
        # 6. Sugere melhorias
        suggestions = await self.improvement_suggester.suggest()
        result["suggestions"] = suggestions
        
        # Registra histórico
        self._learning_history.append(result)
        if len(self._learning_history) > 100:
            self._learning_history = self._learning_history[-100:]
        
        self.logger.info(f"Análise concluída: {len(patterns)} padrões, {len(insights)} insights")
        
        # Publica evento
        await self.event_bus.publish_async(
            "learning.analysis_complete",
            {
                "result": result,
                "timestamp": datetime.now().isoformat()
            },
            source="learning_manager"
        )
        
        return result
    
    async def _generate_insights(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Gera insights a partir da análise.
        """
        insights = []
        
        # Padrões interessantes
        for pattern in analysis.get("patterns", [])[:5]:
            if pattern.get("frequency", 0) > 3:
                insights.append({
                    "type": "pattern",
                    "title": f"Padrão detectado: {pattern.get('name', 'desconhecido')}",
                    "description": pattern.get("description", ""),
                    "confidence": pattern.get("confidence", 0.5),
                    "timestamp": datetime.now().isoformat()
                })
        
        # Anomalias
        for anomaly in analysis.get("anomalies", []):
            insights.append({
                "type": "anomaly",
                "title": f"Anomalia: {anomaly.get('type', 'desconhecida')}",
                "description": anomaly.get("description", ""),
                "severity": anomaly.get("severity", "medium"),
                "timestamp": datetime.now().isoformat()
            })
        
        # Comportamentos
        behavior = analysis.get("behavior", {})
        if behavior.get("common_topics"):
            insights.append({
                "type": "behavior",
                "title": "Tópicos mais frequentes",
                "description": f"Os tópicos mais comuns são: {', '.join(behavior['common_topics'][:3])}",
                "timestamp": datetime.now().isoformat()
            })
        
        return insights
    
    # ===== PERSISTÊNCIA =====
    
    async def _load_history(self) -> None:
        """Carrega histórico."""
        # TODO: Implementar persistência
        pass
    
    async def _save_history(self) -> None:
        """Salva histórico."""
        # TODO: Implementar persistência
        pass
    
    # ===== MÉTODOS PÚBLICOS =====
    
    def get_insights(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtém insights recentes."""
        return self._insights[-limit:]
    
    def get_patterns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtém padrões recentes."""
        return self._patterns[-limit:]
    
    async def health_check(self) -> dict:
        """Health check do LearningManager."""
        return {
            "status": "running" if self._running else "stopped",
            "patterns": len(self._patterns),
            "insights": len(self._insights),
            "history": len(self._learning_history),
            "studied_records": len(self._studied_records)
        }
