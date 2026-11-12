"""Politica experimental de execucao de ferramentas da EVA-OS.

Esta politica nao esta integrada ao ToolManager.
Operacoes privilegiadas permanecem bloqueadas ate haver
autenticacao confiavel vinculada ao canal de execucao.
"""


from dataclasses import dataclass


@dataclass(frozen=True)
class ToolAccessDecision:
    allowed: bool
    reason: str


class ToolExecutionPolicy:
    """Controle explicito de ferramentas com negacao por padrao."""

    _PUBLIC_ACTIONS = frozenset({
        "now",
        "format",
        "add",
        "diff",
        "parse",
    })

    _RESTRICTED_TOOLS = frozenset({
        "system",
        "network",
        "file",
        "python",
        "shell",
    })

    def authorize(self, tool_name, params=None, context=None):
        """
        Avalia somente a politica experimental.

        Nunca utiliza papeis declarados no contexto para
        conceder privilegios administrativos.
        """

        if not isinstance(tool_name, str):
            return ToolAccessDecision(
                False,
                "invalid_tool",
            )

        if not isinstance(params, dict):
            return ToolAccessDecision(
                False,
                "invalid_params",
            )

        if tool_name == "date":
            action = params.get("action")

            if (
                isinstance(action, str)
                and action in self._PUBLIC_ACTIONS
            ):
                return ToolAccessDecision(
                    True,
                    "public_date_operation",
                )

            return ToolAccessDecision(
                False,
                "invalid_date_action",
            )

        if tool_name in self._RESTRICTED_TOOLS:
            return ToolAccessDecision(
                False,
                "privileged_tool_not_enabled",
            )

        return ToolAccessDecision(
            False,
            "unknown_tool",
        )
