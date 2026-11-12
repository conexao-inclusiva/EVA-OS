"""Testes do Core EVA OS."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock

from src.core.event_bus import EventBus, Event, EventPriority
from src.core.service_registry import ServiceRegistry, ServiceStatus
from src.core.dependency_container import DependencyContainer
from src.core.lifecycle_manager import LifecycleManager, ModuleState
from src.core.module_loader import ModuleLoader
from src.core.state_manager import StateManager, SystemState


class TestEventBus:
    """Testes do EventBus."""
    
    def setup_method(self):
        self.logger = Mock()
        self.bus = EventBus(self.logger)
        self.bus._running = True  # Para testes síncronos
    
    def test_publish_sync(self):
        """Testa publicação síncrona."""
        called = False
        
        def callback(event):
            nonlocal called
            called = True
            assert event.type == "TEST_EVENT"
            assert event.data == {"foo": "bar"}
        
        self.bus.subscribe("TEST_EVENT", callback)
        self.bus.publish(Event("TEST_EVENT", {"foo": "bar"}))
        
        assert called
    
    @pytest.mark.asyncio
    async def test_publish_async(self):
        """Testa publicação assíncrona."""
        called = False
        
        async def callback(event):
            nonlocal called
            called = True
            assert event.type == "TEST_EVENT"
        
        self.bus.subscribe_async("TEST_EVENT", callback)
        await self.bus.publish_async(Event("TEST_EVENT"))
        
        # Aguarda processamento
        await asyncio.sleep(0.1)
        assert called
    
    def test_wildcard(self):
        """Testa listener wildcard."""
        called = []
        
        def callback(event):
            called.append(event.type)
        
        self.bus.subscribe("*", callback)
        self.bus.publish(Event("EVENT_1"))
        self.bus.publish(Event("EVENT_2"))
        
        assert "EVENT_1" in called
        assert "EVENT_2" in called
    
    def test_has_subscribers(self):
        """Testa verificação de inscritos."""
        def callback(event): pass
        
        assert not self.bus.has_subscribers("TEST_EVENT")
        self.bus.subscribe("TEST_EVENT", callback)
        assert self.bus.has_subscribers("TEST_EVENT")


class TestServiceRegistry:
    """Testes do ServiceRegistry."""
    
    def setup_method(self):
        self.logger = Mock()
        self.registry = ServiceRegistry(self.logger)
    
    def test_register_and_get(self):
        """Testa registro e obtenção."""
        class TestService:
            pass
        
        service = TestService()
        self.registry.register("test", service)
        
        assert self.registry.get("test") is service
        assert self.registry.exists("test")
    
    def test_alias(self):
        """Testa alias."""
        class TestService:
            pass
        
        service = TestService()
        self.registry.register("test", service)
        self.registry.register_alias("alias", "test")
        
        assert self.registry.get("alias") is service
    
    def test_status(self):
        """Testa status."""
        class TestService:
            pass
        
        service = TestService()
        self.registry.register("test", service)
        
        assert self.registry.get_status("test") == ServiceStatus.REGISTERED
        
        self.registry.set_status("test", ServiceStatus.RUNNING)
        assert self.registry.get_status("test") == ServiceStatus.RUNNING


class TestDependencyContainer:
    """Testes do DependencyContainer."""
    
    def setup_method(self):
        self.logger = Mock()
        self.registry = ServiceRegistry(self.logger)
        self.container = DependencyContainer(self.logger, self.registry)
    
    def test_resolve_singleton(self):
        """Testa resolução de singleton."""
        class TestService:
            pass
        
        service = TestService()
        self.container.register_singleton("test", service)
        
        resolved = self.container.resolve("test")
        assert resolved is service
    
    def test_resolve_factory(self):
        """Testa resolução de fábrica."""
        class TestService:
            pass
        
        self.container.register_factory("test", lambda: TestService())
        
        resolved = self.container.resolve("test")
        assert isinstance(resolved, TestService)


class TestStateManager:
    """Testes do StateManager."""
    
    def setup_method(self):
        self.logger = Mock()
        self.event_bus = Mock()
        self.state_manager = StateManager(self.logger, self.event_bus)
    
    def test_initial_state(self):
        """Testa estado inicial."""
        assert self.state_manager.get_state() == SystemState.OFFLINE
    
    def test_set_state(self):
        """Testa mudança de estado."""
        result = self.state_manager.set_state(SystemState.BOOTING, "Teste")
        assert result
        assert self.state_manager.get_state() == SystemState.BOOTING
    
    def test_invalid_transition(self):
        """Testa transição inválida."""
        result = self.state_manager.set_state(SystemState.EXECUTING, "Teste")
        assert not result
        assert self.state_manager.get_state() == SystemState.OFFLINE
    
    def test_busy_state(self):
        """Testa verificação de ocupado."""
        assert not self.state_manager.is_busy()
        
        self.state_manager.set_state(SystemState.THINKING, "Teste")
        assert self.state_manager.is_busy()
    
    def test_idle_state(self):
        """Testa verificação de ocioso."""
        assert not self.state_manager.is_idle()
        
        self.state_manager.set_state(SystemState.IDLE, "Teste")
        assert self.state_manager.is_idle()