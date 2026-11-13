#!/usr/bin/env python3
"""EVA OS - Ponto de entrada principal."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asyncio
import signal
from pathlib import Path
import threading
import time
import socket

sys.path.insert(0, str(Path(__file__).parent))

from src.kernel import Boot


def check_ollama():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 11434))
        sock.close()
        return result == 0
    except:
        return False


class EVAOS:
    def __init__(self):
        self.boot = Boot()
        self._shutdown_requested = False
        self._shutdown_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._llm = None
        self._brain = None
        self._web_server = None
        self._console_thread = None
        self._loop = None
        self.logger = None
        
        # Referências para serviços (para shutdown)
        self._memory_manager = None
        self._long_term_memory = None
        self._lifecycle_manager = None   # ← NOVO
    
    def _run_console(self) -> None:
        """Inicia o console interativo (cmd) em uma thread separada.

        A thread só bloqueia em input(); publicação de eventos usa o loop principal.
        """
        try:
            from src.interfaces.cli.console import EVAConsole
            
            core = self.boot.core
            if not core:
                print("❌ Core não inicializado")
                return
            
            if not self._loop:
                print("❌ Event loop principal não disponível para o console")
                return
            
            console = EVAConsole(
                core.event_bus, 
                core.logger, 
                core.config,
                loop=self._loop,
                shutdown_event=self._shutdown_event,
                lifecycle_manager=self._lifecycle_manager,
                brain=self._brain,
            )
            
            try:
                console.cmdloop()
            except KeyboardInterrupt:
                pass
            
        except Exception as e:
            print(f"❌ Erro no console: {e}")
            import traceback
            traceback.print_exc()
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._shutdown_event.set)
            else:
                self._shutdown_event.set()
    
    async def run(self) -> None:
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("\n🔍 Verificando Ollama...")
        if check_ollama():
            print("✅ Ollama está rodando!")
        else:
            print("⚠️ Ollama não detectado.")
        
        success = await self.boot.boot()
        
        if not success:
            print("❌ Falha no boot. Encerrando.")
            sys.exit(1)
        
        core = self.boot.core
        self.logger = core.logger
        registry = core.service_registry
        event_bus = core.event_bus
        logger = core.logger
        config = core.config
        self._loop = asyncio.get_running_loop()

        # ============================================================
        # Obtém o LifecycleManager do core (já deve existir)
        # ============================================================
        self._lifecycle_manager = getattr(core, 'lifecycle_manager', None)
        if not self._lifecycle_manager:
            self.logger.warning("LifecycleManager não encontrado no core; shutdown será manual.")
        
        # ============================================================
        # 1. LLM
        # ============================================================
        print("🧠 Iniciando LLM...")
        try:
            from src.llm.llm_manager import LLMManager
            self._llm = LLMManager(event_bus, logger, config)
            await self._llm.initialize()
            registry.register("llm_manager", self._llm)
            print("✅ LLM iniciado")
        except Exception as e:
            print(f"❌ Erro ao iniciar LLM: {e}")
            import traceback
            traceback.print_exc()
        
        # ============================================================
        # 2. BRAIN
        # ============================================================
        print("🧠 Iniciando Brain...")
        try:
            from src.consciousness.brain import Brain
            self._brain = Brain(event_bus, logger, config, service_registry=registry)
            self._brain._llm_manager = self._llm
            await self._brain.initialize()
            registry.register("brain", self._brain)

            # EVA_ETAPA_33_3_VINCULACAO_POS_BRAIN
            # Vincula somente agentes ja iniciados pelo AgentManager.
            # Nao cria novas instancias nem reinicia os plugins existentes.
            plugin_manager = core.plugin_manager
            owner = registry.get("agent_manager")
            for plugin_name in (
                "knowledge_agent",
                "memory_agent",
                "planner_agent",
            ):
                plugin_id = plugin_manager._plugins_by_name.get(plugin_name)
                plugin = plugin_manager._plugins.get(plugin_id)

                if plugin is None or owner is None:
                    logger.warning(
                        "VINCULACAO_33_3_INDISPONIVEL: " + plugin_name
                    )
                    continue

                success = await plugin_manager._load_plugin(plugin)
                expected = owner.get_agent(
                    plugin_name.removesuffix("_agent")
                )
                same_instance = (
                    expected is not None
                    and registry.get(plugin_name) is expected
                    and plugin.instance is expected
                )

                if success and same_instance:
                    logger.info(
                        "VINCULACAO_33_3_OK: " + plugin_name
                    )
                else:
                    logger.error(
                        "VINCULACAO_33_3_FALHOU: "
                        + plugin_name
                        + " - "
                        + str(plugin.error)
                    )
            self._memory_manager = self._brain._modules.get("memory_manager")
            self._long_term_memory = self._brain._modules.get("long_term_memory")
            # EVA_ETAPA_34_3_CONVERSAS_COMPARTILHADAS
            # Reutiliza exclusivamente as instancias criadas pelo Brain.
            try:
                from pathlib import Path as _ConversationPath
                from datetime import datetime as _ConversationDateTime
                from src.core.plugin_manager import PluginStatus as _ConversationStatus

                _coordinator = getattr(
                    self._brain, "conversation_coordinator", None
                )
                if _coordinator is None:
                    raise RuntimeError("Coordenador do Brain indisponivel")

                _components = (
                    ("conversation_coordinator", _coordinator),
                    ("conversation_archive", _coordinator.archive),
                    ("turn_state_manager", _coordinator.states),
                )

                _expected_db = _ConversationPath(
                    _coordinator.db_path
                ).resolve()
                _validated = []

                # Valida todos antes de registrar qualquer componente.
                for _name, _instance in _components:
                    _plugin = core.plugin_manager.get_plugin(_name)
                    if _plugin is None and _instance is not None:
                        _instance_type = type(_instance)
                        _plugin = next(
                            (
                                _candidate
                                for _candidate in core.plugin_manager._plugins.values()
                                if _candidate.manifest.main_class == _instance_type.__name__
                                and _candidate.module is not None
                                and getattr(
                                    _candidate.module,
                                    _candidate.manifest.main_class,
                                    None,
                                ) is _instance_type
                            ),
                            None,
                        )
                    if _plugin is None or _instance is None:
                        raise RuntimeError("Plugin ou instancia ausente: " + _name)

                    _class = getattr(
                        _plugin.module,
                        _plugin.manifest.main_class,
                        None,
                    )
                    if not isinstance(_class, type):
                        raise RuntimeError("Classe nao encontrada: " + _name)

                    if not isinstance(_instance, _class):
                        raise RuntimeError("Classe divergente: " + _name)

                    if _ConversationPath(_instance.db_path).resolve() != _expected_db:
                        raise RuntimeError("Banco divergente: " + _name)

                    for _dependency in _plugin.manifest.requires:
                        if core.plugin_manager._resolve_service(_dependency) is None:
                            raise RuntimeError(
                                "Dependencia indisponivel: "
                                + _name + "/" + _dependency
                            )

                    if _plugin.instance is not None and _plugin.instance is not _instance:
                        raise RuntimeError("Outra instancia no plugin: " + _name)

                    _existing = registry.get(_name)
                    if _existing is not None and _existing is not _instance:
                        raise RuntimeError("Outra instancia no registro: " + _name)

                    _validated.append((_name, _instance, _plugin))

                for _name, _instance, _plugin in _validated:
                    if registry.get(_name) is None:
                        registry.register(
                            _name, _instance, _plugin.manifest.requires
                        )

                    _plugin.instance = _instance
                    _plugin.status = _ConversationStatus.STARTED
                    _plugin.error = None

                    if _plugin.loaded_at is None:
                        _plugin.loaded_at = _ConversationDateTime.now()
                    if _plugin.initialized_at is None:
                        _plugin.initialized_at = _ConversationDateTime.now()

                    _plugin.started_at = _ConversationDateTime.now()

                    # O Brain continua responsavel pelo ciclo de vida.
                    core.plugin_manager._delegated_plugins[
                        _plugin.manifest.id
                    ] = self._brain

                    logger.info("VINCULACAO_34_3_OK: " + _name)

            except Exception:
                logger.exception("VINCULACAO_34_3_FALHOU")
            print("✅ Brain iniciado")
        except Exception as e:
            print(f"❌ Erro ao iniciar brain: {e}")
            import traceback
            traceback.print_exc()
        
        # ============================================================
        # 3. WEB SERVER
        # ============================================================
        print("🌐 Iniciando Web Server...")
        try:
            from src.interfaces.web.web_server import WebServer
            self._web_server = WebServer(event_bus, logger, config)
            await self._web_server.initialize()
            await self._web_server.start()
            registry.register("web_server", self._web_server)
            print("✅ Web Server iniciado")
        except Exception as e:
            print(f"❌ Erro ao iniciar Web Server: {e}")
            import traceback
            traceback.print_exc()
        
        # ============================================================
        # 4. CONSOLE (cmd) - em thread separada
        # ============================================================
        print("💬 Iniciando Console...")
        try:
            self._console_thread = threading.Thread(target=self._run_console, daemon=False)
            self._console_thread.start()
            time.sleep(1)
            print("✅ Console iniciado")
        except Exception as e:
            print(f"❌ Erro ao iniciar Console: {e}")
            self._shutdown_event.set()
        
        print("\n" + "=" * 60)
        print("🚀 EVA OS PRONTA!")
        print("   💬 Console: digite qualquer coisa para conversar")
        print("   🌐 Web: http://localhost:8000")
        print("   🎤 Fale com a EVA usando o microfone")
        print("=" * 60 + "\n")
        # ========== ALTERADO: mensagem de encerramento ==========
        print("💡 Digite 'eva encerrar sistema' para encerrar\n")
        # =======================================================
        
        # ============================================================
        # 5. LOOP PRINCIPAL – AGUARDA EVENTO DE SHUTDOWN
        # ============================================================
        try:
            await self._shutdown_event.wait()
            if self.logger:
                self.logger.info("📴 Evento de shutdown detectado")
            else:
                print("📴 Evento de shutdown detectado")
        except asyncio.CancelledError:
            if self.logger:
                self.logger.info("📴 Loop principal cancelado")
            else:
                print("📴 Loop principal cancelado")
        finally:
            await self.shutdown()
    
    def _signal_handler(self, signum, frame) -> None:
        print(f"\n📴 Desligando (sinal)...")
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._shutdown_event.set)
        else:
            self._shutdown_event.set()
    
    async def shutdown(self) -> None:
        """Desliga a EVA de forma segura e idempotente."""
        async with self._shutdown_lock:
            if self._shutdown_requested:
                return
            self._shutdown_requested = True
            self._shutdown_event.set()
            
            if self.logger:
                self.logger.info("=" * 50)
                self.logger.info("EVA OS - Desligando...")
                self.logger.info("=" * 50)
            else:
                print("=" * 50)
                print("EVA OS - Desligando...")
                print("=" * 50)
            
            # ----------------------------------------------------------
            # 1. Brain primeiro (desliga módulos vivos, inclusive MemoryManager)
            # ----------------------------------------------------------
            if self._brain:
                try:
                    await self._brain.shutdown()
                    print("✅ Brain desligado")
                except Exception as e:
                    print(f"❌ Erro ao desligar Brain: {e}")
                    if self.logger:
                        self.logger.error(f"Erro ao desligar Brain: {e}")
            
            # ----------------------------------------------------------
            # 2. Persistência extra da mesma instância registrada no Core
            # ----------------------------------------------------------
            try:
                registry = self.boot.core.service_registry if self.boot.core else None
                memory_manager = None
                if registry:
                    memory_manager = registry.get("memory_manager")
                if memory_manager is None:
                    memory_manager = self._memory_manager
                if memory_manager and hasattr(memory_manager, "_save_memories"):
                    await memory_manager._save_memories()
                    print("✅ Memória salva (MemoryManager)")
                    if self.logger:
                        self.logger.info("Memória salva (MemoryManager)")
                # LongTermMemory
                long_term = registry.get("long_term_memory") if registry else self._long_term_memory
                if long_term and hasattr(long_term, "_save"):
                    await long_term._save()
                    print("✅ Memória de longo prazo salva")
                # KnowledgeManager
                knowledge = registry.get("knowledge_manager") if registry else None
                if knowledge and hasattr(knowledge, "_save_knowledge"):
                    await knowledge._save_knowledge()
                    print("✅ Conhecimento salvo")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Erro ao salvar memória: {e}")
                else:
                    print(f"Erro ao salvar memória: {e}")
            
            # ----------------------------------------------------------
            # 3. Demais componentes
            # ----------------------------------------------------------
            if self._web_server:
                try:
                    await self._web_server.shutdown()
                    print("✅ Web Server desligado")
                except Exception as e:
                    print(f"❌ Erro ao desligar Web Server: {e}")
            
            if self._lifecycle_manager:
                try:
                    await self._lifecycle_manager.stop_all()
                    print("✅ LifecycleManager.stop_all concluído")
                except Exception as e:
                    print(f"❌ Erro ao parar módulos via LifecycleManager: {e}")
            
            # ----------------------------------------------------------
            # Desliga o Boot (core, plugins, health, eventbus)
            # ----------------------------------------------------------
            try:
                await self.boot.shutdown()
                print("✅ Boot desligado")
            except Exception as e:
                print(f"❌ Erro ao desligar Boot: {e}")
            
            # ----------------------------------------------------------
            # Aguarda a thread do console terminar
            # ----------------------------------------------------------
            if self._console_thread and self._console_thread.is_alive():
                try:
                    self._console_thread.join(timeout=2)
                    if self._console_thread.is_alive():
                        if self.logger:
                            self.logger.warning("Thread do console não terminou a tempo")
                        else:
                            print("⚠️ Thread do console não terminou a tempo")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Erro ao aguardar console: {e}")
            
            if self.logger:
                self.logger.info("✅ EVA OS desligado com sucesso")
            print("✅ EVA OS desligado com sucesso")
            print("=" * 50)


async def main():
    eva = EVAOS()
    await eva.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n📴 EVA OS interrompido.")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)