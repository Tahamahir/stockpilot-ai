from __future__ import annotations

import json
import os
import re

import httpx

from app.business_tools import (
    get_inventory_summary,
    get_product_forecast,
    get_replenishment_priorities,
    get_sales_performance,
    get_supplier_performance,
    get_stockpilot_capabilities,
)


# =========================================================
# Configuration
# =========================================================

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://ollama:11434",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:4b",
)
FAST_BUSINESS_RESPONSES = (
    os.getenv(
        "FAST_BUSINESS_RESPONSES",
        "true",
    )
    .strip()
    .lower()
    == "true"
)

OLLAMA_TIMEOUT = httpx.Timeout(
    connect=15.0,
    read=600.0,
    write=60.0,
    pool=60.0,
)


# =========================================================
# Business labels
# =========================================================

URGENCY_LABELS = {
    "critical": "Critique",
    "high": "Élevée",
    "medium": "Moyenne",
    "planned": "Planifiée",
    "no_order": "Aucune commande",
}


SUPPLIER_TIER_LABELS = {
    "excellent": "Excellent",
    "good": "Bon",
    "needs_monitoring": "À surveiller",
    "critical": "Critique",
}


# =========================================================
# Structured routing schema
# =========================================================

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "tool": {
            "type": "string",
            "enum": [
                "get_inventory_summary",
                "get_replenishment_priorities",
                "get_product_forecast",
                "get_sales_performance",
                "get_supplier_performance",
                "none",
            ],
        },
        "limit": {
            "type": "integer",
        },
        "urgency": {
            "type": "string",
        },
        "sku": {
            "type": "string",
        },
        "store_name": {
            "type": "string",
        },
    },
    "required": [
        "tool",
        "limit",
        "urgency",
        "sku",
        "store_name",
    ],
}
STOCKPILOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_inventory_summary",
            "description": (
                "Récupère les DONNÉES RÉELLES de performance "
                "des fournisseurs StockPilot : scores, taux de "
                "livraison à temps, fulfillment, retards, meilleurs "
                "fournisseurs et fournisseurs à risque. "
                "Utiliser uniquement lorsque l'utilisateur demande "
                "des résultats, KPI, classements ou analyses réelles "
                "sur les fournisseurs. "
                "NE PAS utiliser lorsque l'utilisateur demande "
                "simplement ce que propose, fait ou permet le module "
                "Supplier Performance. Dans ce cas utiliser "
                "get_stockpilot_capabilities avec "
                "topic='supplier_performance'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_replenishment_priorities",
            "description": (
                "Retourne les recommandations ML de "
                "réapprovisionnement déjà classées par priorité. "
                "Utiliser pour savoir quoi commander, "
                "réapprovisionner ou prioriser."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Nombre de recommandations souhaitées. "
                            "5 par défaut."
                        ),
                    },
                    "urgency": {
                        "type": "string",
                        "enum": [
                            "critical",
                            "high",
                            "medium",
                            "planned",
                            "no_order",
                        ],
                        "description": (
                            "Filtre uniquement si l'utilisateur demande "
                            "explicitement un niveau précis, par exemple "
                            "'uniquement les critiques'. "
                            "NE PAS utiliser ce paramètre pour "
                            "'les plus urgents' ou 'les priorités', "
                            "car le backend classe déjà les résultats "
                            "du plus urgent au moins urgent."
                        ),
                    },
                    "store_name": {
                        "type": "string",
                        "description": (
                            "Magasin optionnel, par exemple "
                            "Rabat ou Casablanca."
                        ),
                    },
                },
                "required": [],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_product_forecast",
            "description": (
                "Retourne la prévision réelle de demande "
                "pour un SKU, éventuellement pour un magasin."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {
                        "type": "string",
                        "description": (
                            "SKU du produit, par exemple SKU-00017."
                        ),
                    },
                    "store_name": {
                        "type": "string",
                        "description": (
                            "Magasin optionnel."
                        ),
                    },
                },
                "required": ["sku"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_sales_performance",
            "description": (
                "Retourne les données réelles de ventes : "
                "chiffre d'affaires, marge, transactions, "
                "produits les plus vendus et performances magasins."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Nombre d'éléments dans les classements. "
                            "5 par défaut."
                        ),
                    },
                },
                "required": [],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_supplier_performance",
            "description": (
                "Retourne les performances réelles des fournisseurs : "
                "scores, livraisons à temps, fulfillment et retards."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Nombre de fournisseurs dans les résultats. "
                            "5 par défaut."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
    "type": "function",
    "function": {
        "name": "get_stockpilot_capabilities",
        "description": (
            "Source de vérité sur les fonctionnalités, modules "
            "et limites de StockPilot. "
            "Utiliser lorsque l'utilisateur demande ce que fait, "
            "propose ou permet StockPilot ou un de ses modules. "
            "Exemples : 'Que propose Inventory Health ?', "
            "'À quoi sert Demand Forecast ?', "
            "'Explique Replenishment', "
            "'Que propose Supplier Performance ?'. "
            "Pour ces questions, ne pas utiliser les tools "
            "de données métier."
            ),
        
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": [
                        "overview",
                        "inventory_health",
                        "sales",
                        "demand_forecast",
                        "replenishment",
                        "supplier_performance",
                        "real_time",
                        "automatic_orders",
                        "automatic_promotions",
                        "erp",
                    ],
                }
            },
            "required": [],
        },
    },
},

]
ALLOWED_TOOL_NAMES = {
    "get_inventory_summary",
    "get_replenishment_priorities",
    "get_product_forecast",
    "get_sales_performance",
    "get_supplier_performance",
    "get_stockpilot_capabilities"
}


def sanitize_agent_route(
    tool_name: str,
    arguments: dict | None,
    user_message: str = "",
) -> dict:
    route = default_route()

    if tool_name not in ALLOWED_TOOL_NAMES:
        return route

    route["tool"] = tool_name

    if not isinstance(arguments, dict):
        arguments = {}

    # -----------------------------
    # Limit
    # -----------------------------

    try:
        route["limit"] = max(
            1,
            min(
                int(
                    arguments.get(
                        "limit",
                        5,
                    )
                ),
                50,
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        route["limit"] = 5

    # -----------------------------
    # Urgency
    # -----------------------------

    requested_urgency = str(
        arguments.get(
            "urgency",
            "",
        )
        or ""
    ).strip().lower()

    message = (
        user_message
        .strip()
        .lower()
    )

    explicit_urgency = ""

    if any(
        word in message
        for word in (
            "critique",
            "critiques",
            "critical",
        )
    ):
        explicit_urgency = "critical"

    elif any(
        word in message
        for word in (
            "priorité élevée",
            "priorite elevee",
            "high",
        )
    ):
        explicit_urgency = "high"

    elif any(
        word in message
        for word in (
            "priorité moyenne",
            "priorite moyenne",
            "medium",
        )
    ):
        explicit_urgency = "medium"

    elif any(
        word in message
        for word in (
            "planifiée",
            "planifiee",
            "planned",
        )
    ):
        explicit_urgency = "planned"

    elif any(
        word in message
        for word in (
            "sans commande",
            "aucune commande",
            "no_order",
        )
    ):
        explicit_urgency = "no_order"

    # Important:
    # "les plus urgents" != urgency="high".
    # Dans ce cas, on conserve le classement naturel
    # du moteur StockPilot.
    if explicit_urgency:
        route["urgency"] = (
            explicit_urgency
        )

    else:
        route["urgency"] = ""

    # -----------------------------
    # SKU
    # -----------------------------

    sku = str(
        arguments.get(
            "sku",
            "",
        )
        or ""
    ).strip().upper()

    if re.fullmatch(
        r"SKU-\d+",
        sku,
        flags=re.IGNORECASE,
    ):
        route["sku"] = sku

    # -----------------------------
    # Store
    # -----------------------------

    store_name = str(
        arguments.get(
            "store_name",
            "",
        )
        or ""
    ).strip()

    if len(store_name) <= 100:
        route["store_name"] = store_name
        # -----------------------------
    # StockPilot capability topic
    # -----------------------------

    allowed_topics = {
        "overview",
        "inventory_health",
        "sales",
        "demand_forecast",
        "replenishment",
        "supplier_performance",
        "real_time",
        "automatic_orders",
        "automatic_promotions",
        "erp",
    }

    topic = str(
        arguments.get(
            "topic",
            "",
        )
        or ""
    ).strip().lower()

    if (
        tool_name
        == "get_stockpilot_capabilities"
    ):
        if topic not in allowed_topics:
            topic = "overview"

        route["topic"] = topic

    return route

def agent_route_user_request(
    user_message: str,
    context: dict | None = None,
) -> tuple[dict, bool]:
    """
    Let Qwen choose the appropriate StockPilot tool.

    Returns:
        (route, success)

    success=True:
        Qwen produced a valid decision,
        including the decision to use no tool.

    success=False:
        Ollama failed or returned invalid data.
        The legacy router can then be used as fallback.
    """

    conversation_context = (
        normalize_conversation_context(
            context
        )
    )

    context_json = json.dumps(
        conversation_context,
        ensure_ascii=False,
    )

    system_prompt = """
Tu es StockPilot AI, l'assistant intelligent intégré
à la plateforme StockPilot.

StockPilot permet actuellement de :

- analyser les ventes historiques ;
- consulter le chiffre d'affaires, la marge
  et les performances commerciales ;
- analyser la santé des stocks ;
- identifier les ruptures, stocks faibles,
  positions critiques et surstocks ;
- consulter les prévisions de demande générées
  par le modèle ML ;
- consulter les recommandations ML
  de réapprovisionnement ;
- analyser les performances des fournisseurs ;
- comparer les performances des magasins
  à partir des données disponibles.

IMPORTANT :

Tu ne dois jamais prétendre que StockPilot possède
une fonctionnalité qui n'est pas explicitement
mentionnée ci-dessus.

En particulier, ne prétends pas que StockPilot :

- fonctionne en temps réel ;
- passe automatiquement des commandes ;
- modifie le stock après chaque vente ;
- contacte automatiquement les fournisseurs ;
- exécute automatiquement des promotions ;
- remplace un ERP ;
- prend automatiquement des décisions commerciales.

Les recommandations StockPilot sont des aides
à la décision.

Pour toute question nécessitant des chiffres réels
StockPilot, les données doivent provenir des tools.

Pour une question générale ou conversationnelle,
réponds naturellement sans inventer de données.

Réponds en français.
Sois naturel, utile et concis.
"""

    try:
        payload = call_ollama(
            {
                "model":
                    OLLAMA_MODEL,

                "messages": [
                    {
                        "role":
                            "system",

                        "content":
                            system_prompt,
                    },
                    {
                        "role":
                            "user",

                        "content":
                            user_message,
                    },
                ],

                "tools":
                    STOCKPILOT_TOOLS,

                "stream":
                    False,

                "think":
                    False,

                "options": {
                    "temperature":
                        0,

                    "num_predict":
                        150,
                },
            }
        )

        message = payload.get(
            "message",
            {},
        )

        tool_calls = message.get(
            "tool_calls",
            [],
        )

        # Qwen intentionally decided
        # that no business tool is required.
        if not tool_calls:
            return (
                default_route(),
                True,
            )

        tool_call = tool_calls[0]

        function = tool_call.get(
            "function",
            {},
        )

        tool_name = function.get(
            "name",
            "",
        )

        arguments = function.get(
            "arguments",
            {},
        )

        route = sanitize_agent_route(
            tool_name=tool_name,
            arguments=arguments,
            user_message=user_message,
        )

        if route["tool"] == "none":
            return (
                default_route(),
                False,
            )

        return (
            route,
            True,
        )

    except (
        httpx.HTTPError,
        TypeError,
        ValueError,
        KeyError,
    ):
        return (
            default_route(),
            False,
        )

def agent_plan_user_request(
    user_message: str,
    context: dict | None = None,
) -> tuple[list[dict], bool]:
    """
    Let Qwen select one or several StockPilot tools.

    Returns:
        (routes, success)

    [] + success=True:
        no business tool is needed.

    success=False:
        agent planning failed.
    """
    conversation_memory = (
        normalize_conversation_context(
            context
        )
        )

    memory_json = json.dumps(
        conversation_memory,
        ensure_ascii=False,
    )
    conversation_context = (
        normalize_conversation_context(
            context
        )
    )

    context_json = json.dumps(
        conversation_context,
        ensure_ascii=False,
    )

    system_prompt = f"""
Tu es le cerveau de routing de StockPilot AI.

Tu disposes de plusieurs tools sécurisés.

Une question peut nécessiter :
- aucun tool ;
- un seul tool ;
- plusieurs tools.

Utilise TOUS les tools réellement nécessaires
pour répondre à la demande utilisateur.

Exemples :

"Quelle est la situation de mon stock ?"
→ get_inventory_summary

"Donne-moi les 3 réapprovisionnements les plus urgents"
→ get_replenishment_priorities(limit=3)

"Analyse mon stock et donne-moi les 3
réapprovisionnements les plus urgents"
→ get_inventory_summary
ET get_replenishment_priorities(limit=3)

"Quel est mon CA et quels fournisseurs
ont le plus de problèmes ?"
→ get_sales_performance
ET get_supplier_performance

"Bonjour"
→ aucun tool.
RÈGLE DE DISTINCTION ENTRE DESCRIPTION D'UN MODULE
ET CONSULTATION DES DONNÉES :

Si l'utilisateur demande ce qu'un module "propose",
"fait", "permet", "sert à faire" ou demande de
"l'expliquer", il demande les fonctionnalités
du module.

Dans ce cas, utiliser get_stockpilot_capabilities
avec le topic correspondant.

Exemples :

"Que propose Supplier Performance ?"
→ get_stockpilot_capabilities
  topic="supplier_performance"

"À quoi sert Demand Forecast ?"
→ get_stockpilot_capabilities
  topic="demand_forecast"

"Explique Inventory Health"
→ get_stockpilot_capabilities
  topic="inventory_health"

En revanche, si l'utilisateur demande des chiffres,
résultats, KPI, classements ou analyses réelles,
utiliser le business tool correspondant.

"Quels fournisseurs sont les moins performants ?"
→ get_supplier_performance

"Quelle est la demande prévue pour SKU-00017 ?"
→ get_product_forecast
IMPORTANT :

Pour "les plus urgents", "prioritaires",
"les premières priorités" :
NE PAS renseigner urgency.

Le backend classe déjà les recommandations :
critical → high → medium → planned.

Utilise urgency uniquement si l'utilisateur
demande explicitement un niveau précis,
par exemple :
"uniquement les critiques".

N'invente jamais de données StockPilot.
MÉMOIRE CONVERSATIONNELLE :

Tu reçois un CONTEXTE_ACTIF contenant éventuellement :

- last_tool : dernier outil métier utilisé ;
- active_sku : produit actuellement référencé ;
- active_store : magasin actuellement référencé ;
- sku / store_name : filtres précédemment utilisés ;
- topic : dernier module évoqué.

Utilise ce contexte pour comprendre les références
conversationnelles comme :

"ce produit"
"ce SKU"
"sa prévision"
"pour lui"
"ce magasin"
"seulement là-bas"
"et à Rabat ?"

IMPORTANT :

Une nouvelle intention explicite de l'utilisateur
est toujours prioritaire sur l'ancien contexte.

Si l'utilisateur demande une DONNÉE RÉELLE sur
l'entité active, utilise le business tool correspondant.

Exemple :

CONTEXTE_ACTIF :
active_sku = SKU-00105
active_store = Magasin Casablanca

Utilisateur :
"Et sa prévision ?"

→ utiliser get_product_forecast
→ sku = SKU-00105
→ store_name = Magasin Casablanca

NE PAS utiliser get_stockpilot_capabilities dans ce cas.

get_stockpilot_capabilities sert uniquement à expliquer
ce que fait ou propose un module.

Exemple :

"Que propose Demand Forecast ?"
→ get_stockpilot_capabilities

"Et sa prévision ?"
avec active_sku disponible
→ get_product_forecast
Contexte conversationnel :

{context_json}
"""

    try:
        payload = call_ollama(
            {
                "model":
                    OLLAMA_MODEL,

                "messages": [
                    {
                        "role":
                            "system",

                        "content":
                            system_prompt,
                    },
                    {
                        "role":
                            "user",

                        "content": (
                            f"CONTEXTE_ACTIF :\n"
                            f"{memory_json}\n\n"
                            f"DEMANDE_UTILISATEUR :\n"
                            f"{user_message}"
                        ),
                    },
                ],

                "tools":
                    STOCKPILOT_TOOLS,

                "stream":
                    False,

                "think":
                    False,

                "options": {
                    "temperature":
                        0,

                    "num_predict":
                        220,
                },
            }
        )

        message = payload.get(
            "message",
            {},
        )

        tool_calls = message.get(
            "tool_calls",
            [],
        )

        # Qwen intentionally decided
        # that no tool is required.
        if not tool_calls:
            return [], True

        routes = []

        # Security:
        # never execute an unlimited number
        # of model-generated tool calls.
        for tool_call in tool_calls[:5]:

            function = tool_call.get(
                "function",
                {},
            )

            tool_name = function.get(
                "name",
                "",
            )

            arguments = function.get(
                "arguments",
                {},
            )

            route = sanitize_agent_route(
                tool_name=tool_name,
                arguments=arguments,
                user_message=user_message,
            )

            if route["tool"] == "none":
                continue

            route = apply_conversation_context(
                user_message=user_message,
                route=route,
                context=context,
            )

            routes.append(
                route
            )

        if not routes:
            return [], False

        # Remove exact duplicate calls.
        unique_routes = []
        seen = set()

        for route in routes:

            route_key = (
                route.get(
                    "tool",
                    "none",
                ),
                route.get(
                    "limit",
                    5,
                ),
                route.get(
                    "urgency",
                    "",
                ),
                route.get(
                    "sku",
                    "",
                ),
                route.get(
                    "store_name",
                    "",
                ),
                route.get(
                    "topic",
                    "",
                ),
            )

            if route_key in seen:
                continue

            seen.add(
                route_key
            )

            unique_routes.append(
                route
            )

        return (
            unique_routes,
            True,
        )

    except (
        httpx.HTTPError,
        TypeError,
        ValueError,
        KeyError,
    ):
        return [], False


# =========================================================
# Ollama HTTP
# =========================================================

def call_ollama(
    payload: dict,
) -> dict:
    # Qwen3 peut utiliser un mode de raisonnement
    # plus lent. Pour StockPilot, on privilégie
    # des réponses rapides.
    payload.setdefault(
        "think",
        False,
    )

    # Garde le modèle chargé pendant 30 minutes
    # afin d'éviter de le recharger à chaque question.
    payload.setdefault(
        "keep_alive",
        "30m",
    )

    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=OLLAMA_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# Health
# =========================================================

def test_ollama_connection() -> dict:
    response = httpx.get(
        f"{OLLAMA_BASE_URL}/api/tags",
        timeout=10.0,
    )

    response.raise_for_status()

    payload = response.json()

    models = [
        model.get("name")
        for model in payload.get(
            "models",
            [],
        )
    ]

    return {
        "status": "ok",
        "model": OLLAMA_MODEL,
        "available": OLLAMA_MODEL in models,
        "installed_models": models,
    }


# =========================================================
# Formatting
# =========================================================

def format_number_fr(
    value,
    decimals: int = 2,
) -> str:
    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        number = 0.0

    formatted = (
        f"{number:,.{decimals}f}"
    )

    return (
        formatted
        .replace(",", " ")
        .replace(".", ",")
    )


def localize_business_terms(
    content: str,
) -> str:
    """
    Translate business status labels that Qwen may
    occasionally return in English.
    """

    if not content:
        return ""

    replacements = {
        "priorité critical":
            "priorité Critique",

        "priorité high":
            "priorité Élevée",

        "priorité medium":
            "priorité Moyenne",

        "priorité planned":
            "priorité Planifiée",

        "priority critical":
            "priorité Critique",

        "priority high":
            "priorité Élevée",

        "priority medium":
            "priorité Moyenne",

        "priority planned":
            "priorité Planifiée",
    }

    localized = content

    for source, target in replacements.items():
        localized = re.sub(
            re.escape(source),
            target,
            localized,
            flags=re.IGNORECASE,
        )

    return localized


# =========================================================
# Remove leaked reasoning
# =========================================================

def clean_model_answer(
    content: str,
) -> str:
    if not content:
        return ""

    cleaned = content.strip()

    cleaned = re.sub(
        r"(?is)<think>.*?</think>",
        "",
        cleaned,
    ).strip()

    if "</think>" in cleaned:
        cleaned = (
            cleaned
            .split(
                "</think>",
                1,
            )[1]
            .strip()
        )

    return cleaned


def contains_reasoning_leak(
    content: str,
) -> bool:
    if not content:
        return True

    lowered = (
        content
        .strip()
        .lower()
    )

    suspicious_starts = (
        "okay,",
        "okay ",
        "let me",
        "let's",
        "first, i need",
        "first,",
        "we need",
        "i need to",
        "the user",
        "looking at",
    )

    if lowered.startswith(
        suspicious_starts
    ):
        return True

    suspicious_phrases = (
        "the user is asking",
        "i need to check",
        "the backend data",
        "the tool executed was",
        "let me check",
        "the response has",
        "i should",
        "i need",
    )

    return any(
        phrase in lowered
        for phrase in suspicious_phrases
    )


# =========================================================
# Default route
# =========================================================

def default_route() -> dict:
    return {
        "tool": "none",
        "limit": 5,
        "urgency": "",
        "sku": "",
        "store_name": "",
        "topic": "",
        "active_sku": "",
        "active_store": "",
        "recent_entities": [],
    }

def default_conversation_context() -> dict:
    return {
        "last_tool": "none",
        "limit": 5,
        "urgency": "",
        "sku": "",
        "store_name": "",
        "topic": "",
        "active_sku": "",
        "active_store": "",
        "recent_entities": [],
    }


def normalize_conversation_context(
    context: dict | None,
) -> dict:
    normalized = (
        default_conversation_context()
    )

    if isinstance(
        context,
        dict,
    ):
        normalized.update(
            {
                key: context.get(
                    key,
                    default_value,
                )
                for key, default_value
                in normalized.items()
            }
        )

    return normalized


def route_to_context(
    route: dict,
) -> dict:
    return {
        "last_tool":
            route.get(
                "tool",
                "none",
            ),

        "limit":
            route.get(
                "limit",
                5,
            ),

        "urgency":
            route.get(
                "urgency",
                "",
            ),

        "sku":
            route.get(
                "sku",
                "",
            ),

        "store_name":
            route.get(
                "store_name",
                "",
            ),
        "topic":
            route.get(
                "topic",
                "",
             ),
        "active_sku":
            route.get(
                "active_sku",
                route.get(
                    "sku",
                    "",
                 ),
            ),

        "active_store":
            route.get(
                "active_store",
                route.get(
                    "store_name",
                    "",
                ),
            ),
        "recent_entities":
            route.get(
                "recent_entities",
                [],
            ),
    }

# =========================================================
# Deterministic routing
# =========================================================

def apply_deterministic_guards(
    user_message: str,
    route: dict,
) -> dict:
    lower_message = (
        user_message.lower()
    )

    allowed_tools = {
        "get_inventory_summary",
        "get_replenishment_priorities",
        "get_product_forecast",
        "get_sales_performance",
        "get_supplier_performance",
        "none",
    }

    if route.get(
        "tool"
    ) not in allowed_tools:
        route["tool"] = "none"

    # =====================================================
    # Normalize limit
    # =====================================================

    try:
        route["limit"] = max(
            1,
            min(
                int(
                    route.get(
                        "limit",
                        10,
                    )
                ),
                50,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):
        route["limit"] = 10

    route["urgency"] = str(
        route.get(
            "urgency",
            "",
        )
        or ""
    ).strip().lower()

    route["sku"] = str(
        route.get(
            "sku",
            "",
        )
        or ""
    ).strip()

    route["store_name"] = str(
        route.get(
            "store_name",
            "",
        )
        or ""
    ).strip()

    # =====================================================
    # SKU / Forecast
    # =====================================================

    sku_match = re.search(
        r"\bSKU-\d+\b",
        user_message,
        flags=re.IGNORECASE,
    )

    if sku_match:
        route["tool"] = (
            "get_product_forecast"
        )

        route["sku"] = (
            sku_match
            .group(0)
            .upper()
        )

    # =====================================================
    # Replenishment
    # =====================================================

    elif any(
        keyword in lower_message
        for keyword in (
            "commander",
            "commande",
            "commandes",
            "réapprovisionnement",
            "reapprovisionnement",
            "réapprovisionner",
            "reapprovisionner",
            "recommandation ml",
            "recommandations ml",
            "priorité",
            "priorite",
            "priorités",
            "priorites",
            "urgent",
            "urgents",
            "urgente",
            "urgentes",
            "risque de rupture",
            "plan ml",
        )
    ):
        route["tool"] = (
            "get_replenishment_priorities"
        )

    # =====================================================
    # Sales
    # =====================================================

    elif any(
        keyword in lower_message
        for keyword in (
            "chiffre d'affaires",
            "chiffre d’affaires",
            "ca total",
            "revenu",
            "revenus",
            "vente",
            "ventes",
            "vendu",
            "vendus",
            "vendue",
            "vendues",
            "plus vendu",
            "plus vendus",
            "meilleures ventes",
            "top produit",
            "top produits",
            "panier moyen",
            "marge",
            "transactions",
            "meilleur magasin",
            "meilleurs magasins",
            "magasin réalise",
            "magasin realise",
        )
    ):
        route["tool"] = (
            "get_sales_performance"
        )

    # =====================================================
    # Suppliers
    # =====================================================

    elif any(
        keyword in lower_message
        for keyword in (
            "fournisseur",
            "fournisseurs",
            "supplier",
            "suppliers",
            "livraison fournisseur",
            "livraisons fournisseur",
            "retard fournisseur",
            "retards fournisseur",
            "meilleur fournisseur",
            "meilleurs fournisseurs",
            "performance fournisseur",
            "performance des fournisseurs",
            "taux de livraison",
            "taux de fulfillment",
            "taux de service fournisseur",
            "problèmes de livraison",
            "problemes de livraison",
        )
    ):
        route["tool"] = (
            "get_supplier_performance"
        )

    # =====================================================
    # Inventory
    # =====================================================

    elif any(
        keyword in lower_message
        for keyword in (
            "état du stock",
            "etat du stock",
            "résumé du stock",
            "resume du stock",
            "stock actuel",
            "rupture de stock",
            "stock faible",
            "faible stock",
            "valeur du stock",
            "situation du stock",
        )
    ):
        route["tool"] = (
            "get_inventory_summary"
        )

    # =====================================================
    # Explicit urgency
    #
    # "les plus urgents" DOES NOT mean critical only.
    # =====================================================

    route["urgency"] = ""

    critical_patterns = (
        "priorité critique",
        "priorite critique",
        "priorités critiques",
        "priorites critiques",
        "niveau critique",
        "uniquement critique",
        "uniquement critiques",
        "urgence critique",
        "critical",
    )

    high_patterns = (
        "priorité élevée",
        "priorite elevee",
        "priorités élevées",
        "priorites elevees",
        "niveau élevé",
        "niveau eleve",
        "niveau high",
        "urgence élevée",
        "urgence elevee",
    )

    medium_patterns = (
        "priorité moyenne",
        "priorite moyenne",
        "priorités moyennes",
        "priorites moyennes",
        "niveau moyen",
        "niveau medium",
    )

    planned_patterns = (
        "priorité planifiée",
        "priorite planifiee",
        "priorités planifiées",
        "priorites planifiees",
        "niveau planned",
        "planifiée",
        "planifiee",
    )

    if any(
        pattern in lower_message
        for pattern in critical_patterns
    ):
        route["urgency"] = "critical"

    elif any(
        pattern in lower_message
        for pattern in high_patterns
    ):
        route["urgency"] = "high"

    elif any(
        pattern in lower_message
        for pattern in medium_patterns
    ):
        route["urgency"] = "medium"

    elif any(
        pattern in lower_message
        for pattern in planned_patterns
    ):
        route["urgency"] = "planned"

    # =====================================================
    # Numeric limit
    #
    # Examples:
    # - 5 produits les plus vendus
    # - 3 recommandations
    # - 3 fournisseurs
    # =====================================================

    if route["tool"] in {
        "get_replenishment_priorities",
        "get_sales_performance",
        "get_supplier_performance",
    }:
        limit_match = re.search(
            r"\b(\d{1,2})\b",
            user_message,
        )

        if limit_match:
            route["limit"] = max(
                1,
                min(
                    int(
                        limit_match.group(1)
                    ),
                    50,
                ),
            )

    return route


# =========================================================
# LLM Router
# =========================================================
def deterministic_route(
    user_message: str,
) -> dict:
    """
    Try to route known StockPilot business questions
    without calling the LLM.
    """

    route = default_route()

    route = apply_deterministic_guards(
        user_message,
        route,
    )

    return route
def extract_store_name(
    user_message: str,
) -> str:
    """
    Extract known demo store locations.

    Examples:
    - Rabat
    - Magasin Rabat
    - Casablanca
    """

    lower_message = (
        user_message
        .lower()
    )

    known_stores = {
        "rabat":
            "Rabat",

        "casablanca":
            "Casablanca",
    }

    for keyword, store_name in (
        known_stores.items()
    ):
        if re.search(
            rf"\b{re.escape(keyword)}\b",
            lower_message,
        ):
            return store_name

    return ""


def looks_like_follow_up(
    user_message: str,
) -> bool:
    lower_message = (
        user_message
        .strip()
        .lower()
    )

    follow_up_starts = (
        "et ",
        "et seulement",
        "et uniquement",
        "seulement ",
        "uniquement ",
        "garde ",
        "gardez ",
        "retire ",
        "retirez ",
        "enlève ",
        "enleve ",
        "enlevez ",
        "supprime ",
        "supprimez ",
        "sans ",
        "pour rabat",
        "pour casablanca",
        "à rabat",
        "a rabat",
        "à casablanca",
        "a casablanca",
        "les 3",
        "les 5",
    )

    return (
        lower_message.startswith(
            follow_up_starts
        )
       
    )

def apply_conversation_context(
    user_message: str,
    route: dict,
    context: dict | None,
) -> dict:
    """
    Merge the previous structured business context
    into a follow-up question.

    No LLM call is required.
    """

    context = (
        normalize_conversation_context(
            context
        )
    )

    lower_message = (
        user_message
        .lower()
    )

    previous_tool = (
        context.get(
            "last_tool",
            "none",
        )
    )

    # =====================================================
    # Follow-up inherits previous business tool
    # =====================================================

    if (
        route.get(
            "tool"
        ) == "none"
        and previous_tool != "none"
        and looks_like_follow_up(
            user_message
        )
    ):
        route["tool"] = (
            previous_tool
        )

        route["limit"] = (
            context.get(
                "limit",
                10,
            )
        )

        route["urgency"] = (
            context.get(
                "urgency",
                "",
            )
        )

        route["sku"] = (
            context.get(
                "sku",
                "",
            )
        )

        route["store_name"] = (
            context.get(
                "store_name",
                "",
            )
        )

    # =====================================================
    # Explicit store in new question
    # =====================================================

    explicit_store = (
        extract_store_name(
            user_message
        )
    )

    if explicit_store:
        route["store_name"] = (
            explicit_store
        )

    # =====================================================
    # Preserve previous store for natural follow-up
    # =====================================================

    elif (
        looks_like_follow_up(
            user_message
        )
        and not route.get(
            "store_name"
        )
        and context.get(
            "store_name"
        )
    ):
        route["store_name"] = (
            context[
                "store_name"
            ]
        )
    if (
        route.get("tool")
        == "get_product_forecast"
    ):
        if not route.get("sku"):
            route["sku"] = (
                context.get(
                    "active_sku",
                    "",
                )
                or context.get(
                    "sku",
                    "",
                )
            )

        if not route.get("store_name"):
            route["store_name"] = (
                context.get(
                    "active_store",
                    "",
                )
                or context.get(
                    "store_name",
                    "",
                )
            )
    # =====================================================
    # Explicit urgency
    # =====================================================

    if any(
        pattern in lower_message
        for pattern in (
            "critique",
            "critiques",
            "critical",
        )
    ):
        route["urgency"] = (
            "critical"
        )

    elif any(
        pattern in lower_message
        for pattern in (
            "priorité élevée",
            "priorite elevee",
            "niveau élevé",
            "niveau eleve",
            "high",
        )
    ):
        route["urgency"] = (
            "high"
        )

    elif any(
        pattern in lower_message
        for pattern in (
            "priorité moyenne",
            "priorite moyenne",
            "niveau moyen",
            "medium",
        )
    ):
        route["urgency"] = (
            "medium"
        )

    elif any(
        pattern in lower_message
        for pattern in (
            "planifiée",
            "planifiee",
            "planned",
        )
    ):
        route["urgency"] = (
            "planned"
        )

    # =====================================================
    # User explicitly removes urgency filter
    # =====================================================

    remove_urgency_patterns = (
        "toutes les priorités",
        "toutes les priorites",
        "sans filtre de priorité",
        "sans filtre de priorite",
        "retire le filtre critique",
        "retirez le filtre critique",
        "enlève le filtre critique",
        "enleve le filtre critique",
        "supprime le filtre critique",
        "supprimez le filtre critique",
        "sans filtre critique",
        "sans priorité critique",
        "sans priorite critique",
        "retire la priorité critique",
        "retire la priorite critique",
    )

    if any(
        phrase in lower_message
        for phrase in remove_urgency_patterns
    ):
        route["urgency"] = ""

    # =====================================================
    # Explicit limit
    # =====================================================

    limit_match = re.search(
        r"\b(\d{1,2})\b",
        user_message,
    )

    if (
        limit_match
        and route.get(
            "tool"
        ) in {
            "get_replenishment_priorities",
            "get_sales_performance",
            "get_supplier_performance",
        }
    ):
        route["limit"] = max(
            1,
            min(
                int(
                    limit_match.group(1)
                ),
                50,
            ),
        )

    return route
def route_user_request(
    user_message: str,
    context: dict | None = None,
) -> dict:
    # =====================================================
    # Native Qwen tool calling
    # =====================================================

    agent_route, agent_success = (
        agent_route_user_request(
            user_message=user_message,
            context=context,
        )
    )

    if agent_success:
        return agent_route

    # =====================================================
    # Legacy router below = emergency fallback
    # =====================================================
    """
    Fast hybrid router.

    1. Try deterministic Python routing first.
    2. Call Ollama only if Python cannot identify
       the business intent.
    """

    # =====================================================
    # FAST PATH
    # =====================================================

    fast_route = (
        apply_deterministic_guards(
            user_message,
            default_route(),
        )
    )

    fast_route = (
        apply_conversation_context(
            user_message=
                user_message,

            route=
                fast_route,

            context=
                context,
        )
    )

    if fast_route["tool"] != "none":
        return fast_route

    # =====================================================
    # LLM FALLBACK
    #
    # Used only for ambiguous / unknown questions.
    # =====================================================

    router_prompt = """
Tu es uniquement le routeur sécurisé de StockPilot AI.

Tu ne dois jamais répondre à la question métier.
Tu dois uniquement sélectionner un tool.

Tools disponibles :

1. get_inventory_summary

Pour :
- état du stock
- stock faible
- rupture
- stock critique
- valeur du stock


2. get_replenishment_priorities

Pour :
- commandes
- réapprovisionnement
- priorités
- recommandations ML
- risque de rupture


3. get_product_forecast

Pour :
- forecast
- prévision
- demande future
- prévision d'un SKU


4. get_sales_performance

Pour :
- chiffre d'affaires
- ventes
- marge
- panier moyen
- transactions
- produits vendus
- performance magasin


5. get_supplier_performance

Pour :
- fournisseurs
- performance fournisseurs
- retards
- problèmes de livraison
- meilleur fournisseur


6. none

Si aucun tool StockPilot n'est adapté.

Règles :

limit = 10 par défaut.
urgency = "" par défaut.
sku = "" par défaut.
store_name = "" par défaut.
"""

    route = default_route()

    try:
        payload = call_ollama(
            {
                "model": OLLAMA_MODEL,

                "messages": [
                    {
                        "role": "system",
                        "content": router_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_message,
                    },
                ],

                "stream": False,
                "think": False,

                "format": ROUTE_SCHEMA,

                "keep_alive": "30m",

                "options": {
                    "temperature": 0,
                    "num_predict": 80,
                },
            }
        )

        content = (
            payload
            .get(
                "message",
                {},
            )
            .get(
                "content",
                "",
            )
        )

        parsed_route = json.loads(
            content
        )

        if isinstance(
            parsed_route,
            dict,
        ):
            route.update(
                parsed_route
            )

    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        KeyError,
    ):
        route = default_route()

    route = (
        apply_deterministic_guards(
            user_message,
            route,
        )
    )   

    route = (
        apply_conversation_context(
            user_message=
                user_message,

            route=
                route,

            context=
                context,
        )
    )

    return route

def execute_route(
    route: dict,
) -> tuple[dict, dict]:
    tool_name = route[
        "tool"
    ]

    # =====================================================
    # Inventory
    # =====================================================

    if (
        tool_name
        == "get_inventory_summary"
    ):
        arguments = {}

        result = (
            get_inventory_summary()
        )

    # =====================================================
    # Replenishment
    # =====================================================

    elif (
        tool_name
        == "get_replenishment_priorities"
    ):
        arguments = {
            "limit":
                route["limit"],
        }

        if route["urgency"]:
            arguments[
                "urgency"
            ] = route[
                "urgency"
            ]
        if route["store_name"]:
            arguments[
                "store_name"
            ] = route[
                "store_name"
            ]

        result = (
            get_replenishment_priorities(
                **arguments
            )
        )

    # =====================================================
    # Forecast
    # =====================================================

    elif (
        tool_name
        == "get_product_forecast"
    ):
        if not route["sku"]:
            return (
                {
                    "error": (
                        "Aucun SKU valide "
                        "n'a été fourni."
                    )
                },
                {},
            )

        arguments = {
            "sku":
                route["sku"],
        }

        if route[
            "store_name"
        ]:
            arguments[
                "store_name"
            ] = route[
                "store_name"
            ]

        result = (
            get_product_forecast(
                **arguments
            )
        )

    # =====================================================
    # Sales
    # =====================================================

    elif (
        tool_name
        == "get_sales_performance"
    ):
        arguments = {
            "limit":
                route["limit"],
        }

        result = (
            get_sales_performance(
                **arguments
            )
        )

    # =====================================================
    # Suppliers
    # =====================================================

    elif (
        tool_name
        == "get_supplier_performance"
    ):
        arguments = {
            "limit":
                route["limit"],
        }

        result = (
            get_supplier_performance(
                **arguments
            )
        )
        # =====================================================
    # StockPilot capabilities
    # =====================================================

    elif (
        tool_name
        == "get_stockpilot_capabilities"
    ):
        arguments = {
            "topic":
                route.get(
                    "topic",
                    "overview",
                )
                or "overview",
        }

        result = (
            get_stockpilot_capabilities(
                **arguments
            )
        )
    else:
        return {}, {}

    return result, arguments

def execute_agent_plan(
    routes: list[dict],
) -> list[dict]:
    """
    Execute a validated StockPilot multi-tool plan.

    Each item contains:
    - tool name
    - validated arguments
    - route
    - verified backend result
    """

    executions = []

    # Security limit:
    # never execute an unlimited number
    # of LLM-generated calls.
    for route in routes[:5]:

        if not isinstance(
            route,
            dict,
        ):
            continue

        tool_name = route.get(
            "tool",
            "none",
        )

        if tool_name == "none":
            continue

        try:
            result, arguments = (
                execute_route(
                    route
                )
            )

            executions.append(
                {
                    "tool":
                        tool_name,

                    "arguments":
                        arguments,

                    "route":
                        route,

                    "result":
                        result,

                    "success":
                        not bool(
                            result.get(
                                "error"
                            )
                            if isinstance(
                                result,
                                dict,
                            )
                            else False
                        ),
                }
            )

        except Exception:
            executions.append(
                {
                    "tool":
                        tool_name,

                    "arguments":
                        {},

                    "route":
                        route,

                    "result": {
                        "error":
                            "Tool execution failed."
                    },

                    "success":
                        False,
                }
            )

    return executions
# =========================================================
# Deterministic fallback
# =========================================================
def build_locked_multi_tool_answer(
    user_message: str,
    executions: list[dict],
) -> str:
    """
    Combine several verified StockPilot tool results.

    Sensitive facts remain generated by the backend,
    not rewritten by the LLM.
    """

    sections = []

    for execution in executions:

        if not execution.get(
            "success",
            False,
        ):
            continue

        tool_name = execution.get(
            "tool",
            "none",
        )

        result = execution.get(
            "result",
            {},
        )

        locked_answer = (
            build_locked_business_answer(
                tool_name=tool_name,
                tool_result=result,
                user_message=user_message,
            )
        )

        # If this tool has no dedicated locked renderer yet,
        # use the deterministic fallback.
        if locked_answer is None:
            locked_answer = (
                fallback_business_answer(
                    tool_name=tool_name,
                    tool_result=result,
                    user_message=user_message,
                )
            )

        if locked_answer:
            sections.append(
                locked_answer
            )

    if not sections:
        return (
            "Je n'ai pas pu obtenir de données "
            "StockPilot exploitables pour cette demande."
        )

    return "\n\n---\n\n".join(
        sections
    )
def build_multi_tool_verified_evidence(
    executions: list[dict],
) -> list[dict]:
    """
    Build a compact verified evidence set
    for multi-tool LLM synthesis.

    The LLM must never receive raw database
    results when sanitized evidence exists.
    """

    evidence_items = []

    for execution in executions:

        if not execution.get(
            "success",
            False,
        ):
            continue

        tool_name = execution.get(
            "tool",
            "",
        )

        tool_result = execution.get(
            "result",
            {},
        )

        arguments = execution.get(
            "arguments",
            {},
        )

        verified_evidence = (
            build_verified_evidence(
                tool_name=tool_name,
                tool_result=tool_result,
            )
        )

        evidence_items.append(
            {
                "tool":
                    tool_name,

                "arguments":
                    arguments,

                "evidence":
                    verified_evidence,
            }
        )

    return evidence_items
def build_multi_tool_synthesis_evidence(
    executions: list[dict],
) -> dict:
    """
    Build a compact, authoritative evidence package
    specifically for multi-tool LLM synthesis.

    Only information useful for business synthesis
    is exposed to the LLM.
    """

    evidence = {}

    for execution in executions:

        if not execution.get(
            "success",
            False,
        ):
            continue

        tool_name = execution.get(
            "tool",
            "",
        )

        result = execution.get(
            "result",
            {},
        )

        arguments = execution.get(
            "arguments",
            {},
        )

        # =================================================
        # Sales
        # =================================================

        if tool_name == "get_sales_performance":

            summary = result.get(
                "summary",
                {},
            )

            stores = result.get(
                "stores",
                [],
            )

            best_store = (
                stores[0]
                if stores
                else {}
            )

            evidence["sales"] = {
                "period_start":
                    summary.get(
                        "start_date"
                    ),

                "period_end":
                    summary.get(
                        "end_date"
                    ),

                "net_revenue_mad":
                    summary.get(
                        "net_revenue"
                    ),

                "gross_margin_mad":
                    summary.get(
                        "gross_margin"
                    ),

                "gross_margin_rate_percentage":
                    summary.get(
                        "gross_margin_rate_percentage"
                    ),

                "total_quantity_sold":
                    summary.get(
                        "total_quantity_sold"
                    ),

                "transaction_count":
                    summary.get(
                        "transaction_count"
                    ),

                "average_basket_mad":
                    summary.get(
                        "average_basket_value"
                    ),

                "best_store_by_revenue": {
                    "store_name":
                        best_store.get(
                            "store_name"
                        ),

                    "net_revenue_mad":
                        best_store.get(
                            "net_revenue"
                        ),
                },
            }

        # =================================================
        # Suppliers
        # =================================================

        elif tool_name == "get_supplier_performance":

            summary = result.get(
                "summary",
                {},
            )

            suppliers_at_risk = result.get(
                "suppliers_at_risk",
                [],
            )

            limit = int(
                arguments.get(
                    "limit",
                    5,
                )
                or 5
            )

            limit = max(
                1,
                min(
                    limit,
                    5,
                ),
            )

            risk_items = []

            for supplier in (
                suppliers_at_risk[:limit]
            ):
                risk_items.append(
                    {
                        "supplier_name":
                            supplier.get(
                                "supplier_name"
                            ),

                        "supplier_code":
                            supplier.get(
                                "supplier_code"
                            ),

                        "on_time_delivery_rate_percentage":
                            supplier.get(
                                "on_time_delivery_rate_percentage"
                            ),

                        "late_deliveries":
                            supplier.get(
                                "late_deliveries"
                            ),

                        "average_delivery_delay_days":
                            supplier.get(
                                "average_delivery_delay_days"
                            ),

                        "supplier_score":
                            supplier.get(
                                "supplier_score"
                            ),
                    }
                )

            evidence["suppliers"] = {
                "supplier_count":
                    summary.get(
                        "supplier_count"
                    ),

                "average_supplier_score":
                    summary.get(
                        "average_supplier_score"
                    ),

                "average_on_time_delivery_rate_percentage":
                    summary.get(
                        "average_on_time_delivery_rate_percentage"
                    ),

                "average_fulfillment_rate_percentage":
                    summary.get(
                        "average_fulfillment_rate_percentage"
                    ),

                "total_late_deliveries":
                    summary.get(
                        "total_late_deliveries"
                    ),

                "suppliers_at_risk":
                    risk_items,
            }

        # =================================================
        # Inventory
        # =================================================

        elif tool_name == "get_inventory_summary":

            critical = int(
                result.get(
                    "critical_count",
                    0,
                )
            )

            out_of_stock = int(
                result.get(
                    "out_of_stock_count",
                    0,
                )
            )

            low_stock = int(
                result.get(
                    "low_stock_count",
                    0,
                )
            )

            total = int(
                result.get(
                    "total_positions",
                    0,
                )
            )

            attention = (
                critical
                + out_of_stock
                + low_stock
            )

            attention_rate = (
                round(
                    attention
                    / total
                    * 100,
                    1,
                )
                if total
                else 0
            )

            evidence["inventory"] = {
                "total_positions":
                    total,

                "critical":
                    critical,

                "out_of_stock":
                    out_of_stock,

                "low_stock":
                    low_stock,

                "healthy":
                    result.get(
                        "healthy_count",
                        0,
                    ),

                "overstock":
                    result.get(
                        "overstock_count",
                        0,
                    ),

                "attention_positions":
                    attention,

                "attention_rate_percentage":
                    attention_rate,

                "stock_value_at_cost_mad":
                    result.get(
                        "stock_value_at_cost",
                        0,
                    ),
            }

        # =================================================
        # Replenishment
        # =================================================

        elif tool_name == "get_replenishment_priorities":

            recommendations = result.get(
                "recommendations",
                [],
            )

            compact_recommendations = []

            for index, item in enumerate(
                recommendations,
                start=1,
            ):
                compact_recommendations.append(
                    {
                        "rank":
                            index,

                        "sku":
                            item.get(
                                "sku"
                            ),

                        "store_name":
                            item.get(
                                "store_name"
                            ),

                        "urgency":
                            item.get(
                                "urgency_level"
                            ),

                        "recommended_order_quantity":
                            item.get(
                                "recommended_order_quantity"
                            ),

                        "forecast_30d":
                            item.get(
                                "forecast_30d"
                            ),

                        "estimated_stockout_date":
                            item.get(
                                "estimated_stockout_date"
                            ),
                    }
                )

            evidence["replenishment"] = {
                "ranking_is_authoritative":
                    True,

                "recommendations":
                    compact_recommendations,
            }

        # =================================================
        # Forecast
        # =================================================

        elif tool_name == "get_product_forecast":

            stores = []

            for store in result.get(
                "stores",
                [],
            ):
                stores.append(
                    {
                        "store_name":
                            store.get(
                                "store_name"
                            ),

                        "forecast_total":
                            store.get(
                                "forecast_total"
                            ),
                    }
                )

            evidence["forecast"] = {
                "sku":
                    result.get(
                        "sku"
                    ),

                "product_name":
                    result.get(
                        "product_name"
                    ),

                "forecast_total":
                    result.get(
                        "forecast_total"
                    ),

                "horizon_days":
                    result.get(
                        "horizon_days"
                    ),

                "forecast_start_date":
                    result.get(
                        "forecast_start_date"
                    ),

                "forecast_end_date":
                    result.get(
                        "forecast_end_date"
                    ),

                "stores":
                    stores,
            }

        # =================================================
        # StockPilot capabilities
        # =================================================

        elif tool_name == "get_stockpilot_capabilities":

            evidence["stockpilot_capabilities"] = {
                "topic":
                    result.get(
                        "topic"
                    ),

                "supported":
                    result.get(
                        "supported"
                    ),

                "statement":
                    result.get(
                        "statement"
                    ),
            }

    return evidence

def generate_multi_tool_synthesis(
    user_message: str,
    executions: list[dict],
) -> str:
    """
    Generate a short business synthesis from
    compact verified multi-tool evidence.

    Exact numerical details remain handled by
    deterministic backend renderers.
    """

    evidence = (
        build_multi_tool_synthesis_evidence(
            executions
        )
    )

    if not evidence:
        return ""

    evidence_json = json.dumps(
        evidence,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    system_prompt = """
Tu es StockPilot AI.

Tu dois produire une synthèse métier courte à partir
UNIQUEMENT des faits contenus dans EVIDENCE_JSON.

RÈGLES STRICTES :

- Utilise uniquement les informations présentes
  dans EVIDENCE_JSON.
- N'invente aucun fait.
- N'invente aucune cause.
- N'invente aucune tendance historique.
- N'invente aucune fonctionnalité StockPilot.
- N'invente aucun délai ou fréquence de mise à jour.
- Ne donne aucun nouveau conseil qui n'est pas
  directement supporté par les faits fournis.
- Ne recalcule pas de nouveaux KPI.
- Ne modifie jamais un classement fourni.
- Si un classement de réapprovisionnement est marqué
  authoritative, respecte exactement son ordre.
- Si une liste suppliers_at_risk est fournie,
  respecte son ordre.
- Ne donne pas de valeurs quantitatives précises
  dans la synthèse. Les détails chiffrés seront
  affichés séparément par le backend.
- Les identifiants comme SKU-00105 sont autorisés.
- Tu peux citer les noms de magasins,
  produits ou fournisseurs présents dans les faits.
- Fais une synthèse de 2 à 4 phrases maximum.
- Pas de titre.
- Pas de liste.
- Pas de tableau.
- Réponds en français.
- Ne révèle jamais ton raisonnement interne.

La synthèse doit aider un responsable métier
à comprendre rapidement les principaux constats,
sans remplacer les détails factuels affichés ensuite.
"""

    payload = call_ollama(
        {
            "model":
                OLLAMA_MODEL,

            "messages": [
                {
                    "role":
                        "system",

                    "content":
                        system_prompt,
                },
                {
                    "role":
                        "user",

                    "content": (
                        f"Question utilisateur :\n"
                        f"{user_message}\n\n"
                        f"EVIDENCE_JSON :\n"
                        f"{evidence_json}"
                    ),
                },
            ],

            "stream":
                False,

            "think":
                False,

            "keep_alive":
                "30m",

            "options": {
                "temperature":
                    0.1,

                "num_predict":
                    180,
            },
        }
    )

    content = (
        payload
        .get(
            "message",
            {},
        )
        .get(
            "content",
            "",
        )
    )

    cleaned = (
        clean_model_answer(
            content
        )
    )

    if (
        not cleaned
        or contains_reasoning_leak(
            cleaned
        )
    ):
        return ""

    return cleaned
def build_multi_tool_verified_insights(
    executions: list[dict],
) -> list[str]:
    """
    Build business insights that are already
    factually validated by the backend.

    The LLM may reformulate or connect them,
    but must not derive new conclusions.
    """

    insights: list[str] = []

    for execution in executions:

        if not execution.get(
            "success",
            False,
        ):
            continue

        tool_name = execution.get(
            "tool",
            "",
        )

        result = execution.get(
            "result",
            {},
        )

        # =================================================
        # Sales
        # =================================================

        if (
            tool_name
            == "get_sales_performance"
        ):

            stores = result.get(
                "stores",
                [],
            )

            if stores:

                best_store = stores[0]

                store_name = (
                    best_store.get(
                        "store_name",
                        "",
                    )
                )

                if store_name:

                    insights.append(
                        (
                            f"{store_name} est le magasin "
                            "générant le plus de chiffre "
                            "d'affaires dans les données "
                            "analysées."
                        )
                    )

            insights.append(
                (
                    "Les données commerciales disponibles "
                    "permettent d'analyser le chiffre "
                    "d'affaires, les volumes vendus, "
                    "les transactions et la marge."
                )
            )

        # =================================================
        # Suppliers
        # =================================================

        elif (
            tool_name
            == "get_supplier_performance"
        ):

            suppliers_at_risk = (
                result.get(
                    "suppliers_at_risk",
                    [],
                )
            )

            top_three = (
                suppliers_at_risk[:3]
            )

            names = [
                supplier.get(
                    "supplier_name"
                )
                for supplier
                in top_three
                if supplier.get(
                    "supplier_name"
                )
            ]

            if names:

                insights.append(
                    (
                        "Les fournisseurs nécessitant "
                        "le plus d'attention parmi ceux "
                        "classés à risque sont, dans "
                        "l'ordre : "
                        + ", ".join(names)
                        + "."
                    )
                )

            

        # =================================================
        # Inventory
        # =================================================

        elif (
            tool_name
            == "get_inventory_summary"
        ):

            critical = int(
                result.get(
                    "critical_count",
                    0,
                )
                or 0
            )

            out_of_stock = int(
                result.get(
                    "out_of_stock_count",
                    0,
                )
                or 0
            )

            low_stock = int(
                result.get(
                    "low_stock_count",
                    0,
                )
                or 0
            )

            total_positions = int(
                result.get(
                    "total_positions",
                    0,
                )
                or 0
            )

            attention_positions = (
                critical
                + out_of_stock
                + low_stock
            )

            if (
                total_positions > 0
                and attention_positions > 0
            ):

                attention_rate = (
                    attention_positions
                    / total_positions
                )

                if attention_rate >= 0.5:

                    insights.append(
                        (
                            "Une part importante des "
                            "positions de stock nécessite "
                            "actuellement une attention "
                            "particulière."
                        )
                    )

                else:

                    insights.append(
                        (
                            "Certaines positions de stock "
                            "nécessitent actuellement une "
                            "attention particulière."
                        )
                    )

        # =================================================
        # Replenishment
        # =================================================

        elif (
            tool_name
            == "get_replenishment_priorities"
        ):

            recommendations = (
                result.get(
                    "recommendations",
                    [],
                )
            )

            if recommendations:

                first = recommendations[0]

                sku = (
                    first.get(
                        "sku",
                        "",
                    )
                )

                store_name = (
                    first.get(
                        "store_name",
                        "",
                    )
                )

                if (
                    sku
                    and store_name
                ):

                    insights.append(
                        (
                            f"{sku} au {store_name} est "
                            "la première priorité dans "
                            "le classement de "
                            "réapprovisionnement ML."
                        )
                    )

                top_skus = [
                    item.get(
                        "sku"
                    )
                    for item
                    in recommendations[:3]
                    if item.get(
                        "sku"
                    )
                ]

                if top_skus:

                    insights.append(
                        (
                            "L'ordre des premières "
                            "priorités ML est : "
                            + ", ".join(
                                top_skus
                            )
                            + "."
                        )
                    )

        # =================================================
        # Product forecast
        # =================================================

        elif (
            tool_name
            == "get_product_forecast"
        ):

            if not result.get(
                "found",
                False,
            ):
                continue

            sku = result.get(
                "sku",
                "",
            )

            stores = result.get(
                "stores",
                [],
            )

            if sku:

                if len(stores) == 1:

                    store_name = (
                        stores[0].get(
                            "store_name",
                            "",
                        )
                    )

                    if store_name:

                        insights.append(
                            (
                                f"Une prévision de demande "
                                f"est disponible pour {sku} "
                                f"au {store_name}."
                            )
                        )

                elif len(stores) > 1:

                    insights.append(
                        (
                            f"Une prévision de demande "
                            f"est disponible pour {sku} "
                            "sur plusieurs magasins."
                        )
                    )

                else:

                    insights.append(
                        (
                            f"Une prévision de demande "
                            f"est disponible pour {sku}."
                        )
                    )

        # =================================================
        # StockPilot capabilities
        # =================================================

        elif (
            tool_name
            == "get_stockpilot_capabilities"
        ):

            statement = result.get(
                "statement",
                "",
            )

            if statement:
                insights.append(
                    statement
                )

    return insights


def generate_multi_tool_synthesis(
    user_message: str,
    executions: list[dict],
) -> str:
    """
    Generate a short natural-language synthesis
    from backend-verified business insights.

    The LLM is only allowed to reformulate and
    connect already validated insights.
    """

    insights = (
        build_multi_tool_verified_insights(
            executions
        )
    )

    if not insights:
        return ""

    insights_text = "\n".join(
        f"- {insight}"
        for insight
        in insights
    )

    system_prompt = """
Tu es StockPilot AI.

Tu dois rédiger une synthèse métier courte et naturelle
à partir UNIQUEMENT des constats contenus dans
VERIFIED_INSIGHTS.

Chaque constat a déjà été vérifié par le backend
StockPilot et constitue une source de vérité.

RÈGLES STRICTES :

- Tu peux reformuler les constats.
- Tu peux relier plusieurs constats entre eux.
- Tu ne dois ajouter aucun nouveau fait.
- Tu ne dois effectuer aucun calcul.
- Tu ne dois créer aucune nouvelle comparaison.
- Tu ne dois inventer aucune cause.
- Tu ne dois inventer aucune tendance.
- Tu ne dois inventer aucune recommandation.
- Tu ne dois ajouter aucun chiffre absent des constats.
- Si les constats ne contiennent aucun chiffre,
  ta réponse ne doit contenir aucun chiffre.
- Tu ne dois modifier aucun classement.
- Tu ne dois modifier aucun ordre fourni.
- Tu ne dois ajouter aucun produit, SKU, magasin
  ou fournisseur absent des constats.
- Tu ne dois présenter aucune hypothèse comme un fait.
- Tu ne dois ajouter aucune information sur
  l'architecture ou le fonctionnement de StockPilot.
- Fais une synthèse de 2 à 4 phrases maximum.
- Pas de titre.
- Pas de liste.
- Pas de tableau.
- Réponds en français.
- Sois naturel, professionnel et concis.
- Ne révèle jamais ton raisonnement interne.

Ton rôle est uniquement de rendre les constats
vérifiés plus faciles à comprendre.
"""

    payload = call_ollama(
        {
            "model":
                OLLAMA_MODEL,

            "messages": [
                {
                    "role":
                        "system",

                    "content":
                        system_prompt,
                },
                {
                    "role":
                        "user",

                    "content": (
                        f"Question utilisateur :\n"
                        f"{user_message}\n\n"
                        f"VERIFIED_INSIGHTS :\n"
                        f"{insights_text}"
                    ),
                },
            ],

            "stream":
                False,

            "think":
                False,

            "keep_alive":
                "30m",

            "options": {
                "temperature":
                    0.1,

                "num_predict":
                    160,
            },
        }
    )

    content = (
        payload
        .get(
            "message",
            {},
        )
        .get(
            "content",
            "",
        )
    )

    cleaned = (
        clean_model_answer(
            content
        )
    )

    if (
        not cleaned
        or contains_reasoning_leak(
            cleaned
        )
    ):
        return ""

    return cleaned
def fallback_business_answer(
    tool_name: str,
    tool_result: dict,
    user_message: str = "",
) -> str:
    lower_message = (
        user_message.lower()
    )

    # =====================================================
    # Inventory
    # =====================================================

    if (
        tool_name
        == "get_inventory_summary"
    ):
        critical = int(
            tool_result.get(
                "critical_count",
                0,
            )
        )

        out_of_stock = int(
            tool_result.get(
                "out_of_stock_count",
                0,
            )
        )

        low_stock = int(
            tool_result.get(
                "low_stock_count",
                0,
            )
        )

        healthy = int(
            tool_result.get(
                "healthy_count",
                0,
            )
        )

        overstock = int(
            tool_result.get(
                "overstock_count",
                0,
            )
        )

        stock_value = (
            format_number_fr(
                tool_result.get(
                    "stock_value_at_cost",
                    0,
                )
            )
        )

        return (
            "État actuel du stock : "
            f"{critical} critique(s), "
            f"{out_of_stock} en rupture, "
            f"{low_stock} à stock faible, "
            f"{healthy} en bonne santé et "
            f"{overstock} en surstock. "
            f"La valeur du stock au coût est de "
            f"{stock_value} MAD."
        )

    # =====================================================
    # Replenishment
    # =====================================================

    if (
        tool_name
        == "get_replenishment_priorities"
    ):
        recommendations = (
            tool_result.get(
                "recommendations",
                [],
            )
        )

        if not recommendations:
            urgency = tool_result.get(
                "urgency_filter",
                "",
            )

            store_name = tool_result.get(
                "store_filter",
                "",
            )

            urgency_label = (
                URGENCY_LABELS.get(
                    urgency,
                    urgency,
                )
                if urgency
                else ""
            )

            if urgency_label and store_name:
                return (
                    "Aucune recommandation de priorité "
                    f"{urgency_label} n'a été trouvée "
                    f"pour le Magasin {store_name}."
                )

            if urgency_label:
                return (
                    "Aucune recommandation de priorité "
                    f"{urgency_label} n'a été trouvée."
                )

            if store_name:
                return (
                    "Aucune recommandation de "
                    "réapprovisionnement n'a été trouvée "
                    f"pour le Magasin {store_name}."
                )

            return (
                "Aucune recommandation de "
                "réapprovisionnement correspondant "
                "aux critères demandés n'a été trouvée."
            )

        lines = [
            "Priorités de réapprovisionnement ML :"
        ]

        for index, item in enumerate(
            recommendations,
            start=1,
        ):
            quantity = item.get(
                "recommended_order_quantity",
                0,
            )

            if isinstance(
                quantity,
                float,
            ) and quantity.is_integer():
                quantity = int(
                    quantity
                )

            stockout_date = (
                item.get(
                    "estimated_stockout_date"
                )
                or "non estimée"
            )

            urgency_level = (
                item.get(
                    "urgency_level",
                    "",
                )
            )

            urgency_label = (
                URGENCY_LABELS.get(
                    urgency_level,
                    urgency_level,
                )
                or "N/A"
            )

            lines.append(
                f"{index}. "
                f"{item.get('sku', 'N/A')} — "
                f"{item.get('product_name', 'N/A')} — "
                f"{item.get('store_name', 'N/A')} : "
                f"priorité {urgency_label}, "
                f"{quantity} unités recommandées, "
                f"rupture estimée le {stockout_date}."
            )

        lines.append(
            "Ces recommandations ML sont des aides "
            "à la décision et ne déclenchent pas "
            "automatiquement une commande."
        )

        return "\n".join(
            lines
        )

    # =====================================================
    # Product forecast
    # =====================================================

    if (
        tool_name
        == "get_product_forecast"
    ):
        if not tool_result.get(
            "found",
            False,
        ):
            return (
                "Aucune prévision n'a été trouvée "
                "pour le SKU et le magasin demandés."
            )

        sku = tool_result.get(
            "sku",
            "N/A",
        )

        product_name = (
            tool_result.get(
                "product_name",
                "Produit inconnu",
            )
        )

        total = float(
            tool_result.get(
                "forecast_total",
                0,
            )
        )

        forecast_start_date = (
            tool_result.get(
                "forecast_start_date",
                "N/A",
            )
        )

        forecast_end_date = (
            tool_result.get(
                "forecast_end_date",
                "N/A",
            )
        )

        horizon_days = (
            tool_result.get(
                "horizon_days",
                30,
            )
        )

        stores = tool_result.get(
            "stores",
            [],
        )

        if len(stores) == 1:
            store_name = (
                stores[0].get(
                    "store_name",
                    "Magasin inconnu",
                )
            )

            store_total = float(
                stores[0].get(
                    "forecast_total",
                    total,
                )
            )

            return (
                f"La demande prévue pour {sku} "
                f"({product_name}) au {store_name} "
                f"est de "
                f"{format_number_fr(store_total)} unités "
                f"sur {horizon_days} jours, "
                f"du {forecast_start_date} "
                f"au {forecast_end_date}."
            )

        if len(stores) > 1:
            lines = [
                (
                    f"La demande totale prévue pour "
                    f"{sku} ({product_name}) est de "
                    f"{format_number_fr(total)} unités "
                    f"sur {horizon_days} jours."
                )
            ]

            for store in stores:
                store_name = (
                    store.get(
                        "store_name",
                        "Magasin inconnu",
                    )
                )

                store_total = float(
                    store.get(
                        "forecast_total",
                        0,
                    )
                )

                lines.append(
                    f"- {store_name} : "
                    f"{format_number_fr(store_total)} unités"
                )

            lines.append(
                f"Période : "
                f"{forecast_start_date} "
                f"au {forecast_end_date}."
            )

            return "\n".join(
                lines
            )

        return (
            f"La demande prévue pour {sku} "
            f"est de "
            f"{format_number_fr(total)} unités."
        )

    # =====================================================
    # Sales
    # =====================================================

    if (
        tool_name
        == "get_sales_performance"
    ):
        summary = tool_result.get(
            "summary",
            {},
        )

        top_quantity = (
            tool_result.get(
                "top_products_by_quantity",
                [],
            )
        )

        top_revenue = (
            tool_result.get(
                "top_products_by_revenue",
                [],
            )
        )

        stores = tool_result.get(
            "stores",
            [],
        )

        # -------------------------------------------------
        # Top products by quantity
        # -------------------------------------------------

        if (
            "plus vendu" in lower_message
            or "plus vendus" in lower_message
            or "meilleures ventes" in lower_message
        ):
            if not top_quantity:
                return (
                    "Aucune donnée de vente produit "
                    "n'est disponible."
                )

            lines = [
                "Produits les plus vendus :"
            ]

            for index, product in enumerate(
                top_quantity,
                start=1,
            ):
                quantity = int(
                    product.get(
                        "quantity_sold",
                        0,
                    )
                )

                lines.append(
                    f"{index}. "
                    f"{product.get('sku', 'N/A')} — "
                    f"{product.get('product_name', 'N/A')} : "
                    f"{quantity:,} unités vendues."
                    .replace(",", " ")
                )

            return "\n".join(
                lines
            )

        # -------------------------------------------------
        # Top products by revenue
        # -------------------------------------------------

        if (
            "produit" in lower_message
            and (
                "chiffre d'affaires"
                in lower_message
                or "chiffre d’affaires"
                in lower_message
                or "revenu"
                in lower_message
            )
        ):
            if not top_revenue:
                return (
                    "Aucune donnée de chiffre d'affaires "
                    "par produit n'est disponible."
                )

            lines = [
                (
                    "Produits générant le plus "
                    "de chiffre d'affaires :"
                )
            ]

            for index, product in enumerate(
                top_revenue,
                start=1,
            ):
                revenue = (
                    format_number_fr(
                        product.get(
                            "net_revenue",
                            0,
                        )
                    )
                )

                lines.append(
                    f"{index}. "
                    f"{product.get('sku', 'N/A')} — "
                    f"{product.get('product_name', 'N/A')} : "
                    f"{revenue} MAD."
                )

            return "\n".join(
                lines
            )

        # -------------------------------------------------
        # Best store
        # -------------------------------------------------

        if (
            "magasin" in lower_message
            and (
                "chiffre d'affaires"
                in lower_message
                or "chiffre d’affaires"
                in lower_message
                or "meilleur" in lower_message
                or "plus de revenu" in lower_message
            )
        ):
            if not stores:
                return (
                    "Aucune performance par magasin "
                    "n'est disponible."
                )

            store = stores[0]

            revenue = (
                format_number_fr(
                    store.get(
                        "net_revenue",
                        0,
                    )
                )
            )

            margin = (
                format_number_fr(
                    store.get(
                        "gross_margin",
                        0,
                    )
                )
            )

            return (
                f"Le magasin réalisant le plus de "
                f"chiffre d'affaires est "
                f"{store.get('store_name', 'N/A')} "
                f"avec {revenue} MAD, "
                f"pour une marge brute de "
                f"{margin} MAD."
            )

        # -------------------------------------------------
        # Global commercial summary
        # -------------------------------------------------

        revenue = (
            format_number_fr(
                summary.get(
                    "net_revenue",
                    0,
                )
            )
        )

        quantity = int(
            summary.get(
                "total_quantity_sold",
                0,
            )
        )

        transactions = int(
            summary.get(
                "transaction_count",
                0,
            )
        )

        basket = (
            format_number_fr(
                summary.get(
                    "average_basket_value",
                    0,
                )
            )
        )

        margin = (
            format_number_fr(
                summary.get(
                    "gross_margin",
                    0,
                )
            )
        )

        margin_rate = (
            format_number_fr(
                summary.get(
                    "gross_margin_rate_percentage",
                    0,
                )
            )
        )

        quantity_formatted = (
            f"{quantity:,}"
            .replace(",", " ")
        )

        transactions_formatted = (
            f"{transactions:,}"
            .replace(",", " ")
        )

        return (
            "Performance commerciale :\n"
            f"- Chiffre d'affaires : {revenue} MAD\n"
            f"- Quantité vendue : "
            f"{quantity_formatted} unités\n"
            f"- Transactions : "
            f"{transactions_formatted}\n"
            f"- Panier moyen : {basket} MAD\n"
            f"- Marge brute : {margin} MAD "
            f"({margin_rate} %)"
        )
    # =====================================================
    # Suppliers
    # =====================================================

    if (
        tool_name
        == "get_supplier_performance"
    ):
        summary = tool_result.get(
            "summary",
            {},
        )

        best_suppliers = (
            tool_result.get(
                "best_suppliers",
                [],
            )
        )

        suppliers_at_risk = (
            tool_result.get(
                "suppliers_at_risk",
                [],
            )
        )

        # -------------------------------------------------
        # Delivery problems / suppliers at risk
        # -------------------------------------------------

        if any(
            expression in lower_message
            for expression in (
                "problème",
                "problèmes",
                "probleme",
                "problemes",
                "retard",
                "retards",
                "moins performant",
                "moins performants",
                "pire fournisseur",
                "pires fournisseurs",
                "à risque",
                "a risque",
            )
        ):
            if not suppliers_at_risk:
                return (
                    "Aucune donnée fournisseur "
                    "n'est disponible."
                )

            lines = [
                (
                    "Fournisseurs présentant le plus "
                    "de problèmes de livraison :"
                )
            ]

            for index, supplier in enumerate(
                suppliers_at_risk,
                start=1,
            ):
                on_time_rate = float(
                    supplier.get(
                        "on_time_delivery_rate_percentage",
                        0,
                    )
                )

                late = int(
                    supplier.get(
                        "late_deliveries",
                        0,
                    )
                )

                delay = float(
                    supplier.get(
                        "average_delivery_delay_days",
                        0,
                    )
                )

                score = float(
                    supplier.get(
                        "supplier_score",
                        0,
                    )
                )

                tier = (
                    supplier.get(
                        "supplier_performance_tier",
                        "",
                    )
                )

                tier_label = (
                    SUPPLIER_TIER_LABELS.get(
                        tier,
                        tier,
                    )
                    or "N/A"
                )

                lines.append(
                    f"{index}. "
                    f"{supplier.get('supplier_name', 'N/A')} "
                    f"({supplier.get('supplier_code', 'N/A')}) : "
                    f"{format_number_fr(on_time_rate)} % "
                    f"de livraisons à temps, "
                    f"{late} livraisons en retard, "
                    f"{format_number_fr(delay)} jours "
                    f"de retard moyen, "
                    f"score {format_number_fr(score)}/100, "
                    f"niveau {tier_label}."
                )

            return "\n".join(
                lines
            )

        # -------------------------------------------------
        # Best suppliers
        # -------------------------------------------------

        if (
            "meilleur fournisseur"
            in lower_message
            or "meilleurs fournisseurs"
            in lower_message
        ):
            if not best_suppliers:
                return (
                    "Aucune donnée fournisseur "
                    "n'est disponible."
                )

            lines = [
                "Meilleurs fournisseurs :"
            ]

            for index, supplier in enumerate(
                best_suppliers,
                start=1,
            ):
                score = float(
                    supplier.get(
                        "supplier_score",
                        0,
                    )
                )

                on_time = float(
                    supplier.get(
                        "on_time_delivery_rate_percentage",
                        0,
                    )
                )

                fulfillment = float(
                    supplier.get(
                        "quantity_fulfillment_rate_percentage",
                        0,
                    )
                )

                tier = (
                    supplier.get(
                        "supplier_performance_tier",
                        "",
                    )
                )

                tier_label = (
                    SUPPLIER_TIER_LABELS.get(
                        tier,
                        tier,
                    )
                    or "N/A"
                )

                lines.append(
                    f"{index}. "
                    f"{supplier.get('supplier_name', 'N/A')} "
                    f"({supplier.get('supplier_code', 'N/A')}) : "
                    f"score {format_number_fr(score)}/100, "
                    f"{format_number_fr(on_time)} % à temps, "
                    f"{format_number_fr(fulfillment)} % "
                    f"de fulfillment, "
                    f"niveau {tier_label}."
                )

            return "\n".join(
                lines
            )

        # -------------------------------------------------
        # Global supplier summary
        # -------------------------------------------------

        supplier_count = int(
            summary.get(
                "supplier_count",
                0,
            )
        )

        average_score = float(
            summary.get(
                "average_supplier_score",
                0,
            )
        )

        on_time = float(
            summary.get(
                "average_on_time_delivery_rate_percentage",
                0,
            )
        )

        fulfillment = float(
            summary.get(
                "average_fulfillment_rate_percentage",
                0,
            )
        )

        late = int(
            summary.get(
                "total_late_deliveries",
                0,
            )
        )

        late_formatted = (
            f"{late:,}"
            .replace(",", " ")  
        )

    return (
        f"Vous avez {supplier_count} fournisseurs. "
        f"Le score moyen est de "
        f"{format_number_fr(average_score)}/100, "
        f"le taux moyen de livraison à temps est de "
        f"{format_number_fr(on_time)} %, "
        f"le taux de fulfillment est de "
        f"{format_number_fr(fulfillment)} % "
        f"et {late_formatted} livraisons en retard "
        f"ont été enregistrées."
    )

    return (
        "Les données ont bien été récupérées, "
        "mais aucune présentation adaptée "
        "n'est disponible."
    )

TOOL_SEMANTICS = {
    "get_inventory_summary": """
Ce tool décrit la santé actuelle du stock.

IMPORTANT :

Les comptages représentent des positions
produit-magasin et NON nécessairement
des produits uniques.

- critical = positions critiques
- out_of_stock = positions en rupture
- low_stock = positions à stock faible
- healthy = positions saines
- overstock = positions en surstock

stock_value_at_cost_mad =
valeur totale du stock au coût.

historical_recommended_order_quantity =
quantité recommandée agrégée issue du mart historique.

IMPORTANT :
Ce champ n'est PAS un seuil de commande.

Ne propose pas automatiquement :
- promotion
- réduction
- liquidation
- transfert de stock

sauf si l'utilisateur le demande explicitement
et que les données disponibles permettent
de justifier cette recommandation.

Présente les faits avant toute interprétation.
""",
}
def build_locked_business_answer(
    tool_name: str,
    tool_result: dict,
    user_message: str = "",
) -> str | None:
    """
    Build authoritative business answers for data where
    ordering / classification must never be changed by the LLM.
    """
        # =====================================================
    # Supplier performance
    # =====================================================
    # =====================================================
# Product forecast
# =====================================================

    if (
        tool_name
        == "get_product_forecast"
    ):
        return (
            fallback_business_answer(
                tool_name=
                    tool_name,

                tool_result=
                    tool_result,

                user_message=
                    user_message,
            )
        )
    if (
        tool_name
        == "get_supplier_performance"
    ):
        return (
            fallback_business_answer(
                tool_name=
                    tool_name,

                tool_result=
                    tool_result,

                user_message=
                    user_message,
            )
        )
    if (
        tool_name
        == "get_sales_performance"
    ):
        return (
            fallback_business_answer(
                tool_name=
                    tool_name,

                tool_result=
                    tool_result,

                user_message=
                    user_message,
            )
        )

    if (
        tool_name
        == "get_stockpilot_capabilities"
    ):
        topic = tool_result.get(
            "topic",
            "overview",
        )

        statement = tool_result.get(
            "statement",
            "",
        )

        if statement:
            return statement

        features = tool_result.get(
            "available_features",
            [],
        )

        if features:
            lines = [
                "StockPilot propose actuellement :",
                "",
            ]

            for feature in features:
                lines.append(
                    f"- {feature}"
                )

            lines.extend(
                [
                    "",
                    (
                        "StockPilot est une plateforme "
                        "d'aide à la décision : ses "
                        "recommandations ne déclenchent "
                        "pas automatiquement des actions."
                    ),
                ]
            )

            return "\n".join(lines)

        return (
            "Aucune information officielle "
            "n'est disponible pour cette capacité."
        )
    if (
        tool_name
        == "get_inventory_summary"
    ):
        total = int(
            tool_result.get(
                "product_store_count",
                0,
            )
            or 0
        )

        critical = int(
            tool_result.get(
                "critical_count",
                0,
            )
            or 0
        )

        out_of_stock = int(
            tool_result.get(
                "out_of_stock_count",
                0,
            )
            or 0
        )

        low_stock = int(
            tool_result.get(
                "low_stock_count",
                0,
            )
            or 0
        )

        healthy = int(
            tool_result.get(
                "healthy_count",
                0,
            )
            or 0
        )

        overstock = int(
            tool_result.get(
                "overstock_count",
                0,
            )
            or 0
        )

        stock_value = tool_result.get(
            "stock_value_at_cost",
            0,
        )

        historical_order_qty = (
            tool_result.get(
                "historical_recommended_order_quantity",
                0,
            )
        )

        attention_count = (
            critical
            + out_of_stock
            + low_stock
        )

        attention_rate = (
            round(
                attention_count
                / total
                * 100,
                1,
            )
            if total
            else 0
        )

        return (
            f"Le stock compte actuellement "
            f"**{total} positions produit-magasin**.\n\n"

            f"- **{critical}** position critique\n"
            f"- **{out_of_stock}** positions en rupture\n"
            f"- **{low_stock}** positions à stock faible\n"
            f"- **{healthy}** positions saines\n"
            f"- **{overstock}** position en surstock\n\n"

            f"La valeur totale du stock au coût est de "
            f"**{format_number_fr(stock_value, 2)} MAD**.\n\n"

            f"### À retenir\n\n"
            f"Les statuts critique, rupture et stock faible "
            f"représentent ensemble **{attention_count} positions**, "
            f"soit **{format_number_fr(attention_rate, 1)} %** "
            f"des positions analysées. C'est donc le principal "
            f"point d'attention dans l'état actuel du stock.\n\n"

            f"La quantité recommandée historique agrégée est de "
            f"**{format_number_fr(historical_order_qty, 0)} unités**. "
            f"Il s'agit d'une quantité agrégée issue du mart "
            f"d'inventaire et **non d'un seuil de commande**."
        )
    if (
        tool_name
        != "get_replenishment_priorities"
    ):
        return None

    recommendations = (
        tool_result.get(
            "recommendations",
            [],
        )
    )

    if not recommendations:
        return fallback_business_answer(
            tool_name=tool_name,
            tool_result=tool_result,
            user_message=user_message,
        )

    urgency_labels = {
        "critical": "Critique",
        "high": "Élevée",
        "medium": "Moyenne",
        "planned": "Planifiée",
        "no_order": "Aucune commande",
    }

    first = recommendations[0]

    first_urgency = (
        urgency_labels.get(
            first.get(
                "urgency_level",
                "",
            ),
            first.get(
                "urgency_level",
                "N/A",
            ),
        )
    )

    lines = [
        (
            f"La priorité principale est "
            f"**{first.get('sku', 'N/A')}** "
            f"au **{first.get('store_name', 'N/A')}**, "
            f"classée **{first_urgency}**."
        ),
        "",
        "### Priorités de réapprovisionnement",
        "",
    ]

    for rank, item in enumerate(
        recommendations,
        start=1,
    ):
        urgency = (
            urgency_labels.get(
                item.get(
                    "urgency_level",
                    "",
                ),
                item.get(
                    "urgency_level",
                    "N/A",
                ),
            )
        )

        quantity = item.get(
            "recommended_order_quantity",
            0,
        )

        if (
            isinstance(quantity, float)
            and quantity.is_integer()
        ):
            quantity = int(quantity)

        forecast = item.get(
            "forecast_30d",
            0,
        )

        stockout_date = (
            item.get(
                "estimated_stockout_date"
            )
            or "non estimée"
        )

        lines.append(
            (
                f"{rank}. **{item.get('sku', 'N/A')}** "
                f"— {item.get('product_name', 'N/A')} "
                f"— {item.get('store_name', 'N/A')}  \n"
                f"   Priorité : **{urgency}** · "
                f"Commande recommandée : "
                f"**{quantity} unités** · "
                f"Demande prévue 30 j : "
                f"**{format_number_fr(forecast, 1)} unités** · "
                f"Rupture estimée : **{stockout_date}**"
            )
        )

    lines.extend(
        [
            "",
            (
                "Le classement ci-dessus provient directement "
                "du moteur de recommandations StockPilot ML."
            ),
        ]
    )

    return "\n".join(lines)
# =========================================================
# Business answer with Qwen
# =========================================================
def build_verified_evidence(
    tool_name: str,
    tool_result: dict,
) -> dict:
    """
    Build a compact, business-safe representation
    of backend results for the LLM.

    The LLM should interpret this evidence,
    not raw internal database fields.
    """
    if (
        tool_name
        == "get_inventory_summary"
    ):
        return {
            "type":
                "inventory_health_summary",

            "scope":
                "product_store_positions",

            "scope_explanation":
                (
                    "Les comptages représentent des "
                    "combinaisons produit-magasin, "
                    "pas nécessairement des produits uniques."
                ),

            "counts": {
                "critical":
                    tool_result.get(
                        "critical_count",
                        0,
                    ),

                "out_of_stock":
                    tool_result.get(
                        "out_of_stock_count",
                        0,
                    ),

                "low_stock":
                    tool_result.get(
                        "low_stock_count",
                        0,
                    ),

                "healthy":
                    tool_result.get(
                        "healthy_count",
                        0,
                    ),

                "overstock":
                    tool_result.get(
                        "overstock_count",
                        0,
                    ),

                "total_product_store_positions":
                    tool_result.get(
                        "product_store_count",
                        0,
                    ),
            },

            "stock_value_at_cost_mad":
                tool_result.get(
                    "stock_value_at_cost",
                    0,
                ),

            "historical_recommended_order_quantity":
                tool_result.get(
                    "historical_recommended_order_quantity",
                    0,
                ),

            "important_interpretation_rules": [
                (
                    "historical_recommended_order_quantity "
                    "est une quantité recommandée agrégée "
                    "provenant du mart historique. "
                    "Ce n'est PAS un seuil de commande."
                ),
                (
                    "Ne pas transformer les positions "
                    "produit-magasin en nombre de produits uniques."
                ),
                (
                    "Ne pas recommander automatiquement "
                    "des promotions, réductions ou liquidations "
                    "pour les surstocks."
                ),
            ],
        }
    if (
        tool_name
        == "get_replenishment_priorities"
    ):
        recommendations = (
            tool_result.get(
                "recommendations",
                [],
            )
        )

        items = []

        for rank, item in enumerate(
            recommendations,
            start=1,
        ):
            items.append(
                {
                    "rank":
                        rank,

                    "sku":
                        item.get("sku"),

                    "product_name":
                        item.get(
                            "product_name"
                        ),

                    "store_name":
                        item.get(
                            "store_name"
                        ),

                    "urgency_level":
                        item.get(
                            "urgency_level"
                        ),

                    "forecast_30d":
                        item.get(
                            "forecast_30d"
                        ),

                    "stock_on_hand":
                        item.get(
                            "stock_on_hand"
                        ),

                    "safety_stock_units":
                        item.get(
                            "safety_stock_units"
                        ),

                    "recommended_order_quantity":
                        item.get(
                            "recommended_order_quantity"
                        ),

                    "estimated_stockout_date":
                        item.get(
                            "estimated_stockout_date"
                        ),
                }
            )

        return {
            "type":
                "ordered_replenishment_priorities",

            "ranking_is_authoritative":
                True,

            "ranking_instruction":
                (
                    "The rank is calculated by the "
                    "StockPilot backend. Preserve it "
                    "exactly."
                ),

            "count":
                len(items),

            "items":
                items,
        }

    return tool_result

def generate_business_answer(
    user_message: str,
    tool_name: str,
    tool_result: dict,
) -> str:
    tool_semantics = TOOL_SEMANTICS.get(
        tool_name,
        "",
    )
    verified_evidence = (
        build_verified_evidence(
            tool_name=tool_name,
            tool_result=tool_result,
        )
    )

    verified_data = json.dumps(
        verified_evidence,
        ensure_ascii=False,
        default=str,
    )

    system_prompt = """

Tu es StockPilot AI, un assistant intelligent spécialisé
dans le pilotage des stocks, ventes, prévisions de demande,
réapprovisionnements et fournisseurs.

Ton rôle n'est PAS de réciter les données.
Ton rôle est de les ANALYSER et de répondre comme
un véritable assistant métier.

Tu reçois des données backend vérifiées provenant
de PostgreSQL via des tools sécurisés.

RÈGLES DE FIABILITÉ :

- Utilise uniquement les données backend fournies.
- N'invente jamais un chiffre.
- N'invente jamais un SKU.
- N'invente jamais un produit.
- N'invente jamais un magasin.
- N'invente jamais un fournisseur.
- N'invente jamais une date.
- N'invente jamais une prévision.
- Si une information n'existe pas dans les données,
  dis clairement qu'elle n'est pas disponible.

RÈGLES DE RÉPONSE :

1. Comprends ce que l'utilisateur cherche réellement.

2. Commence par la conclusion la plus utile.

3. Explique ensuite brièvement pourquoi.

4. Ne transforme pas automatiquement toutes les données
   en une longue liste.

5. Lorsque plusieurs résultats existent,
   sélectionne les plus pertinents selon la question.

6. Mets en évidence les risques, anomalies,
   opportunités ou priorités lorsqu'ils sont visibles
   dans les données.

7. Si la question demande un classement,
   donne un classement clair.

8. Si l'utilisateur demande seulement un chiffre,
   réponds simplement avec ce chiffre et son contexte.

9. Si pertinent, termine par une courte proposition
   d'analyse complémentaire.

STYLE :

- français naturel ;
- professionnel mais conversationnel ;
- concis ;
- pas de jargon inutile ;
- pas de raisonnement interne ;
- pas de "Okay", "Let me", "The user", "I need" ;
- pas de balises <think>.

FORMAT FRANÇAIS :

- devise : MAD ;
- séparateur décimal : virgule ;
- critical = Critique ;
- high = Élevée ;
- medium = Moyenne ;
- planned = Planifiée ;
- no_order = Aucune commande.

IMPORTANT :

Une recommandation ML est une aide à la décision.
Elle ne déclenche jamais automatiquement une commande.
RÈGLES DE FIDÉLITÉ MÉTIER :

- Les données backend sont la seule source de vérité.

- Si les éléments possèdent un champ "rank",
  ce classement est AUTORITAIRE.

- Ne change JAMAIS l'ordre des ranks.

- Si l'utilisateur demande les 5 priorités et que
  5 éléments sont fournis, présente exactement
  ces 5 éléments.

- N'omets aucun élément du classement demandé.

- Ne crée jamais ton propre classement à partir
  d'un autre indicateur.

- Une demande prévue élevée ne signifie pas
  automatiquement qu'un produit est plus prioritaire.

- Ne dis jamais "surstock", "stock suffisant",
  "délai long", "délai court", "bonne performance",
  "mauvaise performance" ou une conclusion similaire
  sauf si cette qualification existe explicitement
  dans les données backend.

- Tu peux comparer des valeurs numériques,
  mais tu ne dois pas inventer de seuil métier.

- Pour get_replenishment_priorities,
  "meilleurs produits selon les recommandations ML"
  signifie :
  "produits-magasin ayant la plus haute priorité
  de réapprovisionnement calculée par StockPilot".

- Un SKU doit toujours être associé à son magasin
  lorsqu'il s'agit d'une recommandation de stock.

- Commence par la conclusion principale.

- Ensuite présente le classement de façon concise.

- Ne produis pas une seconde section d'analyse
  si l'utilisateur ne l'a pas demandée.
"""

    payload = call_ollama(
        {
            "model":
                OLLAMA_MODEL,

            "messages": [
                {
                    "role":
                        "system",

                    "content":
                        system_prompt,
                },
                {
                    "role":
                        "user",

                    "content": (
                        "/no_think\n\n"
                        f"Question utilisateur :\n{user_message}\n\n"
                        f"Tool utilisé : {tool_name}\n\n"
                        "Règles d'interprétation du tool :\n"
                        f"{tool_semantics}\n\n"
                        "Données backend vérifiées :\n"
                        f"{verified_data}\n\n"
                        "Réponds directement en français."
                    ),
                },
            ],

            "stream":
                False,

            "think":
                False,

            "keep_alive":
                "30m",

            "options": {
                "temperature":
                    0,

                "num_predict":
                    350,
            },
        }
    )

    content = (
        payload
        .get(
            "message",
            {},
        )
        .get(
            "content",
            "",
        )
    )

    cleaned = clean_model_answer(
        content
    )

    if (
        not cleaned
        or contains_reasoning_leak(
            cleaned
        )
    ):
        return fallback_business_answer(
            tool_name=tool_name,
            tool_result=tool_result,
            user_message=user_message,
        )

    return localize_business_terms(
        cleaned
    )


# =========================================================
# Generic answer
# =========================================================

def generate_generic_answer(
    user_message: str,
) -> str:
    payload = call_ollama(
        {
            "model":
                OLLAMA_MODEL,

            "messages": [
                {
                    "role":
                        "system",

                        "content": """
Tu es StockPilot AI, l'assistant intelligent intégré
à la plateforme StockPilot.

StockPilot est une plateforme d'aide à la décision
pour le pilotage des stocks, des ventes et
des approvisionnements.

FONCTIONNALITÉS ACTUELLEMENT DISPONIBLES :

- analyser les ventes historiques ;
- consulter le chiffre d'affaires ;
- consulter la marge et les transactions ;
- comparer les performances commerciales ;
- analyser la santé des stocks ;
- identifier les positions en rupture ;
- identifier les positions à stock faible ;
- identifier les positions critiques ;
- identifier les positions en surstock ;
- consulter les prévisions de demande
  générées par le modèle de machine learning ;
- consulter les recommandations ML
  de réapprovisionnement ;
- comparer les performances des magasins ;
- analyser les performances des fournisseurs ;
- consulter notamment leurs scores,
  taux de livraison à temps,
  taux de fulfillment et retards.

LIMITES ACTUELLES :

StockPilot ne doit PAS être présenté comme :

- un système temps réel ;
- un système qui met automatiquement à jour
  le stock après chaque vente ;
- un système qui passe automatiquement
  les commandes fournisseurs ;
- un système qui contacte automatiquement
  les fournisseurs ;
- un système qui déclenche automatiquement
  des promotions ;
- un ERP ;
- un système qui prend automatiquement
  les décisions commerciales.

RÈGLE IMPORTANTE SUR LES LIMITES :

Lorsque tu expliques qu'une fonctionnalité
n'existe pas actuellement, indique simplement
la limitation connue.

N'invente jamais :
- la raison technique de cette limitation ;
- une fréquence de mise à jour ;
- un délai de traitement ;
- un retard des données ;
- un avantage supposé de cette limitation ;
- une architecture technique non fournie.

Si une information n'est pas explicitement définie
dans ce prompt, ne la présente pas comme un fait.

Les recommandations StockPilot sont
des aides à la décision.

Les recommandations StockPilot sont
des aides à la décision.

RÈGLES :

Lorsque l'utilisateur demande ce que StockPilot
propose, décris uniquement les fonctionnalités
explicitement présentes ci-dessus.

N'invente jamais une fonctionnalité supplémentaire.

Pour toute question nécessitant des chiffres réels
StockPilot, ces chiffres doivent provenir
des tools sécurisés.

Tu peux répondre normalement aux salutations,
questions générales et questions conversationnelles.

Réponds toujours en français.
Sois naturel, clair et concis.
Ne révèle jamais ton raisonnement interne.
""",
                },
                {
                    "role":
                        "user",

                    "content":
                        user_message,
                },
            ],

            "stream":
                False,

            "think":
                False,

            "keep_alive":
                "30m",

            "options": {
                "temperature":
                    0.2,

                "num_predict":
                    250,
            },
        }
    )

    content = (
        payload
        .get(
            "message",
            {},
        )
        .get(
            "content",
            "",
        )
    )

    cleaned = clean_model_answer(
        content
    )

    if (
        not cleaned
        or contains_reasoning_leak(
            cleaned
        )
    ):
        return (
            "Je peux vous aider à analyser "
            "les données StockPilot disponibles."
        )

    return cleaned


# =========================================================
# Public assistant
# =========================================================
def generate_agent_final_answer(
    user_message: str,
    tool_name: str,
    arguments: dict,
    tool_result: dict,
) -> str:
    """
    Generate the final natural-language answer after
    a verified StockPilot tool has been executed.

    The model sees:
    user -> assistant tool call -> tool result
    """

    tool_semantics = TOOL_SEMANTICS.get(
        tool_name,
        "",
    )

    verified_evidence = (
        build_verified_evidence(
            tool_name=tool_name,
            tool_result=tool_result,
        )
    )

    evidence_json = json.dumps(
        verified_evidence,
        ensure_ascii=False,
        default=str,
    )

    safe_arguments = (
        arguments
        if isinstance(arguments, dict)
        else {}
    )

    system_prompt = f"""
Tu es StockPilot AI, un assistant métier intelligent
spécialisé dans la gestion des stocks, ventes,
prévisions de demande et fournisseurs.

Tu travailles avec des tools sécurisés StockPilot.

RÈGLE FONDAMENTALE :

Les résultats des tools sont la seule source de vérité
pour les données StockPilot.

Tu peux :
- expliquer les résultats ;
- identifier le point principal ;
- comparer des valeurs présentes ;
- résumer ;
- répondre naturellement à la question.

Tu ne peux PAS :
- inventer des chiffres ;
- inventer des produits ;
- inventer des SKU ;
- inventer des magasins ;
- inventer des fournisseurs ;
- inventer des seuils métier ;
- changer un classement fourni par le backend.
Lorsque les données contiennent un champ
scope_explanation ou important_interpretation_rules,
respecte-les strictement.

Ne renomme jamais un indicateur métier.

Par exemple :
une quantité agrégée n'est pas un seuil,
une position produit-magasin n'est pas
forcément un produit unique.

Si un classement contient un champ rank,
respecte exactement son ordre.

Ne transforme jamais une valeur numérique en
qualification métier comme "bon", "mauvais",
"surstock", "risque élevé" ou "délai long"
si cette qualification n'est pas explicitement
présente dans les données.

Réponds en français.

Commence par la conclusion utile.
Reste concis.
N'explique jamais ton raisonnement interne.

Sémantique du tool utilisé :

{tool_semantics}
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },

        {
            "role": "user",
            "content": user_message,
        },

        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": safe_arguments,
                    },
                }
            ],
        },

        {
            "role": "tool",
            "tool_name": tool_name,
            "content": evidence_json,
        },
    ]

    payload = call_ollama(
        {
            "model": OLLAMA_MODEL,

            "messages": messages,

            "stream": False,

            "think": False,

            "options": {
                "temperature": 0.1,
                "num_predict": 350,
            },
        }
    )

    content = (
        payload
        .get(
            "message",
            {},
        )
        .get(
            "content",
            "",
        )
    )

    cleaned = clean_model_answer(
        content
    )

    if (
        not cleaned
        or contains_reasoning_leak(
            cleaned
        )
    ):
        return fallback_business_answer(
            tool_name=tool_name,
            tool_result=tool_result,
            user_message=user_message,
        )

    return localize_business_terms(
        cleaned
    )
def enrich_route_with_active_entity(
    route: dict,
    executions: list[dict],
) -> dict:
    """
    Enrich the response route with the main business
    entity selected by the executed tools.

    This information is used by conversation memory
    for follow-up questions such as:
    "Et sa prévision ?"
    """

    enriched_route = dict(
        route
    )

    enriched_route.setdefault(
        "active_sku",
        "",
    )

    enriched_route.setdefault(
        "active_store",
        "",
    )
    enriched_route.setdefault(
        "recent_entities",
        [],
    )

    # We inspect executions in reverse order so that
    # the most recent relevant business tool has priority.
    for execution in reversed(
        executions
    ):

        if not execution.get(
            "success",
            False,
        ):
            continue

        tool_name = execution.get(
            "tool",
            "",
        )

        result = execution.get(
            "result",
            {},
        )

               # =================================================
        # Replenishment
        # =================================================

        if (
            tool_name
            == "get_replenishment_priorities"
        ):
            recommendations = result.get(
                "recommendations",
                [],
            )

            if recommendations:

                # ==========================================
                # Store the entities returned by the ranking
                # ==========================================

                recent_entities = []

                for index, recommendation in enumerate(
                    recommendations,
                    start=1,
                ):
                    sku = (
                        recommendation.get(
                            "sku",
                            "",
                        )
                        or ""
                    )

                    store_name = (
                        recommendation.get(
                            "store_name",
                            "",
                        )
                        or ""
                    )

                    if not sku:
                        continue

                    recent_entities.append(
                        {
                            "rank": index,
                            "sku": sku,
                            "store_name": store_name,
                        }
                    )

                enriched_route[
                    "recent_entities"
                ] = recent_entities

                # ==========================================
                # First ranked entity becomes active
                # ==========================================

                first = recommendations[0]

                sku = (
                    first.get(
                        "sku",
                        "",
                    )
                    or ""
                )

                store_name = (
                    first.get(
                        "store_name",
                        "",
                    )
                    or ""
                )

                if sku:
                    enriched_route[
                        "active_sku"
                    ] = sku

                if store_name:
                    enriched_route[
                        "active_store"
                    ] = store_name

                break
                # =================================================
        # Product forecast
        # =================================================

        if (
            tool_name
            == "get_product_forecast"
        ):

            sku = (
                result.get(
                    "sku",
                    "",
                )
                or execution.get(
                    "arguments",
                    {},
                ).get(
                    "sku",
                    "",
                )
                or ""
            )

            arguments = execution.get(
                "arguments",
                {},
            )

            store_name = (
                arguments.get(
                    "store_name",
                    "",
                )
                or ""
            )

            if sku:
                enriched_route[
                    "active_sku"
                ] = sku

            if store_name:
                enriched_route[
                    "active_store"
                ] = store_name


            break
    return enriched_route
def ask_stockpilot(
    user_message: str,
    context: dict | None = None,
) -> dict:
    """
    Main StockPilot AI orchestration.

    Flow:
    1. Qwen plans zero, one or several tools.
    2. Backend validates the plan.
    3. Verified tools are executed.
    4. Sensitive facts remain locked.
    """

    # =====================================================
    # 1. Agent planning
    # =====================================================

    routes, planning_success = (
        agent_plan_user_request(
            user_message=user_message,
            context=context,
        )
    )

    # =====================================================
    # 2. Fallback to legacy single router
    # =====================================================

    if not planning_success:

        fallback_route = (
            route_user_request(
                user_message=user_message,
                context=context,
            )
        )

        if (
            fallback_route.get(
                "tool"
            )
            != "none"
        ):
            routes = [
                fallback_route
            ]

        else:
            routes = []

    # =====================================================
    # 3. No business tool required
    # =====================================================

    if not routes:

        try:
            answer = (
                generate_generic_answer(
                    user_message
                )
            )

        except Exception:
            answer = (
                "Je peux vous aider à analyser "
                "les stocks, ventes, prévisions, "
                "réapprovisionnements et fournisseurs "
                "de StockPilot."
            )

        return {
            "model":
                OLLAMA_MODEL,

            "answer":
                answer,

            "tools_used":
                [],

            "route":
                default_route(),

            "context":
                normalize_conversation_context(
                    context
                ),
        }

    # =====================================================
    # 4. Execute verified tool plan
    # =====================================================

    executions = (
        execute_agent_plan(
            routes
        )
    )

    successful_executions = [
        execution
        for execution in executions
        if execution.get(
            "success",
            False,
        )
    ]

    # =====================================================
    # 5. Complete execution failure
    # =====================================================

    if not successful_executions:

        return {
            "model":
                OLLAMA_MODEL,

            "answer": (
                "Je n'ai pas pu récupérer les "
                "données StockPilot nécessaires "
                "pour répondre à cette demande."
            ),

            "tools_used": [
                {
                    "name":
                        execution.get(
                            "tool",
                            "unknown",
                        ),

                    "arguments":
                        execution.get(
                            "arguments",
                            {},
                        ),
                }
                for execution
                in executions
            ],

            "route":
                routes[-1],

            "context":
                route_to_context(
                    routes[-1]
                ),
        }

    # =====================================================
    # 6. MULTI-TOOL answer
    # =====================================================

    if len(
    successful_executions
    ) > 1:

    # =============================================
    # Deterministic factual details
    # =============================================

        locked_details = (
            build_locked_multi_tool_answer(
                user_message=
                    user_message,

                executions=
                    successful_executions,
            )
        )

    # =============================================
    # Detect sensitive ML ranking
    # =============================================

        has_sensitive_ranking = any(
            execution.get(
                "tool",
                "",
            )
            == "get_replenishment_priorities"
            for execution
            in successful_executions
        )

    # =============================================
    # Natural LLM synthesis
    # =============================================

        if has_sensitive_ranking:

                # Replenishment ranking must remain
            # fully controlled by the backend.
            synthesis = ""

        else:

            try:

                synthesis = (
                    generate_multi_tool_synthesis(
                        user_message=
                            user_message,

                        executions=
                            successful_executions,
                    )
                )   

            except Exception:

                synthesis = ""

    # =============================================
    # Final multi-tool response
    # =============================================

        if synthesis:

            answer = (
                f"{synthesis}\n\n"
                "---\n\n"
                f"{locked_details}"
            )

        else:

            answer = (
                locked_details
            )
    # =====================================================
    # 7. SINGLE-TOOL answer
    # =====================================================

    else:

        execution = (
            successful_executions[0]
        )

        tool_name = execution[
            "tool"
        ]

        result = execution[
            "result"
        ]

        arguments = execution.get(
            "arguments",
            {},
        )

        locked_answer = (
            build_locked_business_answer(
                tool_name=
                    tool_name,

                tool_result=
                    result,

                user_message=
                    user_message,
            )
        )

        if locked_answer is not None:

            answer = (
                locked_answer
            )

        elif FAST_BUSINESS_RESPONSES:

            answer = (
                fallback_business_answer(
                    tool_name=
                        tool_name,

                    tool_result=
                        result,

                    user_message=
                        user_message,
                )
            )

        else:

            try:
                answer = (
                    generate_agent_final_answer(
                        user_message=
                            user_message,

                        tool_name=
                            tool_name,

                        arguments=
                            arguments,

                        tool_result=
                            result,
                    )
                )

            except Exception:

                answer = (
                    fallback_business_answer(
                        tool_name=
                            tool_name,

                        tool_result=
                            result,

                        user_message=
                            user_message,
                    )
                )

    # =====================================================
    # 8. Response metadata
    # =====================================================

    tools_used = [
        {
            "name":
                execution[
                    "tool"
                ],

            "arguments":
                execution.get(
                    "arguments",
                    {},
                ),
        }
        for execution
        in successful_executions
    ]

    # The last selected business tool becomes
    # the structured context for a follow-up.
    primary_route = (
        successful_executions[-1]
        .get(
            "route",
            routes[-1],
        )
    )
    previous_context = (
        normalize_conversation_context(
            context
        )
    )

    if not primary_route.get(
        "active_sku",
    ):
        primary_route[
            "active_sku"
        ] = previous_context.get(
            "active_sku",
            "",
        )

    if not primary_route.get(
        "active_store",
    ):
        primary_route[
            "active_store"
        ] = previous_context.get(
            "active_store",
            "",
        )

    if not primary_route.get(
        "recent_entities",
    ):
        primary_route[
            "recent_entities"
        ] = previous_context.get(
            "recent_entities",
            [],
        )    

    primary_route = (
        enrich_route_with_active_entity(
            route=
                primary_route,

            executions=
                successful_executions,
        )
    )
    

    return {
        "model":
            OLLAMA_MODEL,

        "answer":
            answer,

        "tools_used":
            tools_used,

        "route":
            primary_route,

        "context":
            route_to_context(
                primary_route
            ),
    }