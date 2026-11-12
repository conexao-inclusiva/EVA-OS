import unittest
import asyncio
from aiohttp import web
from src.tools.builtin.jellyfin_tool import JellyfinTool
from src.core.llm_decision_gate import LLMDecisionGate
from src.llm.llm_manager import LLMManager


class FakeLogger:
    def __init__(self):
        self.errors = []
        self.infos = []

    def info(self, msg, *args, **kwargs):
        self.infos.append(msg)

    def warning(self, msg, *args, **kwargs):
        pass

    def error(self, msg, *args, **kwargs):
        self.errors.append(msg)

    def debug(self, msg, *args, **kwargs):
        pass


class FakeConfig:
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestJellyfinSearch(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger = FakeLogger()

        self.app = web.Application()
        self.app.router.add_get("/Search/Hints", self._handle_search)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()

        host, port = self.site._server.sockets[0].getsockname()[:2]
        self.server_url = f"http://{host}:{port}"

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def _handle_search(self, request):
        token = request.headers.get("X-Emby-Token")
        if token != "valid-api-key":
            return web.json_response({"Message": "Unauthorized"}, status=401)

        query = request.query.get("searchTerm", "")
        media_type = request.query.get("includeMediaTypes", "")

        if media_type != "Movie":
            return web.json_response([], status=200)

        mock_movies = [
            {"Name": "Inception", "Type": "Movie", "Id": "1"},
            {"Name": "Interstellar", "Type": "Movie", "Id": "2"},
            {"Name": "Matrix", "Type": "Movie", "Id": "3"}
        ]

        results = [m for m in mock_movies if query.lower() in m["Name"].lower()]
        return web.json_response(results, status=200)

    def test_decision_gate_jellyfin_bypass(self):
        gate = LLMDecisionGate(self.logger)
        
        # Test bypass when high confidence and Jellyfin intent present
        context = {"message": "tocar filme Inception"}
        local_resolution = {"high_confidence": True, "resolved": True}
        
        should_call = asyncio.run(gate.should_call_llm(context, local_resolution))
        self.assertFalse(should_call, "LLM should be bypassed for Jellyfin query with high confidence")

    def test_gpu_throttling_params(self):
        config = FakeConfig({
            "llm.ollama.num_gpu": 2,
            "llm.ollama.num_thread": 8,
            "llm.max_concurrent": 1
        })
        manager = LLMManager(None, self.logger, config)
        
        # Verify manager loaded params
        self.assertEqual(manager._num_gpu, 2)
        self.assertEqual(manager._num_thread, 8)
        
        # Verify semaphore is initialized
        self.assertIsInstance(manager._semaphore, asyncio.Semaphore)

    def test_tool_metadata_and_params(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        info = tool.get_info()
        self.assertEqual(info["name"], "jellyfin_tool")
        self.assertEqual(info["capabilities"], ["media_search", "play"])
        self.assertEqual(tool.get_required_params(), ["action"])

    def test_validate_without_api_key(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": ""})
        tool = JellyfinTool(self.logger, config)

        self.assertFalse(tool.validate({"action": "media_search", "query": "Inception"}))
        self.assertIn("Jellyfin API key não configurada", self.logger.errors)

    def test_validate_with_valid_params(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        self.assertTrue(tool.validate({"action": "media_search", "query": "Inception"}))

    async def test_search_movie_success(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        result = await tool.execute({"action": "media_search", "query": "Inception"})
        self.assertTrue(result["success"])
        self.assertEqual(result["query"], "Inception")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["Name"], "Inception")
        self.assertTrue(result["high_confidence"])
        self.assertTrue(result["resolved"])

    async def test_search_movie_unauthorized(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "invalid-api-key"})
        tool = JellyfinTool(self.logger, config)

        result = await tool.execute({"action": "media_search", "query": "Inception"})
        self.assertFalse(result["success"])
        self.assertIn("Erro Jellyfin: 401", result["error"])

    async def test_search_connection_error(self):
        config = FakeConfig({"jellyfin.url": "http://127.0.0.1:59999", "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        result = await tool.execute({"action": "media_search", "query": "Inception"})
        self.assertFalse(result["success"])
        self.assertTrue("error" in result)

    async def test_execute_with_validation(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        result = await tool.execute({"action": "media_search", "query": "Interstellar"})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["Name"], "Interstellar")


if __name__ == "__main__":
    unittest.main()
