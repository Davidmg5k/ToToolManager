
def prompt_template(
    agent_name: str,
    when_use_it: str,
    *,
    important: str = "",
) -> str:
    """Genera un prompt template para un agente.

    Precondición: agent_name y when_use_it son strings no vacíos
    Postcondición: retorna string con el template formateado
    """
    important_block = ""
    if important and important.strip():
        important_block = f"IMPORTANT\n{important}\n"

    return f"""I'm {agent_name}, a professional assistant.
---
USE ME WHEN
{when_use_it}
---

---
{important_block}
---
"""
