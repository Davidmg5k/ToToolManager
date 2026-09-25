"""
Test de rendimiento y análisis del chat - Captura qué se envía al LLM
y métricas de ejecución (requests, tool calls, tokens, etc.)

API actual de to_tool_manager (referencia REQ-001..REQ-007):
- TTMBuilder: add_service / add_module / add_middleware / build()
- Service.instructions: instrucciones por servicio (no existe build_system_prompt)
- Service.build_as_capability(): expone los tools que verá el LLM
- El endpoint /send delega en chat_task_manager.start(...) (patrón Task Queue)
"""
import time
from unittest.mock import patch, AsyncMock
from dataclasses import dataclass, field

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


def _build_builder(session):
    """Construye el TTMBuilder igual que en la app (REQ-004)."""
    from app.controller.agent import (
        build_user_service,
        build_commerce_module,
        build_communication_module,
    )
    from app.router.api.chat import SYSTEM_PROMPT

    builder = __import__("to_tool_manager").TTMBuilder(
        name="Assistant Agent Application",
        system_prompt=SYSTEM_PROMPT,
    )
    user_svc = build_user_service(session)
    builder.add_service(
        name=user_svc.name,
        service=user_svc.service,
        instructions=user_svc.instructions,
        middleware=user_svc.middleware,
        args=user_svc.args,
        kwargs=user_svc.kwargs,
    )
    commerce = build_commerce_module(session)
    builder.add_module(
        name=commerce.name,
        services=commerce.services,
        description=commerce.description,
        system_prompt=commerce.system_prompt,
    )
    communication = build_communication_module(session)
    builder.add_module(
        name=communication.name,
        services=communication.services,
        description=communication.description,
        system_prompt=communication.system_prompt,
    )
    return builder


class TestChatPerformanceAnalysis:
    """
    Test que analiza qué se envía al LLM y métricas de rendimiento
    """

    def test_llm_payload_analysis(self, client):
        """
        Analiza el payload completo que se envía al LLM incluyendo:
        - System prompt
        - Mensaje del usuario
        - Servicios descubiertos (vía el contrato de TTMBuilder)
        """
        print("\n" + "="*80)
        print("ANALISIS DEL PAYLOAD ENVIADO AL LLM")
        print("="*80)

        # 1. Primero creamos una sesion
        create_resp = client.post("/api/chat/sessions", data={"title": "Test Analisis"})
        chat_id = create_resp.json()["data"]["chat_id"]
        print(f"\n[1] Sesion creada: {chat_id}")

        # 2. Capturamos el payload real construyendo el builder con la misma
        #    configuracion que usa chat_send -> chat_task_manager.start
        metrics = LLMMetrics()

        # El endpoint delega en chat_task_manager.start; lo mockeamos para
        # no lanzar un agente real y capturar los parametros de la llamada.
        with patch("app.router.api.chat.chat_task_manager") as mock_task_manager:
            mock_task_manager.start = AsyncMock(return_value="task-1")

            # 3. Enviamos el mensaje problemático
            test_message = "Revisando el invantario y los pagos en COP voy mal? estoy teniendo perdidas?"

            print("\n[2] ENVIANDO MENSAJE AL CHAT:")
            print(f"    Mensaje: '{test_message}'")

            response = client.post(
                f"/api/chat/sessions/{chat_id}/send",
                data={"message": test_message}
            )

            print("\n[3] RESPUESTA DEL ENDPOINT:")
            print(f"    Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"    Task ID: {data['data'].get('task_id')}")
                print(f"    Status: {data['data'].get('status')}")

            call_kwargs = mock_task_manager.start.await_args.kwargs
            metrics.user_message_length = len(call_kwargs["message"])
            metrics.system_prompt_length = len(call_kwargs["system_prompt"])
            metrics.messages_sent.append({"role": "user", "content": call_kwargs["message"]})

        # 4. Analizamos el payload que el agente ve (contrato TTMBuilder)
        print("\n[4] PAYLOAD DE LA TAREA ESCALADA:")
        print(f"    Model: {call_kwargs['model']}")
        print("    System Prompt Preview:")
        system_prompt = call_kwargs["system_prompt"]
        if system_prompt:
            print("    --- INICIO SYSTEM PROMPT ---")
            print(f"    {system_prompt[:500]}...")
            print("    --- FIN SYSTEM PROMPT (preview) ---")
            print(f"    Longitud total: {len(system_prompt)} caracteres")
        print(f"    Mensaje del usuario: '{call_kwargs['message']}'")

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

        resources = [
            build_user_service(session),
            build_order_service(session),
            build_inventory_service(session),
            build_payment_service(session),
            build_notification_service(session),
            build_commerce_module(session),
            build_communication_module(session),
        ]

        services = [r for r in resources if type(r).__name__ == "Service"]
        modules = [r for r in resources if type(r).__name__ == "Module"]

        # Obtenemos todas las herramientas disponibles vía build_as_capability
        print("\n[1] SERVICIOS REGISTRADOS:")
        tool_specs = []
        for s in services:
            capability = s.build_as_capability()
            tool_names = [t.name for t in capability.tools]
            tool_specs.extend(tool_names)
            print(f"    - {s.name}: {s.instructions[:80]}...")

        print("\n[2] MODULOS REGISTRADOS:")
        for m in modules:
            print(f"    - {m.name}: {m.description[:80]}...")

        print("\n[3] TOOLS (lo que el LLM puede usar):")
        for i, name in enumerate(tool_specs, 1):
            print(f"    {i}. {name}")

        print("\n[4] RESUMEN:")
        print(f"    Total herramientas: {len(tool_specs)}")
        print(f"    Servicios: {len(services)}")
        print(f"    Modulos: {len(modules)}")

        print("\n" + "="*80)

        # Verificaciones basicas
        assert len(services) > 0, "Deberia haber servicios registrados"
        assert len(modules) > 0, "Deberia haber modulos registrados"
        assert len(tool_specs) > 0, "Deberia haber tools disponibles"

    def test_system_prompt_construction(self, session):
        """
        Analiza como se construye el system prompt que ve el LLM
        (SYSTEM_PROMPT de la app + instructions por servicio en capabilities)
        """
        print("\n" + "="*80)
        print("CONSTRUCCION DEL SYSTEM PROMPT")
        print("="*80)

        from app.router.api.chat import SYSTEM_PROMPT

        # System prompt de la app
        print("\n[1] SYSTEM PROMPT DE LA APLICACION:")
        print(f"    '{SYSTEM_PROMPT}'")
        print(f"    Longitud: {len(SYSTEM_PROMPT)} caracteres")

        # Instrucciones por servicio (el equivalente actual de build_instructions)
        builder = _build_builder(session)
        builder.build()
        root = builder.agent.root_capability
        framework_instructions = root.get_instructions()
        auto_system_prompt = "\n".join(
            s for s in framework_instructions if isinstance(s, str)
        )

        print("\n[2] INSTRUCTIONS AUTO-GENERADAS (primeros 1000 chars):")
        print(f"    {auto_system_prompt[:1000]}...")
        print(f"    Longitud total: {len(auto_system_prompt)} caracteres")

        # Instrucciones explícitas por servicio (Capability.get_instructions)
        service_instructions = []
        for cap in root.capabilities:
            if type(cap).__name__ != "Capability":
                continue
            cap_instructions = cap.get_instructions()
            if cap_instructions:
                service_instructions.append("\n".join(cap_instructions))

        print("\n[3] ANALISIS DE COMPLEJIDAD DEL CONTEXTO:")
        total_prompt_size = len(SYSTEM_PROMPT) + len(auto_system_prompt)
        print(f"    System prompt app: {len(SYSTEM_PROMPT)} chars")
        print(f"    Instructions auto: {len(auto_system_prompt)} chars")
        print(f"    Total contexto fijo: ~{total_prompt_size} chars (~{total_prompt_size // 4} tokens estimados)")

        print("\n" + "="*80)

        # Verificaciones
        assert len(SYSTEM_PROMPT) > 100, "System prompt deberia ser sustancial"
        assert len(auto_system_prompt) > 0, "Las instructions deberian incluir info de herramientas"
        assert len(service_instructions) > 0, "Los servicios deberian declarar instructions"

    def test_mocked_llm_call_tracking(self, session):
        """
        Rastrea las llamadas reales al LLM con tracking completo
        (construye el agente real sin ejecutarlo)
        """
        print("\n" + "="*80)
        print("TRACKING DE LLAMADAS AL LLM (SIMULADO)")
        print("="*80)

        import os
        if not os.environ.get("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set, skipping real agent construction test")

        from app.security.middleware_ai.sanitize import SensitiveFieldMiddlewareAI

        # Construimos el builder real
        builder = _build_builder(session)
        builder.add_middleware(SensitiveFieldMiddlewareAI())
        builder.build()

        agent = builder.agent

        print("\n[1] AGENTE CONSTRUIDO EXITOSAMENTE")
        print(f"    Model: {agent.model}")

        # Simulamos una llamada y rastreamos
        print("\n[2] SIMULACION DE FLUJO DE EJECUCION:")

        test_message = "Revisando el invantario y los pagos en COP voy mal? estoy teniendo perdidas?"

        print("\n    Paso 1: Usuario envia mensaje")
        print(f"    Mensaje: '{test_message}'")

        print("\n    Paso 2: Sistema construye contexto")
        print("    - System prompt se agrega al historial")
        print("    - User message se agrega al historial")
        print("    - Tools se serializan como disponibles")

        print("\n    Paso 3: LLM recibe:")
        print("    - Rol: system -> System prompt")
        print(f"    - Rol: user -> '{test_message}'")

        print("\n    Paso 4: LLM decide acciones")
        print("    - Podria llamar a inventory_service (list_products)")
        print("    - Podria llamar a payment_service (list_payments)")
        print("    - Podria llamar a order_service (list_orders)")

        print("\n    Paso 5: Respuesta generada")
        print("    - Tokens de respuesta estimados: ~200-500")

        print("\n[3] METRICAS ESTIMADAS DE LA LLAMADA:")
        print("    - Input tokens estimados: ~800-1200 (contexto + mensaje)")
        print("    - Output tokens estimados: ~200-500 (respuesta)")
        print("    - Posibles tool calls: 0-3 (depende del analisis del LLM)")
        print("    - Tiempo estimado: 1-3 segundos (Groq es rapido)")

        print("\n" + "="*80)

        # Verificacion de que el agente se construyo correctamente
        assert agent is not None, "El agente deberia construirse correctamente"
        assert agent.model is not None, "El agente deberia tener un modelo"

    def test_performance_metrics_collection(self, client):
        """
        Recolecta metricas de rendimiento de una llamada real al chat
        (tarea mockeada en la frontera chat_task_manager.start)
        """
        print("\n" + "="*80)
        print("METRICAS DE RENDIMIENTO")
        print("="*80)

        call_log = []

        with patch("app.router.api.chat.chat_task_manager") as mock_task_manager:
            async def capture_start(**kwargs):
                call_log.append({
                    "type": "start",
                    "kwargs": kwargs,
                })
                return "task-1"

            mock_task_manager.start = capture_start

            create_resp = client.post("/api/chat/sessions", data={"title": "Performance Test"})
            chat_id = create_resp.json()["data"]["chat_id"]

            start_time = time.time()

            response = client.post(
                f"/api/chat/sessions/{chat_id}/send",
                data={"message": "Test message"}
            )

            end_time = time.time()

            print("\n[1] METRICAS DE EJECUCION:")
            print(f"    Tiempo total: {(end_time - start_time) * 1000:.2f}ms")
            print(f"    Status code: {response.status_code}")

            print("\n[2] LLAMADAS REGISTRADAS:")
            for i, call in enumerate(call_log, 1):
                print(f"    {i}. Tipo: {call['type']}")
                print(f"       Model: {call['kwargs'].get('model', 'N/A')}")
                print(f"       Mensaje: '{call['kwargs'].get('message')}'")

            print("\n[3] RESUMEN DE OPERACIONES:")
            print(f"    chat_task_manager.start llamado: {len(call_log)} vez/veces")

        print("\n" + "="*80)

    def test_context_window_analysis(self, session):
        """
        Analiza el tamano del contexto que consume el LLM
        """
        print("\n" + "="*80)
        print("ANALISIS DE VENTANA DE CONTEXTO")
        print("="*80)

        from app.router.api.chat import SYSTEM_PROMPT

        builder = _build_builder(session)
        builder.build()
        root = builder.agent.root_capability
        framework_instructions = root.get_instructions()
        auto_system_prompt = "\n".join(
            s for s in framework_instructions if isinstance(s, str)
        )

        test_message = "Revisando el invantario y los pagos en COP voy mal? estoy teniendo perdidas?"

        # Calculamos longitudes
        len_system = len(SYSTEM_PROMPT)
        len_auto = len(auto_system_prompt)
        len_message = len(test_message)
        total_chars = len_system + len_auto + len_message

        # Estimacion de tokens (aproximacion: 1 token ~ 4 caracteres)
        tok_system = len_system // 4
        tok_auto = len_auto // 4
        tok_message = len_message // 4
        total_tokens = tok_system + tok_auto + tok_message

        print("\n[1] DESGLOSE DEL CONTEXTO:")
        print("    +-----------------------------+----------+----------+")
        print("    | Componente                  | Chars    | Tokens   |")
        print("    +-----------------------------+----------+----------+")
        print(f"    | System Prompt (app)         | {len_system:>8} | {tok_system:>8} |")
        print(f"    | System Prompt (auto)        | {len_auto:>8} | {tok_auto:>8} |")
        print(f"    | User Message                | {len_message:>8} | {tok_message:>8} |")
        print("    +-----------------------------+----------+----------+")
        print(f"    | TOTAL ESTIMADO              | {total_chars:>8} | {total_tokens:>8} |")
        print("    +-----------------------------+----------+----------+")

        print("\n[2] ANALISIS DE CAPACIDAD:")
        print("    - Context window tipico Groq: 32K-128K tokens")
        print(f"    - Contexto usado: ~{total_tokens} tokens ({(total_tokens/32000)*100:.1f}% de 32K)")
        print(f"    - Espacio restante: ~{32000 - total_tokens} tokens")
        print(f"    - Capacidad para historial: ~{(32000 - total_tokens) // 100} mensajes adicionales")

        print("\n[3] RECOMENDACIONES:")
        if total_tokens > 10000:
            print("    - Contexto grande: considerar compresion de historial")
        if total_tokens > 5000:
            print("    - System prompt largo: evaluar si todo es necesario")
        print("    - Para este caso especifico, el contexto es manejable")

        print("\n" + "="*80)

        # Verificacion
        assert total_tokens < 32000, "El contexto no deberia exceder la ventana de tokens"