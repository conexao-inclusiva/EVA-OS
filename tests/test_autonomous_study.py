import asyncio
import unittest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from src.learning.learning_manager import LearningManager
from src.kernel.events import Event, EventBus

class TestAutonomousStudy(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_event_bus = MagicMock(spec=EventBus)
        self.mock_logger = MagicMock()
        self.mock_config = MagicMock()
        self.mock_memory_manager = MagicMock()
        self.mock_knowledge_manager = MagicMock()
        
        self.manager = LearningManager(
            self.mock_event_bus,
            self.mock_logger,
            self.mock_config,
            self.mock_memory_manager,
            self.mock_knowledge_manager
        )

    async def test_survival_study_trigger(self):
        """Verifica se o estudo de sobrevivência é disparado."""
        record = await self.manager.study_survival_basics()
        
        self.assertEqual(record["category"], "survival_basics")
        self.assertIn(record["topic"], self.manager.survival_topics)
        self.assertTrue(len(self.manager._studied_records) > 0)
        self.mock_logger.info.assert_any_call(
            f"[AutonomousStudy] Estudando sobrevivência básica: {record['topic']}"
        )

    async def test_medicine_study_trigger(self):
        """Verifica se o estudo de medicina é disparado."""
        record = await self.manager.study_basic_medicine()
        
        self.assertEqual(record["category"], "basic_medicine")
        self.assertIn(record["topic"], self.manager.medicine_topics)
        self.assertTrue(len(self.manager._studied_records) > 0)
        self.mock_logger.info.assert_any_call(
            f"[AutonomousStudy] Estudando medicina básica: {record['topic']}"
        )

    async def test_keyword_detection_survival(self):
        """Verifica se palavras-chave de sobrevivência disparam estudo."""
        text = "Estou perdido na selva e sem fogo."
        result = await self.manager.check_keyword_trigger(text)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "survival_basics")

    async def test_keyword_detection_medicine(self):
        """Verifica se palavras-chave de medicina disparam estudo."""
        text = "Preciso de socorros para este ferimento."
        result = await self.manager.check_keyword_trigger(text)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "basic_medicine")

    async def test_system_idle_trigger(self):
        """Verifica se o evento de sistema ocioso inicia um ciclo de estudo."""
        event = Event(type="system.idle", payload={}, source="scheduler")
        await self.manager._on_system_idle(event)
        
        # O trigger_idle_study deve ter sido chamado e adicionado um registro
        self.assertTrue(len(self.manager._studied_records) > 0)
        self.mock_logger.info.assert_any_call(
            "[AutonomousStudy] Sistema ocioso detectado. Iniciando rotina de estudo autônomo..."
        )

    async def test_knowledge_manager_integration(self):
        """Verifica se conceitos são adicionados à base de conhecimento."""
        # Configura um mock para verificar a chamada add_concept
        self.mock_knowledge_manager.add_concept = MagicMock()
        self.mock_knowledge_manager.graph = MagicMock()
        
        await self.manager.study_survival_basics()
        
        # Verifica se o grafo foi atualizado
        self.assertTrue(self.mock_knowledge_manager.graph.add_node.called)

    async def test_invalid_keyword_input(self):
        """Verifica comportamento com entrada inválida nas palavras-chave."""
        result = await self.manager.check_keyword_trigger(123)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
