import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from src.core.event_types import EventType
from src.interfaces.web.web_server import WebServer
from src.kernel.events import Event, EventBus


class TestWebServerInitialization(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.config = MagicMock()
        self.config.get.side_effect = lambda key, default=None: default
        self.event_bus = MagicMock(spec=EventBus)

    def test_web_server_init(self):
        server = WebServer(self.event_bus, self.logger, self.config)
        self.assertIsNotNone(server.app)
        self.assertEqual(server.event_bus, self.event_bus)
        self.assertFalse(server._running)
        self.assertFalse(server._initialized)

    def test_web_event_subscriptions(self):
        server = WebServer(self.event_bus, self.logger, self.config)
        self.assertTrue(server._web_events_subscribed)
        subscribed_events = [call[0][0] for call in self.event_bus.subscribe.call_args_list]
        self.assertIn(EventType.ASSISTANT_RESPONSE, subscribed_events)
        self.assertIn(EventType.PROCESSING_START, subscribed_events)
        self.assertIn(EventType.PROCESSING_END, subscribed_events)
        self.assertIn("pipeline.status", subscribed_events)


class TestWebServerStaticAndRoutes(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.config = MagicMock()
        self.config.get.side_effect = lambda key, default=None: default
        self.event_bus = MagicMock(spec=EventBus)
        self.server = WebServer(self.event_bus, self.logger, self.config)
        self.client = TestClient(self.server.app)

    def test_index_route(self):
        response = self.client.get("/")
        self.assertIn(response.status_code, (200, 404))

    def test_status_route(self):
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "running")
        self.assertIn("websockets", data)
        self.assertIn("timestamp", data)

    def test_api_system_info_route(self):
        response = self.client.get("/api/system/info")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "operational")

    def test_api_agents_status_route(self):
        response = self.client.get("/api/agents/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("agents", data)
        self.assertIn("general", data["agents"])

    def test_static_files_mounting(self):
        routes = [getattr(route, "path", None) for route in self.server.app.routes]
        self.assertTrue(any(r and r.startswith("/static") for r in routes))


class TestWebServerEventBusIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger = MagicMock()
        self.config = MagicMock()
        self.config.get.side_effect = lambda key, default=None: default
        self.event_bus = MagicMock(spec=EventBus)
        self.event_bus.publish_async = AsyncMock()
        self.server = WebServer(self.event_bus, self.logger, self.config)

    async def test_websocket_user_message_publishes_event(self):
        ws_mock = MagicMock()
        raw_msg = json.dumps({
            "type": "user.message",
            "text": "Olá EVA!",
            "user": "Alberto",
            "mode": "normal"
        })

        await self.server._handle_websocket_message(ws_mock, raw_msg)

        self.event_bus.publish_async.assert_called_once()
        call_args = self.event_bus.publish_async.call_args
        self.assertEqual(call_args[0][0], EventType.USER_MESSAGE)
        payload = call_args[0][1]
        self.assertEqual(payload["text"], "Olá EVA!")
        self.assertEqual(payload["user"], "Alberto")
        self.assertEqual(payload["mode"], "normal")
        self.assertEqual(payload["source"], "web")

    async def test_broadcast_assistant_response(self):
        ws_mock = AsyncMock()
        self.server._active_websockets.add(ws_mock)

        event = Event(
            type=EventType.ASSISTANT_RESPONSE,
            payload={"text": "Resposta da EVA"},
            source="brain"
        )
        await self.server._on_response(event)

        ws_mock.send_text.assert_called_once()
        sent_data = json.loads(ws_mock.send_text.call_args[0][0])
        self.assertEqual(sent_data["type"], "assistant.response")
        self.assertEqual(sent_data["text"], "Resposta da EVA")

    async def test_broadcast_pipeline_status(self):
        ws_mock = AsyncMock()
        self.server._active_websockets.add(ws_mock)

        event = Event(
            type="pipeline.status",
            payload={"step": "context.ready"},
            source="brain"
        )
        await self.server._on_pipeline_status(event)

        ws_mock.send_text.assert_called_once()
        sent_data = json.loads(ws_mock.send_text.call_args[0][0])
        self.assertEqual(sent_data["type"], "pipeline.status")
        self.assertEqual(sent_data["step"], "context.ready")


if __name__ == "__main__":
    unittest.main()
