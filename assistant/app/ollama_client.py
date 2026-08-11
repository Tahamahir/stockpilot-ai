from __future__ import annotations

import json
import os
import re

import httpx

from app.business_tools import (
    get_inventory_summary,
    get_product_forecast,
    get_replenishment_priorities,
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

OLLAMA_TIMEOUT = httpx.Timeout(
    connect=15.0,
    read=600.0,
    write=60.0,
    pool=60.0,
)


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
# Remove leaked reasoning
# =========================================================

def clean_model_answer(
    content: str,
) -> str:
    if not content:
        return ""

    cleaned = content.strip()

    # Complete thinking block
    cleaned = re.sub(
        r"(?is)<think>.*?</think>",
        "",
        cleaned,
    ).strip()

    # Thinking leaked before closing tag
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

    lowered = content.strip().lower()

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
        "looking at the data",
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
    )

    return any(
        phrase in lowered
        for phrase in suspicious_phrases
    )


def fallback_business_answer(
    tool_name: str,
    tool_result: dict,
) -> str:
    """
    Deterministic fallback.

    It uses only verified backend data.
    No LLM-generated values.
    """

    if (
        tool_name
        == "get_inventory_summary"
    ):
        return (
            "État actuel du stock : "
            f"{tool_result.get('critical_count', 0)} critique(s), "
            f"{tool_result.get('out_of_stock_count', 0)} "
            "en rupture, "
            f"{tool_result.get('low_stock_count', 0)} "
            "à stock faible et "
            f"{tool_result.get('healthy_count', 0)} "
            "en bonne santé. "
            "La valeur du stock au coût est de "
            f"{tool_result.get('stock_value_at_cost', 0):,.2f} MAD."
        ).replace(",", " ")

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
                quantity = int(quantity)

            stockout_date = (
                item.get(
                    "estimated_stockout_date"
                )
                or "non estimée"
            )

            lines.append(
                f"{index}. "
                f"{item.get('sku', 'N/A')} — "
                f"{item.get('product_name', 'N/A')} — "
                f"{item.get('store_name', 'N/A')} : "
                f"priorité {item.get('urgency_level', 'N/A')}, "
                f"{quantity} unités recommandées, "
                f"rupture estimée le {stockout_date}."
            )

        lines.append(
            "Ces recommandations ML sont des aides "
            "à la décision et ne déclenchent pas "
            "automatiquement une commande."
        )

        return "\n".join(lines)

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

        product_name = tool_result.get(
            "product_name",
            "Produit inconnu",
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

        # =====================================================
        # One matching store
        # =====================================================

        if len(stores) == 1:
            store_name = stores[0].get(
                "store_name",
                "Magasin inconnu",
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
                f"est de {store_total:.2f} unités "
                f"sur {horizon_days} jours, "
                f"du {forecast_start_date} "
                f"au {forecast_end_date}."
            )

    # =====================================================
    # Several stores
    # =====================================================

    if len(stores) > 1:
        lines = [
            (
                f"La demande totale prévue pour "
                f"{sku} ({product_name}) est de "
                f"{total:.2f} unités sur "
                f"{horizon_days} jours."
            )
        ]

        for store in stores:
            store_name = store.get(
                "store_name",
                "Magasin inconnu",
            )

            store_total = float(
                store.get(
                    "forecast_total",
                    0,
                )
            )

            lines.append(
                f"- {store_name} : "
                f"{store_total:.2f} unités"
            )

        lines.append(
            (
                f"Période : "
                f"{forecast_start_date} "
                f"au {forecast_end_date}."
            )
        )

        return "\n".join(
            lines
        )

    return (
        f"La demande prévue pour {sku} "
        f"est de {total:.2f} unités "
        f"sur {horizon_days} jours."
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


# =========================================================
# Deterministic routing guards
# =========================================================

def apply_deterministic_guards(
    user_message: str,
    route: dict,
) -> dict:
    lower_message = user_message.lower()

    # -----------------------------------------------------
    # Normalize
    # -----------------------------------------------------

    allowed_tools = {
        "get_inventory_summary",
        "get_replenishment_priorities",
        "get_product_forecast",
        "none",
    }

    if route.get("tool") not in allowed_tools:
        route["tool"] = "none"

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
    except (TypeError, ValueError):
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
    # SKU
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
    # IMPORTANT:
    # "les plus urgents" DOES NOT mean
    # urgency = critical.
    #
    # We apply an urgency filter only when the user
    # explicitly requests one severity.
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
    # Explicit limit
    # =====================================================

    if (
        route["tool"]
        == "get_replenishment_priorities"
    ):
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

def route_user_request(
    user_message: str,
) -> dict:
    router_prompt = """
Tu es uniquement le routeur sécurisé de StockPilot AI.

Tu ne dois jamais répondre à la question métier.
Tu dois uniquement sélectionner le tool approprié.

TOOLS :

1. get_inventory_summary
Utiliser pour :
- état global du stock
- stock actuel
- rupture de stock
- faible stock
- stock critique
- valeur du stock

2. get_replenishment_priorities
Utiliser pour :
- quoi commander
- produits à commander
- produits les plus urgents
- priorités de commande
- recommandations ML
- plan de réapprovisionnement
- risque de rupture
- commandes recommandées

IMPORTANT :
"les plus urgents" signifie classer les recommandations
par priorité.
Cela NE signifie PAS urgency="critical".

urgency doit être renseigné seulement si l'utilisateur
demande explicitement :
critical
high
medium
planned

Sinon urgency doit être "".

3. get_product_forecast
Utiliser pour :
- forecast d'un SKU
- prévision de demande
- demande prévue sur 30 jours
- prévision d'un produit précis

4. none
Seulement lorsque la question ne nécessite aucune donnée
StockPilot.

RÈGLES :

- limit = 10 par défaut.
- sku = "" si aucun SKU.
- store_name = "" si aucun magasin précis.
- urgency = "" par défaut.
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
                    "num_predict": 120,
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
        # Do not fail the entire assistant if the
        # LLM router fails.
        #
        # The deterministic guards below can still
        # route the main business use cases.
        route = default_route()

    return apply_deterministic_guards(
        user_message,
        route,
    )


# =========================================================
# Execute ONLY approved functions
# =========================================================

def execute_route(
    route: dict,
) -> tuple[dict, dict]:
    tool_name = route["tool"]

    if tool_name == "get_inventory_summary":
        arguments = {}

        result = (
            get_inventory_summary()
        )

    elif (
        tool_name
        == "get_replenishment_priorities"
    ):
        arguments = {
            "limit": route["limit"],
        }

        if route["urgency"]:
            arguments[
                "urgency"
            ] = route["urgency"]

        result = (
            get_replenishment_priorities(
                **arguments
            )
        )

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
            "sku": route["sku"],
        }

        if route["store_name"]:
            arguments[
                "store_name"
            ] = route["store_name"]

        result = (
            get_product_forecast(
                **arguments
            )
        )

    else:
        return {}, {}

    return result, arguments


# =========================================================
# Generate answer from VERIFIED DATA
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

Réponds DIRECTEMENT à la question.
Ne réfléchis pas à voix haute.

Tu dois utiliser UNIQUEMENT les données
backend vérifiées fournies.

Règles absolues :

- N'invente aucun produit.
- N'invente aucun SKU.
- N'invente aucun magasin.
- N'invente aucune quantité.
- N'invente aucune date.
- N'invente aucune prévision.
- N'invente aucun niveau de priorité.
- N'invente aucune devise.

La devise StockPilot est MAD pour
les informations monétaires.

N'explique jamais comment tu analyses
la question.

N'écris jamais :
- "Okay"
- "Let me"
- "The user"
- "I need"
- ton raisonnement
- tes étapes internes
- une balise think

Commence directement par la réponse métier.

Réponds uniquement en français.

Pour une recommandation ML, indique :
SKU, produit, magasin, priorité,
quantité recommandée et date estimée
de rupture lorsque ces données existent.

Une recommandation ML est une aide
à la décision et ne déclenche aucune
commande automatiquement.

/no_think
"""

    payload = call_ollama(
        {
            "model": OLLAMA_MODEL,

            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        "/no_think\n\n"
                        f"Question : {user_message}\n\n"
                        "Données backend vérifiées :\n"
                        f"{verified_data}\n\n"
                        "Réponds directement en français."
                    ),
                },
            ],

            "stream": False,
            "think": False,
            "keep_alive": "30m",

            "options": {
                "temperature": 0,
                "num_predict": 600,
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

    # Qwen3:4b sometimes leaks its reasoning
    # despite non-thinking mode.
    # Never expose it to the API user.
    if contains_reasoning_leak(
        cleaned
    ):
        return fallback_business_answer(
            tool_name,
            tool_result,
        )

    if not cleaned:
        return fallback_business_answer(
            tool_name,
            tool_result,
        )

    return cleaned

# =========================================================
# Generic answer
# =========================================================

def generate_generic_answer(
    user_message: str,
) -> str:
    payload = call_ollama(
        {
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Tu es StockPilot AI. "
                        "Réponds en français. "
                        "Réponds uniquement aux questions "
                        "générales ne nécessitant pas les "
                        "données privées StockPilot. "
                        "N'invente jamais de chiffres "
                        "concernant le stock, les ventes, "
                        "les forecasts ou les commandes."
                    ),
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.2,
                "num_predict": 250,
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

    return clean_model_answer(
        content
    )


# =========================================================
# Public assistant function
# =========================================================

def ask_stockpilot(
    user_message: str,
) -> dict:
    user_message = (
        user_message
        .strip()
    )

    if not user_message:
        return {
            "model": OLLAMA_MODEL,
            "answer": (
                "Veuillez saisir une question."
            ),
            "tools_used": [],
            "route": default_route(),
        }

    route = route_user_request(
        user_message
    )

    tool_name = route["tool"]

    # =====================================================
    # Generic question
    # =====================================================

    if tool_name == "none":
        return {
            "model": OLLAMA_MODEL,
            "answer": (
                generate_generic_answer(
                    user_message
                )
            ),
            "tools_used": [],
            "route": route,
        }

    # =====================================================
    # Business data question
    # =====================================================

    try:
        result, arguments = (
            execute_route(
                route
            )
        )

    except Exception as error:
        return {
            "model": OLLAMA_MODEL,
            "answer": (
                "Une erreur est survenue lors "
                "de la récupération des données "
                "StockPilot."
            ),
            "tools_used": [
                {
                    "name": tool_name,
                    "arguments": {},
                }
            ],
            "route": route,
            "error": str(error),
        }

    # =====================================================
    # Generate final natural-language answer
    # =====================================================

    try:
        answer = (
            generate_business_answer(
                user_message=user_message,
                tool_name=tool_name,
                tool_result=result,
            )
        )

    except Exception:
        # If Qwen fails after the business tool succeeded,
        # never lose the verified result.
        answer = (
            "Les données ont bien été récupérées, "
            "mais la génération de la réponse "
            "en langage naturel a échoué."
        )

    return {
        "model": OLLAMA_MODEL,
        "answer": answer,
        "tools_used": [
            {
                "name": tool_name,
                "arguments": arguments,
            }
        ],
        "route": route,
    }