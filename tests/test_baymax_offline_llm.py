import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock
from src.llm.llm_manager import LLMManager
from src.prompt.prompt_builder import PromptBuilder
from src.consciousness.brain import Brain
from src.kernel.events import EventBus

class TestBaymaxOfflineLLM(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.event_bus = MagicMock(spec=EventBus)
        self.logger = MagicMock()
        self.config = {
            "llm.ollama.host": "localhost",
            "llm.ollama.port": 11434,
            "llm.model": "qwen2.5:7b"
        }
        self.llm_manager = LLMManager(self.event_bus, self.logger, self.config)
        self.prompt_builder = PromptBuilder(self.event_bus, self.logger, self.config)

    async def test_offline_llm_fallback(self):
        """Valida que o LLMManager retorna a resposta de fallback quando offline."""
        self.llm_manager._ollama_available = False
        self.llm_manager._check_ollama = AsyncMock(return_value=False)
        
        response = await self.llm_manager.generate("Oi, tudo bem?")
        self.assertIn("Estou operando em modo offline", response)
        self.assertIn("modelo de linguagem local não está disponível", response)

    async def test_baymax_persona_prompt_structure(self):
        """Valida se a persona Baymax é incorporada no prompt."""
        context = {"message": "Como você está?"}
        memory = {"history": []}
        knowledge = {}
        plan = {}
        reasoning = {}
        emotion = {}
        
        prompt_data = await self.prompt_builder.process(
            context, memory, knowledge, plan, reasoning, emotion
        )
        prompt = prompt_data["prompt"]
        
        self.assertIn("Você é EVA, uma assistente pessoal e companheira atenta inspirada no Baymax", prompt)
        self.assertIn("acolhedor, calmo, claro, atencioso", prompt)

    async def test_cognitive_pipeline_flow_integrity(self):
        """Valida se o fluxo de processamento integra os componentes de forma coesa."""
        # Setup mocks para o cérebro
        brain = Brain(self.event_bus, self.logger, self.config)
        brain._modules = {
            "llm_manager": self.llm_manager,
            "prompt_builder": self.prompt_builder
        }
        
        # Simula uma mensagem que deveria acionar empatia
        text = "Estou com dor de cabeça e cansado."
        empathetic_prefix = brain._check_baymax_empathy_routing(text)
        
        self.assertIsNotNone(empathetic_prefix)
        self.assertIn("Sinto muito que você esteja se sentindo assim", empathetic_prefix)

    async def test_decision_gate_logic(self):
        """Valida se o LLMDecisionGate permite roteamento local."""
        gate = self.llm_manager.decision_gate
        context = {"unresolved_references": False}
        local_res = {"response": "Estou bem, como você?", "confidence": 0.9, "resolved": True}
        
        should_call = await gate.should_call_llm(context, local_res)
        self.assertFalse(should_call, "DecisionGate deveria retornar False para resposta local de alta confiança.")

if __name__ == "__main__":
    unittest.main()
