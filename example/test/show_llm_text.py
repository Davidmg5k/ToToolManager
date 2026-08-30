import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.controller.agent import (
    build_user_service,
    build_commerce_module,
    build_communication_module,
)
from to_tool_manager import ToToolManager
from to_tool_manager.core.prompts import build_system_prompt, build_instructions
from app.router.api.chat import SYSTEM_PROMPT

# Construimos el manager igual que en la app
from sqlmodel import Session, SQLModel, create_engine

db_path = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")
engine = create_engine(f"sqlite:///{db_path}")

with Session(engine) as session:
    manager = ToToolManager([
        build_user_service(session),
        build_commerce_module(session),
        build_communication_module(session),
    ])

    all_services = list(manager.services.values()) + list(manager.modules.values())
    auto_system_prompt = build_system_prompt(all_services)
    instructions = build_instructions()

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
    print("## 2. System prompt auto-generado por to_tool_manager (con tools)")
    print()
    print("`")
    print(auto_system_prompt)
    print("`")
    print()
    print("## 3. Instructions (no persistido en historial, se envía aparte)")
    print()
    print("`")
    print(instructions)
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
    total = len(SYSTEM_PROMPT) + len(auto_system_prompt) + len(instructions) + len(test_message)
    print(f"| Componente | Chars | Tokens (~) |")
    print(f"|---|---|---|")
    print(f"| System Prompt (app) | {len(SYSTEM_PROMPT)} | {len(SYSTEM_PROMPT)//4} |")
    print(f"| System Prompt (auto) | {len(auto_system_prompt)} | {len(auto_system_prompt)//4} |")
    print(f"| Instructions | {len(instructions)} | {len(instructions)//4} |")
    print(f"| User Message | {len(test_message)} | {len(test_message)//4} |")
    print(f"| **TOTAL** | **{total}** | **{total//4}** |")
