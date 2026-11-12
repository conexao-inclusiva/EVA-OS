import unittest
import asyncio
from unittest.mock import AsyncMock, patch
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


class TestJellyfinPlayback(unittest.IsolatedAsyncioTestCase):
    """
    Testes unitários para a funcionalidade de reprodução (playback) do JellyfinTool.
    Verifica a integração com servidor mock e execução de comandos locais.
    """

    async def asyncSetUp(self):
        self.logger = FakeLogger()

        # Configuração do servidor local mock para API Jellyfin
        self.app = web.Application()
        self.app.router.add_get("/Search/Hints", self._handle_search)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()

        host, port = self.site._server.sockets[0].getsockname()[:2]
        self.server_url = f"http://{host}:{port}"

        self.config = FakeConfig({
            "jellyfin.url": self.server_url,
            "jellyfin.api_key": "token-autenticado"
        })
        self.tool = JellyfinTool(self.logger, self.config)

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def _handle_search(self, request):
        """Handler mock para busca de itens."""
        return web.json_response([
            {"Name": "The Matrix", "Type": "Movie", "Id": "m123_matrix"}
        ])

    def test_playback_capabilities_registration(self):
        """Verifica se as capacidades de playback estão registradas no metadado."""
        info = self.tool.get_info()
        self.assertIn("play", info["capabilities"])
        self.assertIn("media_search", info["capabilities"])

    def test_validate_playback_params(self):
        """Valida a lógica de validação para a ação 'play'."""
        # Válido
        self.assertTrue(self.tool.validate({"action": "play", "item_id": "m123"}))
        # Inválido: ID faltando
        self.assertFalse(self.tool.validate({"action": "play"}))
        # Inválido: Tipo incorreto de ID
        self.assertFalse(self.tool.validate({"action": "play", "item_id": 123}))
        # Inválido: Ação desconhecida
        self.assertFalse(self.tool.validate({"action": "pause", "item_id": "m123"}))

    @patch("asyncio.create_subprocess_exec")
    async def test_play_execution_flow(self, mock_exec):
        """Verifica o fluxo de execução da ação 'play' disparando comando xdg-open."""
        # Mock do processo assíncrono
        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_process

        item_id = "m123_matrix"
        params = {"action": "play", "item_id": item_id}
        
        result = await self.tool.execute(params)

        self.assertTrue(result["success"])
        self.assertEqual(result["item_id"], item_id)
        
        # Verifica se o comando correto foi montado para o player local
        expected_url = f"{self.server_url}/web/index.html#!/details?id={item_id}"
        mock_exec.assert_called_once_with("xdg-open", expected_url)
        self.assertIn(f"Comando de reprodução enviado para: {item_id}", self.logger.infos)

    async def test_search_and_play_integration(self):
        """Testa o fluxo completo: pesquisa e depois reprodução do ID encontrado."""
        # 1. Pesquisa
        search_params = {"action": "media_search", "query": "Matrix"}
        search_result = await self.tool.execute(search_params)
        
        self.assertTrue(search_result["success"])
        self.assertEqual(search_result["count"], 1)
        found_id = search_result["results"][0]["Id"]
        self.assertEqual(found_id, "m123_matrix")

        # 2. Reprodução com ID da pesquisa
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = AsyncMock()
            mock_process.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_process
            
            play_params = {"action": "play", "item_id": found_id}
            play_result = await self.tool.execute(play_params)
            
            self.assertTrue(play_result["success"])
            self.assertEqual(play_result["item_id"], "m123_matrix")

    @patch("asyncio.create_subprocess_exec")
    async def test_play_error_handling(self, mock_exec):
        """Verifica tratamento de erro quando o comando de sistema falha."""
        mock_exec.side_effect = Exception("System player not found")

        item_id = "fail_id"
        result = await self.tool.execute({"action": "play", "item_id": item_id})

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "System player not found")
        self.assertIn(f"Erro ao reproduzir {item_id}: System player not found", self.logger.errors)

    def test_validate_without_config(self):
        """Verifica se a ferramenta nega execução sem API key configurada."""
        bad_tool = JellyfinTool(self.logger, FakeConfig({}))
        self.assertFalse(bad_tool.validate({"action": "play", "item_id": "1"}))
        self.assertIn("Jellyfin API key não configurada", self.logger.errors)


if __name__ == "__main__":
    unittest.main()
