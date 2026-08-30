# Analisis del Contexto Enviado al LLM

> Generado automaticamente desde tests de rendimiento del example app.
> Fecha: 2026-08-29

---

## Texto completo que el LLM ve

### 1. System Prompt (app)

`
You are a friendly, conversational assistant for a commerce application. You can manage users, orders, products, payments, and notifications. Rules:
- ALWAYS respond in natural, conversational language, like chatting with a friend.
- When listing items, summarize them briefly in a natural sentence. Do NOT dump raw tables or technical fields.
- Never expose internal IDs, UUIDs, or technical field names to the user.
- When creating/updating/deleting, confirm what was done in a friendly way.
- If there is an error, explain it clearly and helpfully.
- Keep responses short and concise.
- Respond in the same language the user writes in.
`

### 2. System Prompt auto-generado (to_tool_manager)

`
<!-- DEFAULT:BEGIN -->
You are an assistant with access to tools. Each tool corresponds to a
Service or Module (sub-agent) and accepts a single operations
argument: a list of {"method": <name>, "args": {...}} objects.
Call a tool ONCE with every operation you need -- never call it
multiple times.

Each operation: {"method": <name>, "args": {"<param_name>": <value>, ...}}. The "args" keys MUST match the parameter names listed in each operation description. Optional "id" and "when" for sequencing.

Example: {"operations": [{"id": "s1", "method": "create_user",
"args": {"data": {"user_name": "...", "email": "..."}},
{"method": "list_users", "args": {},
"when": {"op": "s1", "outcome": "error"}}]}

Available tools:
- **user_service**: Manages user accounts: create, retrieve, update, and delete users.
- **commerce** (Module): Commerce sub-agent: manages products, orders, and payments. Use this module when the user's request involves creating or modifying products, placing orders, processing payments, or querying commerce-related data.
- **communication** (Module): Communication sub-agent: handles user notifications and authentication. Use this module for sending notifications, managing user sessions, or validating access.

Read each tool's own description for its operations and arguments.

Guidelines:
- Only use information returned by tools; never invent data.
- For multi-service requests, call each tool with all needed operations
  and combine results into a single answer.
- Each operation result has "success" + "result"|"error"; a batch call
  can mix successes and failures.
- Retry with different args only if the error is retryable; if the
  resource already exists or is not found, accept and move on.
- Ask only for strictly necessary information when the request is
  ambiguous.
- Never expose internal implementation details.
<!-- DEFAULT:END -->
`

### 3. Instructions (no persistido en historial)

`
<!-- DEFAULT:BEGIN -->
When a request implies multiple independent operations (e.g. creating
several records, or performing actions across more than one service),
execute all tool calls before writing your final answer, running
independent calls in parallel where possible.

Error handling -- hard rules:
- Do not retry a tool call with the exact same arguments after it fails.
- If a tool reports that a resource already exists or is not needed,
  accept that as a completed/no-op outcome and move on to the remaining
  tasks; do not treat it as a blocking failure.
- If a tool reports a resource was not found, record that and continue
  with the rest of the request.
- Never loop indefinitely retrying failed operations.

Once every requested operation has been attempted, stop calling tools
and produce a final, conversational summary:
- What succeeded
- What failed or was skipped, and why
- If the user asked to see/list something, mention the key details
  naturally (e.g. names, emails) without exposing internal IDs or
  technical field names. Do NOT dump raw data tables.
<!-- DEFAULT:END -->
`

### 4. Mensaje del usuario

`
Revisando el invantario y los pagos en COP voy mal? estoy teniendo perdidas?
`

---

## Resumen de tokens

| Componente | Chars | Tokens (~) |
|---|---|---|
| System Prompt (app) | 638 | 159 |
| System Prompt (auto) | 1,883 | 470 |
| Instructions | 1,102 | 275 |
| User Message | 76 | 19 |
| **TOTAL** | **3,699** | **~924** |

---

## Herramientas (tools) disponibles

El ToToolManager registra **3 tools** con formato batched (un solo parametro operations):

| Tool | Tipo | Descripcion |
|---|---|---|
| user_service | Service | CRUD de usuarios |
| commerce | Module (sub-agent) | Productos, ordenes, pagos |
| communication | Module (sub-agent) | Notificaciones, auth |

Cada Module delega a un **sub-agente** con sus propias tools internas:

- **commerce**: inventory_service, order_service, payment_service
- **communication**: 
otification_service, uth_service

---

## Errores y problemas detectados

### 1. System prompt duplicado

El system prompt se envia **dos veces** al LLM:

- **Una vez** como system_prompt del agente (definido en example/app/router/api/chat.py:26-37)
- **Otra vez** como system_prompt auto-generado por 	o_tool_manager (uild_system_prompt())

Pydantic-ai combina ambos en un solo mensaje system. Esto genera un prompt redundante: el LLM ve instrucciones sobre como conversar (app) Y sobre como usar tools (framework) en el mismo bloque. No hay separacion clara.

### 2. Instrucciones contradictorias o confusas

El system prompt de la app dice:
> "Keep responses short and concise."

Pero el system prompt auto-generado dice:
> "Once every requested operation has been attempted, stop calling tools and produce a final, conversational summary: What succeeded, What failed..."

Esto puede causar que el LLM genere respuestas largas para ser "conversacional" cuando deberia ser conciso.

### 3. Tools genericos pierden contexto

Los tools se presentan como user_service, commerce, communication con descripciones genericas. El LLM no sabe que commerce tiene internamente:
- inventory_service.list_products
- payment_service.list_payments
- order_service.list_orders

Esto fuerza al LLM a **adivinar** que tools internos existen dentro de cada module, o a hacer llamadas exploratorias que desperdician tokens.

### 4. Formato batched es opaco

El formato {"operations": [{"method": "...", "args": {...}}]} es poco convencional. Los LLMs estan entrenados con tool calling nativo (function calling de OpenAI, tool_use de Anthropic). El formato batched:
- No es el estandar de la industria
- Requiere mas instrucciones para explicarlo
- Puede confundir al LLM en la primera llamada

### 5. No se envia historial de conversacion

En el test actual, cuando el usuario envia un mensaje, **no se incluyen mensajes anteriores**. El LLM solo ve:
`
[system] System prompt
[user] Mensaje actual
`

Si el usuario pregunta "cuantos productos hay" y luego "y cuantos pagos", el LLM no tiene contexto de la primera pregunta. El ChatTaskManager guarda mensajes en BD pero **no los pasa al agente** en llamadas subsiguientes.

### 6. Instructions se envian pero no se persisten

Las instructions se marcan como "no persistido en historial", pero pydantic-ai las envia como parte del contexto del agente. Esto significa:
- El LLM las ve en cada request
- Ocupan tokens
- Pero no se guardan en el historial de conversacion
- Si el provider no soporta instructions separadas, se pierden

### 7. Error handling es reactivo, no proactivo

El system prompt incluye reglas de error handling:
> "Do not retry a tool call with the exact same arguments after it fails."

Pero no hay mecanismo para que el LLM **detecte** que un module tiene problemas antes de llamarlo. Si el commerce module falla por timeout, el LLM solo lo descubre despues de la llamada.

### 8. No hay feedback de tool availability

Cuando un module no esta disponible (ej: communication no tiene permisos), el LLM no lo sabe hasta que intenta usarlo. No se envia informacion sobre:
- Tools deshabilitados
- Rate limits por service
- Permisos del usuario actual

### 9. Tokens desperdiciados en el system prompt auto-generado

El system prompt auto-generado incluye:
- Un ejemplo completo de formato batched (150+ tokens)
- La lista de tools disponibles (200+ tokens)
- Guidelines genericas (300+ tokens)

Todo esto se envia en **cada request**, incluso si el usuario solo dice "hola". Para una aplicacion con muchos services, esto escala mal.

### 10. No hay diferenciacion entre modulos y servicios

El LLM ve user_service (Service) y commerce (Module) como la misma categoria de tool. Pero son conceptualmente diferentes:
- **Service**: ejecuta operaciones directamente
- **Module**: delega a un sub-agente que ejecuta operaciones

El LLM no puede distinguir cuando usar uno u otro basandose solo en las descripciones.

---

## Recomendaciones

1. **Unificar el system prompt**: combinar el prompt de la app con el auto-generado en un solo bloque coherente
2. **Incluir historial**: pasar mensajes anteriores del chat al agente para mantener contexto
3. **Serializar tools internos**: mostrar al LLM las tools reales de cada module, no solo el nombre del module
4. **Usar tool calling nativo**: si el provider lo soporta, usar function calling en lugar del formato batched
5. **Cachear instructions**: las instructions no deberian reenviarse en cada request si no cambian
6. **Diferenciar modules de services**: usar labels o categorias diferentes para que el LLM entienda la jerarquia
