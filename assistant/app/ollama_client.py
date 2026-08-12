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
        "limit": 10,
        "urgency": "",
        "sku": "",
        "store_name": "",
    }

def default_conversation_context() -> dict:
    return {
        "last_tool": "none",
        "limit": 10,
        "urgency": "",
        "sku": "",
        "store_name": "",
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
                10,
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

    else:
        return {}, {}

    return result, arguments


# =========================================================
# Deterministic fallback
# =========================================================

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


# =========================================================
# Business answer with Qwen
# =========================================================

def generate_business_answer(
    user_message: str,
    tool_name: str,
    tool_result: dict,
) -> str:
    verified_data = json.dumps(
        tool_result,
        ensure_ascii=False,
        default=str,
    )

    system_prompt = """
/no_think

Tu es StockPilot AI.

Réponds DIRECTEMENT à la question utilisateur.

Tu dois utiliser UNIQUEMENT les données backend
vérifiées fournies.

Règles absolues :

- N'invente aucun produit.
- N'invente aucun SKU.
- N'invente aucun magasin.
- N'invente aucun fournisseur.
- N'invente aucune quantité.
- N'invente aucune prévision.
- N'invente aucune date.
- N'invente aucune devise.
- N'invente aucun niveau d'urgence.
- N'invente aucun chiffre d'affaires.

La devise StockPilot est MAD pour les valeurs monétaires.

Les niveaux d'urgence doivent être présentés en français :

critical = Critique
high = Élevée
medium = Moyenne
planned = Planifiée
no_order = Aucune commande

Pour les nombres décimaux en français,
utilise une virgule comme séparateur décimal.

Exemple :
846,77
et non
846.77

N'explique jamais ton raisonnement interne.

N'écris jamais :
- Okay
- Let me
- The user
- I need
- tes étapes internes
- une balise think

Commence directement par la réponse métier.

Réponds uniquement en français.

Une recommandation ML est une aide à la décision
et ne crée jamais automatiquement une commande.

/no_think
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
                        f"Question : {user_message}\n\n"
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
                    600,
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

                    "content": (
                        "/no_think\n"
                        "Tu es StockPilot AI. "
                        "Réponds directement en français. "
                        "N'invente jamais de chiffres "
                        "concernant StockPilot."
                    ),
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

def ask_stockpilot(
    user_message: str,
    context: dict | None = None,
) -> dict:
    user_message = (
        user_message
        .strip()
    )

    if not user_message:
        return {
            "model":
                OLLAMA_MODEL,

            "answer":
                "Veuillez saisir une question.",

            "tools_used":
                [],

            "route":
                default_route(),
        }

    route = route_user_request(
        user_message,
        context=context,
    )

    tool_name = route[
        "tool"
    ]
    updated_context = (
        route_to_context(
            route
        )
    )

    # =====================================================
    # Generic
    # =====================================================

    if tool_name == "none":
        return {
            "model":
                OLLAMA_MODEL,

            "answer":
                generate_generic_answer(
                    user_message
                ),

            "tools_used":
                [],

            "route":
                route,

            "context":
                normalize_conversation_context(
                    context
                ),
        }

    # =====================================================
    # Execute business tool
    # =====================================================

    # =====================================================
# Execute business tool
# =====================================================

    try:
        result, arguments = (
            execute_route(
                route
            )
        )

    except Exception as error:
        return {
            "model":
                OLLAMA_MODEL,

            "answer": (
                "Une erreur est survenue lors "
                "de la récupération des données "
                "StockPilot."
            ),

            "tools_used": [
                {
                    "name":
                        tool_name,

                    "arguments":
                        {},
                }
            ],

            "route":
                route,

            "error":
                str(error),
        }


    # =====================================================
    # Generate response
    # =====================================================

    if FAST_BUSINESS_RESPONSES:

    # Fast mode:
    # no second Ollama call for known business questions.
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

    # LLM mode:
    # Qwen reformulates the verified backend data.
        try:
            answer = (
                generate_business_answer(
                    user_message=
                        user_message,

                    tool_name=
                        tool_name,

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
    # Final API response
    # =====================================================

    return {
        "model":
            OLLAMA_MODEL,

        "answer":
            answer,

        "tools_used": [
            {
                "name":
                    tool_name,

                "arguments":
                    arguments,
            }
        ],

        "route":
            route,
            
        "context":
            updated_context,
    }