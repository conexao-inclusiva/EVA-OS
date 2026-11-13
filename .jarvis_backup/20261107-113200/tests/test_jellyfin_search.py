import unittest
import asyncio
from aiohttp import web
from src.tools.builtin.jellyfin_tool import JellyfinTool


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

    def test_tool_metadata_and_params(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        info = tool.get_info()
        self.assertEqual(info["name"], "jellyfin")
        self.assertEqual(info["capabilities"], ["media_search"])
        self.assertEqual(tool.get_required_params(), ["query"])

    def test_validate_without_api_key(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": ""})
        tool = JellyfinTool(self.logger, config)

        self.assertFalse(tool.validate({"query": "Inception"}))
        self.assertIn("Jellyfin API key não configurada", self.logger.errors)

    def test_validate_with_invalid_params(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        self.assertFalse(tool.validate({}))
        self.assertFalse(tool.validate({"query": 123}))

    def test_validate_with_valid_params(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        self.assertTrue(tool.validate({"query": "Inception"}))

    async def test_search_movie_success(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        result = await tool.execute({"query": "Inception"})
        self.assertTrue(result["success"])
        self.assertEqual(result["query"], "Inception")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["Name"], "Inception")

    async def test_search_movie_unauthorized(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "invalid-api-key"})
        tool = JellyfinTool(self.logger, config)

        result = await tool.execute({"query": "Inception"})
        self.assertFalse(result["success"])
        self.assertIn("Erro na API Jellyfin: 401", result["error"])

    async def test_search_connection_error(self):
        config = FakeConfig({"jellyfin.url": "http://127.0.0.1:59999", "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        result = await tool.execute({"query": "Inception"})
        self.assertFalse(result["success"])
        self.assertIn("query", result)
        self.assertTrue("error" in result)

    async def test_execute_with_validation(self):
        config = FakeConfig({"jellyfin.url": self.server_url, "jellyfin.api_key": "valid-api-key"})
        tool = JellyfinTool(self.logger, config)

        result = await tool.execute_with_validation({"query": "Interstellar"})
        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "jellyfin")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["Name"], "Interstellar")


if __name__ == "__main__":
    unittest.main()
