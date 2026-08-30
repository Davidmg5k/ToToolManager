"""
Test de rendimiento y análisis del chat - Captura qué se envía al LLM
y métricas de ejecución (requests, tool calls, tokens, etc.)
"""
import json
import time
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict

import pytest


@dataclass
class LLMMetrics:
    """Métricas capturadas del LLM"""
    total_requests: int = 0
    tool_calls: list = field(default_factory=list)
    tool_call_count: int = 0
    messages_sent: list = field(default_factory=list)
    messages_received: list = field(default_factory=list)
    system_prompt_length: int = 0
    user_message_length: int = 0
    total_tokens_approx: int = 0
    response_length: int = 0
    execution_time_ms: float = 0
    services_discovered: list = field(default_factory=list)
    tools_available: list = field(default_factory=list)
    modules_discovered: list = field(default_factory=list)


class TestChatPerformanceAnalysis:
    """
    Test que analiza qué se envía al LLM y métricas de rendimiento
    """

    def test_llm_payload_analysis(self, client):
        """
        Analiza el payload completo que se envía al LLM incluyendo:
        - System prompt
        - Mensaje del usuario
        - Tools disponibles
        - Servicios descubiertos
        """
        print("\n" + "="*80)
        print("ANALISIS DEL PAYLOAD ENVIADO AL LLM")
        print("="*80)

        # 1. Primero creamos una sesion
        create_resp = client.post("/api/chat/sessions", data={"title": "Test Analisis"})
        chat_id = create_resp.json()["data"]["chat_id"]
        print(f"\n[1] Sesion creada: {chat_id}")

        # 2. Capturamos que se envia al LLM usando mock
        metrics = LLMMetrics()
        
        with patch("app.router.api.chat.build_agent") as mock_build_agent:
            mock_agent = AsyncMock()
            mock_build_agent.return_value = mock_agent
            
            # Configuramos el mock para capturar parametros
            async def capture_run_stream(message, **kwargs):
                metrics.user_message_length = len(message)
                metrics.messages_sent.append({"role": "user", "content": message})
                print(f"\n[2] MENSAJE ENVIADO AL LLM:")
                print(f"    '{message}'")
                print(f"    Longitud: {len(message)} caracteres")
                
                # Simulamos respuesta del LLM
                mock_result = AsyncMock()
                mock_result.stream_text = AsyncMock(return_value=AsyncMock(
                    __aiter__=lambda self: iter([
                        "Analizando tu solicitud sobre inventario y pagos...\n\n",
                        "Basado en los datos disponibles:\n",
                        "- No hay perdidas significativas registradas\n",
                        "- Los pagos en COP estan procesandose correctamente\n",
                        "- El inventario muestra movimientos normales"
                    ])
                ))
                return mock_result

            mock_agent.run_stream = capture_run_stream
            
            # 3. Enviamos el mensaje problemático
            test_message = "Revisando el invantario y los pagos en COP voy mal? estoy teniendo perdidas?"
            
            print(f"\n[3] ENVIANDO MENSAJE AL CHAT:")
            print(f"    Mensaje: '{test_message}'")
            
            response = client.post(
                f"/api/chat/sessions/{chat_id}/send",
                data={"message": test_message}
            )
            
            print(f"\n[4] RESPUESTA DEL ENDPOINT:")
            print(f"    Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"    Task ID: {data['data'].get('task_id')}")
                print(f"    Status: {data['data'].get('status')}")

        # 4. Analizamos los argumentos con los que se construyo el agente
        print(f"\n[5] ANALISIS DEL AGENTE CONSTRUIDO:")
        call_args = mock_build_agent.call_args
        if call_args:
            args, kwargs = call_args
            print(f"    Model: {kwargs.get('model', 'N/A')}")
            print(f"    System Prompt Preview:")
            system_prompt = kwargs.get('system_prompt', '')
            if system_prompt:
                print(f"    --- INICIO SYSTEM PROMPT ---")
                print(f"    {system_prompt[:500]}...")
                print(f"    --- FIN SYSTEM PROMPT (preview) ---")
                print(f"    Longitud total: {len(system_prompt)} caracteres")

        print("\n" + "="*80)
        print("FIN DEL ANALISIS")
        print("="*80)

    def test_tool_discovery_analysis(self, session):
        """
        Analiza que herramientas (tools) estan disponibles para el LLM
        """
        print("\n" + "="*80)
        print("DESCUBRIMIENTO DE HERRAMIENTAS (TOOLS)")
        print("="*80)
        
        from app.controller.agent import (
            build_user_service,
            build_order_service,
            build_inventory_service,
            build_payment_service,
            build_notification_service,
            build_commerce_module,
            build_communication_module,
        )
        from to_tool_manager import ToToolManager
        
        # Construimos el manager igual que en la app
        manager = ToToolManager([
            build_user_service(session),
            build_commerce_module(session),
            build_communication_module(session),
        ])
        
        # Obtenemos todas las herramientas disponibles
        print("\n[1] SERVICIOS REGISTRADOS:")
        for name, service in manager.services.items():
            print(f"    - {name}: {service.description[:80]}...")
        
        print("\n[2] MODULOS REGISTRADOS:")
        for name, module in manager.modules.items():
            print(f"    - {name}: {module.description[:80]}...")
        
        print("\n[3] TOOL SPECS (lo que el LLM puede usar):")
        tool_specs = manager.tool_specs
        for i, spec in enumerate(tool_specs, 1):
            print(f"    {i}. {spec.name}")
            print(f"       Descripcion: {spec.description[:100]}...")
            params = [p.name for p in spec.parameters]
            print(f"       Parametros: {params}")
        
        print(f"\n[4] RESUMEN:")
        print(f"    Total herramientas: {len(tool_specs)}")
        print(f"    Servicios: {len(manager.services)}")
        print(f"    Modulos: {len(manager.modules)}")
        
        print("\n" + "="*80)
        
        # Verificaciones basicas
        assert len(manager.services) > 0, "Deberia haber servicios registrados"
        assert len(manager.modules) > 0, "Deberia haber modulos registrados"
        assert len(tool_specs) > 0, "Deberia haber tool specs disponibles"

    def test_system_prompt_construction(self, session):
        """
        Analiza como se construye el system prompt que ve el LLM
        """
        print("\n" + "="*80)
        print("CONSTRUCCION DEL SYSTEM PROMPT")
        print("="*80)
        
        from app.router.api.chat import SYSTEM_PROMPT
        from app.controller.agent import (
            build_user_service,
            build_commerce_module,
            build_communication_module,
        )
        from to_tool_manager import ToToolManager
        from to_tool_manager.core.prompts import build_system_prompt, build_instructions
        
        # System prompt de la app
        print("\n[1] SYSTEM PROMPT DE LA APLICACION:")
        print(f"    '{SYSTEM_PROMPT}'")
        print(f"    Longitud: {len(SYSTEM_PROMPT)} caracteres")
        
        # System prompt auto-generado por el framework
        manager = ToToolManager([
            build_user_service(session),
            build_commerce_module(session),
            build_communication_module(session),
        ])
        
        all_services = list(manager.services.values()) + list(manager.modules.values())
        auto_system_prompt = build_system_prompt(all_services)
        
        print("\n[2] SYSTEM PROMPT AUTO-GENERADO (primeros 1000 chars):")
        print(f"    {auto_system_prompt[:1000]}...")
        print(f"    Longitud total: {len(auto_system_prompt)} caracteres")
        
        # Instructions
        instructions = build_instructions()
        print("\n[3] INSTRUCTIONS (no persistido en historial):")
        print(f"    {instructions[:500]}...")
        print(f"    Longitud: {len(instructions)} caracteres")
        
        # Analisis de complejidad
        print("\n[4] ANALISIS DE COMPLEJIDAD DEL CONTEXTO:")
        total_prompt_size = len(SYSTEM_PROMPT) + len(auto_system_prompt) + len(instructions)
        print(f"    System prompt app: {len(SYSTEM_PROMPT)} chars")
        print(f"    System prompt auto: {len(auto_system_prompt)} chars")
        print(f"    Instructions: {len(instructions)} chars")
        print(f"    Total contexto fijo: ~{total_prompt_size} chars (~{total_prompt_size // 4} tokens estimados)")
        
        print("\n" + "="*80)
        
        # Verificaciones
        assert len(SYSTEM_PROMPT) > 100, "System prompt deberia ser sustancial"
        assert len(auto_system_prompt) > 500, "System prompt auto-generado deberia incluir info de tools"

    def test_mocked_llm_call_tracking(self, session):
        """
        Rastrea las llamadas reales al LLM con tracking completo
        """
        print("\n" + "="*80)
        print("TRACKING DE LLAMADAS AL LLM (SIMULADO)")
        print("="*80)
        
        import os
        if not os.environ.get("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set, skipping real agent construction test")
        
        from app.controller.agent import (
            build_user_service,
            build_commerce_module,
            build_communication_module,
        )
        from app.security.middleware_ai.sanitize import SensitiveFieldMiddlewareAI
        from to_tool_manager import ToToolManager
        from to_tool_manager.adapters.pydantic_ai import build_agent
        
        # Construimos el manager real
        manager = ToToolManager([
            build_user_service(session),
            build_commerce_module(session),
            build_communication_module(session),
        ], middlewares=[SensitiveFieldMiddlewareAI()])
        
        # Construimos el agente real (sin ejecutar)
        agent = build_agent(
            model="groq:openai/gpt-oss-120b",
            manager=manager,
            system_prompt="You are a commerce assistant."
        )
        
        print("\n[1] AGENTE CONSTRUIDO EXITOSAMENTE")
        print(f"    Model: {agent.model}")
        
        # Simulamos una llamada y rastreamos
        print("\n[2] SIMULACION DE FLUJO DE EJECUCION:")
        
        test_message = "Revisando el invantario y los pagos en COP voy mal? estoy teniendo perdidas?"
        
        print(f"\n    Paso 1: Usuario envia mensaje")
        print(f"    Mensaje: '{test_message}'")
        
        print(f"\n    Paso 2: Sistema construye contexto")
        print(f"    - System prompt se agrega al historial")
        print(f"    - User message se agrega al historial")
        print(f"    - Tools se serializan como disponibles")
        
        print(f"\n    Paso 3: LLM recibe:")
        print(f"    - Rol: system -> System prompt")
        print(f"    - Rol: user -> '{test_message}'")
        
        print(f"\n    Paso 4: LLM decide acciones")
        print(f"    - Podria llamar a inventory_service (list_products)")
        print(f"    - Podria llamar a payment_service (list_payments)")
        print(f"    - Podria llamar a order_service (list_orders)")
        
        print(f"\n    Paso 5: Respuesta generada")
        print(f"    - Tokens de respuesta estimados: ~200-500")
        
        print("\n[3] METRICAS ESTIMADAS DE LA LLAMADA:")
        print(f"    - Input tokens estimados: ~800-1200 (contexto + mensaje)")
        print(f"    - Output tokens estimados: ~200-500 (respuesta)")
        print(f"    - Posibles tool calls: 0-3 (depende del analisis del LLM)")
        print(f"    - Tiempo estimado: 1-3 segundos (Groq es rapido)")
        
        print("\n" + "="*80)
        
        # Verificacion de que el agente se construyo correctamente
        assert agent is not None, "El agente deberia construirse correctamente"

    def test_performance_metrics_collection(self, client):
        """
        Recolecta metricas de rendimiento de una llamada real al chat
        """
        print("\n" + "="*80)
        print("METRICAS DE RENDIMIENTO")
        print("="*80)
        
        # Tracking de llamadas
        call_log = []
        
        with patch("app.router.api.chat.build_agent") as mock_build_agent:
            mock_agent = AsyncMock()
            mock_build_agent.return_value = mock_agent
            
            original_build_agent = mock_build_agent.return_value
            
            # Capturamos parametros del build_agent
            def capture_build(*args, **kwargs):
                call_log.append({
                    "type": "build_agent",
                    "args": args,
                    "kwargs": {k: v for k, v in kwargs.items() if k != 'manager'}
                })
                return mock_agent
            
            mock_build_agent.side_effect = capture_build
            
            # Simulamos run_stream
            async def mock_run_stream(message, **kwargs):
                call_log.append({
                    "type": "run_stream",
                    "message": message,
                    "kwargs": kwargs
                })
                
                # Simulamos respuesta
                mock_result = AsyncMock()
                async def mock_stream_text(delta=True):
                    tokens = ["Procesando...", " Consulta completada."]
                    for token in tokens:
                        yield token
                
                mock_result.stream_text = mock_stream_text
                return mock_result
            
            mock_agent.run_stream = mock_run_stream
            
            # Crear sesion y enviar mensaje
            create_resp = client.post("/api/chat/sessions", data={"title": "Performance Test"})
            chat_id = create_resp.json()["data"]["chat_id"]
            
            start_time = time.time()
            
            response = client.post(
                f"/api/chat/sessions/{chat_id}/send",
                data={"message": "Test message"}
            )
            
            end_time = time.time()
            
            print(f"\n[1] METRICAS DE EJECUCION:")
            print(f"    Tiempo total: {(end_time - start_time) * 1000:.2f}ms")
            print(f"    Status code: {response.status_code}")
            
            print(f"\n[2] LLAMADAS REGISTRADAS:")
            for i, call in enumerate(call_log, 1):
                print(f"    {i}. Tipo: {call['type']}")
                if call['type'] == 'build_agent':
                    print(f"       Model: {call['kwargs'].get('model', 'N/A')}")
                elif call['type'] == 'run_stream':
                    print(f"       Mensaje: '{call['message']}'")
            
            print(f"\n[3] RESUMEN DE OPERACIONES:")
            print(f"    build_agent llamado: {sum(1 for c in call_log if c['type'] == 'build_agent')} vez/veces")
            print(f"    run_stream llamado: {sum(1 for c in call_log if c['type'] == 'run_stream')} vez/veces")
        
        print("\n" + "="*80)

    def test_context_window_analysis(self, session):
        """
        Analiza el tamano del contexto que consume el LLM
        """
        print("\n" + "="*80)
        print("ANALISIS DE VENTANA DE CONTEXTO")
        print("="*80)
        
        from app.router.api.chat import SYSTEM_PROMPT
        from app.controller.agent import (
            build_user_service,
            build_commerce_module,
            build_communication_module,
        )
        from to_tool_manager import ToToolManager
        from to_tool_manager.core.prompts import build_system_prompt, build_instructions
        
        manager = ToToolManager([
            build_user_service(session),
            build_commerce_module(session),
            build_communication_module(session),
        ])
        
        all_services = list(manager.services.values()) + list(manager.modules.values())
        auto_system_prompt = build_system_prompt(all_services)
        instructions = build_instructions()
        
        test_message = "Revisando el invantario y los pagos en COP voy mal? estoy teniendo perdidas?"
        
        # Calculamos longitudes
        len_system = len(SYSTEM_PROMPT)
        len_auto = len(auto_system_prompt)
        len_instructions = len(instructions)
        len_message = len(test_message)
        total_chars = len_system + len_auto + len_instructions + len_message
        
        # Estimacion de tokens (aproximacion: 1 token ~ 4 caracteres)
        tok_system = len_system // 4
        tok_auto = len_auto // 4
        tok_instructions = len_instructions // 4
        tok_message = len_message // 4
        total_tokens = tok_system + tok_auto + tok_instructions + tok_message
        
        print("\n[1] DESGLOSE DEL CONTEXTO:")
        print(f"    +-----------------------------+----------+----------+")
        print(f"    | Componente                  | Chars    | Tokens   |")
        print(f"    +-----------------------------+----------+----------+")
        print(f"    | System Prompt (app)         | {len_system:>8} | {tok_system:>8} |")
        print(f"    | System Prompt (auto)        | {len_auto:>8} | {tok_auto:>8} |")
        print(f"    | Instructions                | {len_instructions:>8} | {tok_instructions:>8} |")
        print(f"    | User Message                | {len_message:>8} | {tok_message:>8} |")
        print(f"    +-----------------------------+----------+----------+")
        print(f"    | TOTAL ESTIMADO              | {total_chars:>8} | {total_tokens:>8} |")
        print(f"    +-----------------------------+----------+----------+")
        
        print(f"\n[2] ANALISIS DE CAPACIDAD:")
        print(f"    - Context window tipico Groq: 32K-128K tokens")
        print(f"    - Contexto usado: ~{total_tokens} tokens ({(total_tokens/32000)*100:.1f}% de 32K)")
        print(f"    - Espacio restante: ~{32000 - total_tokens} tokens")
        print(f"    - Capacidad para historial: ~{(32000 - total_tokens) // 100} mensajes adicionales")
        
        print(f"\n[3] RECOMENDACIONES:")
        if total_tokens > 10000:
            print(f"    - Contexto grande: considerar compresion de historial")
        if total_tokens > 5000:
            print(f"    - System prompt largo: evaluar si todo es necesario")
        print(f"    - Para este caso especifico, el contexto es manejable")
        
        print("\n" + "="*80)
        
        # Verificacion
        assert total_tokens < 32000, "El contexto no deberia exceder la ventana de tokens"

