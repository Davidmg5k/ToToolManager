import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, create_engine

from app.controller.agent import (
    build_user_service,
    build_commerce_module,
    build_communication_module,
)
from app.router.api.chat import SYSTEM_PROMPT
from app.security.middleware_ai.sanitize import SensitiveFieldMiddlewareAI
from to_tool_manager import TTMBuilder

# Construimos el builder igual que en la app
db_path = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")
engine = create_engine(f"sqlite:///{db_path}")

with Session(engine) as session:
    builder = TTMBuilder(
        name="Assistant Agent Application",
        system_prompt=SYSTEM_PROMPT,
    )
    # user_service va directo al builder (mantiene middleware y args del Service)
    user_svc = build_user_service(session)
    builder.add_service(
        name=user_svc.name,
        service=user_svc.service,
        instructions=user_svc.instructions,
        middleware=user_svc.middleware,
        args=user_svc.args,
        kwargs=user_svc.kwargs,
    )
    # Los módulos conservan sus servicios internos (con middlewares y args)
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
    builder.add_middleware(SensitiveFieldMiddlewareAI())
    builder.build()

    agent = builder.agent
    root = agent.root_capability

    # Capabilities de servicios: id + tools
    service_rows = []
    module_rows = []
    for cap in root.capabilities:
        cap_id = getattr(cap, "id", None)
        cap_type = type(cap).__name__
        if cap_type == "Capability":
            tools = getattr(cap, "tools", None) or []
            tool_names = [t.name if hasattr(t, "name") else str(t) for t in tools]
            service_rows.append({"id": cap_id, "tools": tool_names})
        elif cap_type == "SubAgents" and cap_id:
            module_rows.append({"id": cap_id})

    # Instrucciones efectivas (lo que el LLM recibe del framework)
    framework_instructions = root.get_instructions()
    instructions_text = "\n".join(
        s for s in framework_instructions if isinstance(s, str)
    )

    test_message = "Revisando el invantario y los pagos en COP voy mal? estoy teniendo perdidas?"

    print("# Texto completo que el LLM ve")
    print()
    print("---")
    print()
    print("## 1. Mensaje de sistema (system prompt)")
    print()
    print("`")
    print(SYSTEM_PROMPT)
    print("`")
    print()
    print("## 2. Capabilities registradas por to_tool_manager")
    print()
    print("`")
    for row in service_rows:
        print(f"[{row['id']}] tools: {', '.join(row['tools'])}")
    for row in module_rows:
        print(f"[{row['id']}] (sub-agente: delega con delegate_task)")
    print("`")
    print()
    print("## 3. Instrucciones auto-generadas por to_tool_manager")
    print()
    print("`")
    print(instructions_text if instructions_text else "(sin instrucciones auto-generadas)")
    print("`")
    print()
    print("## 4. Mensaje del usuario")
    print()
    print("`")
    print(test_message)
    print("`")
    print()
    print("---")
    print()
    print("## Resumen de tokens")
    print()
    all_tools = [t for row in service_rows for t in row["tools"]]
    total = len(SYSTEM_PROMPT) + len(instructions_text) + len(test_message)
    print("| Componente | Chars | Tokens (~) |")
    print("|---|---|---|")
    print(f"| System Prompt (app) | {len(SYSTEM_PROMPT)} | {len(SYSTEM_PROMPT)//4} |")
    print(f"| Instrucciones (auto) | {len(instructions_text)} | {len(instructions_text)//4} |")
    print(f"| Tools registrados | {len(all_tools)} | - |")
    print(f"| User Message | {len(test_message)} | {len(test_message)//4} |")
    print(f"| **TOTAL** | **{total}** | **{total//4}** |")