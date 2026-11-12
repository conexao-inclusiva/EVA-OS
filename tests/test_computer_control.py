import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.builtin.computer_control_tool import ComputerControlTool
from src.agents.computer_control_agent import ComputerControlAgent
from src.kernel.events import EventBus


class DummyLogger:
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass
    def debug(self, msg): pass


class DummyConfig:
    def get(self, key, default=None):
        return default


class TestComputerControlTool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger = DummyLogger()
        self.config = DummyConfig()
        self.tool = ComputerControlTool(self.logger, self.config)

    def test_tool_info_and_params(self):
        info = self.tool.get_info()
        self.assertEqual(info["name"], "computer_control")
        self.assertIn("capabilities", info)
        self.assertEqual(self.tool.get_required_params(), ["action"])
        self.assertIn("app_name", self.tool.get_optional_params())
        self.assertIn("computer_control", self.tool.get_capabilities())
        self.assertIn("execute", self.tool.get_permissions())

    def test_validate(self):
        valid_actions = [
            "list_apps", "launch_app", "close_app", "app_status",
            "set_volume", "get_volume", "set_brightness", "get_brightness",
            "power_state", "get_env", "set_env", "list_env"
        ]
        for action in valid_actions:
            self.assertTrue(self.tool.validate({"action": action}))

        self.assertFalse(self.tool.validate("not_a_dict"))
        self.assertFalse(self.tool.validate({}))
        self.assertFalse(self.tool.validate({"action": "invalid_action"}))

    async def test_volume_actions(self):
        set_res = await self.tool.execute({"action": "set_volume", "level": 75})
        self.assertTrue(set_res["success"])
        self.assertEqual(set_res["data"]["volume"], 75)

        get_res = await self.tool.execute({"action": "get_volume"})
        self.assertTrue(get_res["success"])
        self.assertEqual(get_res["data"]["volume"], 75)

    async def test_brightness_actions(self):
        set_res = await self.tool.execute({"action": "set_brightness", "level": 85})
        self.assertTrue(set_res["success"])
        self.assertEqual(set_res["data"]["brightness"], 85)

        get_res = await self.tool.execute({"action": "get_brightness"})
        self.assertTrue(get_res["success"])
        self.assertEqual(get_res["data"]["brightness"], 85)

    async def test_power_state_action(self):
        res = await self.tool.execute({"action": "power_state", "state": "lock", "dry_run": True})
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["state"], "lock")
        self.assertTrue(res["data"]["dry_run"])
        self.assertFalse(res["data"]["executed"])

        invalid_res = await self.tool.execute({"action": "power_state", "state": "invalid_state"})
        self.assertTrue(invalid_res["success"])
        self.assertIn("error", invalid_res["data"])

    async def test_env_actions(self):
        var_name = "EVA_TEST_ENV_VAR"
        var_value = "EVA_VALUE_123"

        set_res = await self.tool.execute({"action": "set_env", "env_name": var_name, "env_value": var_value})
        self.assertTrue(set_res["success"])
        self.assertEqual(os.environ.get(var_name), var_value)

        get_res = await self.tool.execute({"action": "get_env", "env_name": var_name})
        self.assertTrue(get_res["success"])
        self.assertTrue(get_res["data"]["exists"])
        self.assertEqual(get_res["data"]["value"], var_value)

        list_res = await self.tool.execute({"action": "list_env"})
        self.assertTrue(list_res["success"])
        self.assertIn(var_name, list_res["data"]["env"])

        if var_name in os.environ:
            del os.environ[var_name]

    async def test_list_and_status_apps(self):
        list_res = await self.tool.execute({"action": "list_apps"})
        self.assertTrue(list_res["success"])
        self.assertIn("running_count", list_res["data"])
        self.assertIn("running_apps", list_res["data"])

        status_res = await self.tool.execute({"action": "app_status", "app_name": "non_existent_process_12345"})
        self.assertTrue(status_res["success"])
        self.assertFalse(status_res["data"]["running"])

    async def test_launch_app_mock(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 99999
            mock_popen.return_value = mock_proc

            res = await self.tool.execute({"action": "launch_app", "app_name": "dummy_app", "args": ["--test"]})
            self.assertTrue(res["success"])
            self.assertTrue(res["data"]["launched"])
            self.assertEqual(res["data"]["pid"], 99999)

    async def test_close_app_mock(self):
        with patch("psutil.process_iter") as mock_proc_iter:
            mock_proc = MagicMock()
            mock_proc.info = {"pid": 88888, "name": "dummy_app.exe"}
            mock_proc_iter.return_value = [mock_proc]

            res = await self.tool.execute({"action": "close_app", "app_name": "dummy_app.exe"})
            self.assertTrue(res["success"])
            self.assertTrue(res["data"]["closed"])
            self.assertIn(88888, res["data"]["closed_pids"])
            mock_proc.terminate.assert_called_once()

    async def test_execute_with_validation_invalid(self):
        res = await self.tool.execute_with_validation({"invalid": "params"})
        self.assertFalse(res["success"])
        self.assertIn("error", res)


class TestComputerControlAgent(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger = DummyLogger()
        self.config = DummyConfig()
        self.event_bus = MagicMock(spec=EventBus)
        self.event_bus.publish_async = AsyncMock()
        self.agent = ComputerControlAgent(self.event_bus, self.logger, self.config)

    async def test_agent_capabilities_and_lifecycle(self):
        self.assertEqual(self.agent.capabilities, ["computer_control", "app_management", "system_config"])

        await self.agent.initialize()
        await self.agent.start()

        health = await self.agent.health_check()
        self.assertEqual(health["tasks_processed"], 0)
        self.assertEqual(health["name"], "computer_control")

        await self.agent.shutdown()

    async def test_process_task_success(self):
        task = {"action": "set_volume", "level": 80, "request_id": "req-100"}
        result = await self.agent.process(task)

        self.assertTrue(result["success"])
        self.assertEqual(result["task"], "set_volume")

        self.event_bus.publish_async.assert_called_once_with(
            "tool.execute",
            {
                "tool": "computer_control",
                "params": task,
                "request_id": "req-100"
            },
            source="computer_control_agent"
        )

        health = await self.agent.health_check()
        self.assertEqual(health["tasks_processed"], 1)

    async def test_process_task_failure(self):
        self.event_bus.publish_async.side_effect = Exception("Bus error")

        task = {"action": "list_apps"}
        result = await self.agent.process(task)

        self.assertFalse(result["success"])
        self.assertIn("Bus error", result["error"])


if __name__ == "__main__":
    unittest.main()
