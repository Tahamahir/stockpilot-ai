from __future__ import annotations

import httpx
import streamlit as st

from assistant_client import (
    check_assistant_health,
    send_message,
)


# =========================================================
# Page configuration
# =========================================================

st.set_page_config(
    page_title="Assistant IA | StockPilot AI",
    page_icon="💬",
    layout="wide",
)


# =========================================================
# Constants
# =========================================================

WELCOME_MESSAGE = """
Bonjour 👋

Je suis **StockPilot AI**, votre assistant métier.

Je peux analyser les données disponibles concernant :

- l'état des stocks ;
- les recommandations de réapprovisionnement ML ;
- les prévisions de demande ;
- les ventes et le chiffre d'affaires ;
- la performance des magasins ;
- la performance des fournisseurs.

Posez-moi une question sur vos données StockPilot.
"""


EXAMPLE_QUESTIONS = [
    (
        "📦 État du stock",
        "Donne-moi un résumé de l'état actuel de mon stock.",
    ),
    (
        "🛒 Priorités ML",
        (
            "Quels sont les 5 produits-magasin "
            "les plus urgents à commander selon "
            "les recommandations ML ?"
        ),
    ),
    (
        "📈 Prévision",
        (
            "Quelle est la demande prévue sur 30 jours "
            "pour SKU-00071 au Magasin Rabat ?"
        ),
    ),
    (
        "💰 Chiffre d'affaires",
        "Quel est mon chiffre d'affaires total ?",
    ),
    (
        "🏆 Top ventes",
        "Quels sont mes 5 produits les plus vendus ?",
    ),
    (
        "🏪 Magasin",
        (
            "Quel magasin réalise le plus "
            "de chiffre d'affaires ?"
        ),
    ),
    (
        "🚚 Fournisseurs",
        (
            "Quels sont les 3 fournisseurs "
            "qui ont le plus de problèmes de livraison ?"
        ),
    ),
]


TOOL_LABELS = {
    "get_inventory_summary":
        "État du stock",

    "get_replenishment_priorities":
        "Réapprovisionnement ML",

    "get_product_forecast":
        "Prévision de demande",

    "get_sales_performance":
        "Performance commerciale",

    "get_supplier_performance":
        "Performance fournisseurs",
}


# =========================================================
# Session state
# =========================================================

if "assistant_messages" not in st.session_state:
    st.session_state.assistant_messages = [
        {
            "role": "assistant",
            "content": WELCOME_MESSAGE,
            "tools_used": [],
        }
    ]


if "pending_example_question" not in st.session_state:
    st.session_state.pending_example_question = None

if "assistant_context" not in st.session_state:
    st.session_state.assistant_context = {}


# =========================================================
# Helpers
# =========================================================

def tool_display_name(
    tool_name: str,
) -> str:
    return TOOL_LABELS.get(
        tool_name,
        tool_name,
    )


def display_tool_metadata(
    tools_used: list[dict],
) -> None:
    """
    Show which secure backend tool was used.
    """

    if not tools_used:
        return

    with st.expander(
        "🔎 Source de la réponse",
        expanded=False,
    ):
        for tool in tools_used:
            tool_name = tool.get(
                "name",
                "unknown",
            )

            arguments = tool.get(
                "arguments",
                {},
            )

            st.markdown(
                f"**Tool :** "
                f"`{tool_display_name(tool_name)}`"
            )

            if arguments:
                st.markdown(
                    "**Paramètres utilisés :**"
                )

                st.json(
                    arguments,
                    expanded=False,
                )

        st.caption(
            "Les données métier sont récupérées par des "
            "fonctions backend prédéfinies. "
            "Le modèle IA n'exécute pas directement "
            "de requêtes SQL libres."
        )


def process_user_message(
    user_message: str,
) -> None:
    """
    Add the message to the conversation, call the API,
    then store the assistant response.
    """

    user_message = (
        user_message
        .strip()
    )

    if not user_message:
        return

    st.session_state.assistant_messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    try:
        with st.spinner(
            "StockPilot AI analyse vos données..."
        ):
            response = send_message(
                message=
                    user_message,

                context=
                    st.session_state.assistant_context,
            )
        st.session_state.assistant_context = (
            response.get(
                "context",
                {},
            )
        )

        answer = (
            response.get(
                "answer",
                "",
            )
            or (
                "Aucune réponse n'a été retournée "
                "par l'assistant."
            )
        )

        st.session_state.assistant_messages.append(
            {
                "role": "assistant",
                "content": answer,
                "tools_used":
                    response.get(
                        "tools_used",
                        [],
                    ),
                "route":
                    response.get(
                        "route",
                        {},
                    ),
                "model":
                    response.get(
                        "model",
                        "",
                    ),
            }
        )

    except httpx.ConnectError:
        st.session_state.assistant_messages.append(
            {
                "role": "assistant",
                "content": (
                    "Impossible de joindre le service "
                    "StockPilot Assistant API."
                ),
                "tools_used": [],
                "error": True,
            }
        )

    except httpx.TimeoutException:
        st.session_state.assistant_messages.append(
            {
                "role": "assistant",
                "content": (
                    "L'assistant met plus de temps que prévu "
                    "à répondre. Veuillez réessayer."
                ),
                "tools_used": [],
                "error": True,
            }
        )

    except httpx.HTTPStatusError as error:
        st.session_state.assistant_messages.append(
            {
                "role": "assistant",
                "content": (
                    "Le service Assistant IA a retourné "
                    "une erreur."
                ),
                "tools_used": [],
                "error": True,
                "technical_error": str(error),
            }
        )

    except Exception as error:
        st.session_state.assistant_messages.append(
            {
                "role": "assistant",
                "content": (
                    "Une erreur inattendue est survenue "
                    "pendant l'analyse."
                ),
                "tools_used": [],
                "error": True,
                "technical_error": str(error),
            }
        )


# =========================================================
# IMPORTANT
# httpx is needed by the exception handlers above
# =========================================================



# =========================================================
# Header
# =========================================================

st.title(
    "💬 Assistant StockPilot AI"
)

st.caption(
    "Interrogez vos stocks, ventes, prévisions, "
    "recommandations ML et performances fournisseurs "
    "en langage naturel."
)


# =========================================================
# Assistant service health
# =========================================================

try:
    health = check_assistant_health()

    ollama = health.get(
        "ollama",
        {},
    )

    database = health.get(
        "database",
        {},
    )

    service_available = (
        health.get(
            "status"
        )
        == "ok"
    )

except Exception:
    health = {}
    ollama = {}
    database = {}
    service_available = False


# =========================================================
# Sidebar
# =========================================================

with st.sidebar:
    st.header(
        "Assistant IA"
    )

    if service_available:
        st.success(
            "Assistant connecté",
            icon="✅",
        )
    else:
        st.error(
            "Assistant indisponible",
            icon="❌",
        )

    st.divider()

    st.subheader(
        "Infrastructure"
    )

    st.write(
        "**Modèle :**",
        ollama.get(
            "model",
            "Indisponible",
        ),
    )

    ollama_available = (
        ollama.get("status") == "ok"
        and bool(
            ollama.get("model")
        )
    )

    st.write(
        "**LLM :**",
        (
            "Disponible"
            if ollama_available
            else "Indisponible"
        ),
    )

    st.write(
        "**Base :**",
        database.get(
            "database_name",
            "Indisponible",
        ),
    )

    st.divider()

    if st.button(
        "🗑️ Nouvelle conversation",
        use_container_width=True,
    ):
        st.session_state.assistant_messages = [
            {
                "role": "assistant",
                "content": WELCOME_MESSAGE,
                "tools_used": [],
            }
        ]

        st.session_state.pending_example_question = None

        st.rerun()

    st.caption(
        "L'assistant utilise uniquement des tools métier "
        "prédéfinis pour accéder aux données StockPilot."
    )


# =========================================================
# Example questions
# =========================================================

if (
    len(
        st.session_state.assistant_messages
    )
    <= 1
):
    st.subheader(
        "Exemples de questions"
    )

    columns = st.columns(2)

    for index, (
        label,
        question,
    ) in enumerate(
        EXAMPLE_QUESTIONS
    ):
        column = columns[
            index % 2
        ]

        with column:
            if st.button(
                label,
                key=f"example_{index}",
                use_container_width=True,
            ):
                st.session_state.pending_example_question = (
                    question
                )

                st.rerun()

    st.divider()


# =========================================================
# Process an example question
# =========================================================

if (
    st.session_state.pending_example_question
    is not None
):
    pending_question = (
        st.session_state.pending_example_question
    )

    st.session_state.pending_example_question = None

    process_user_message(
        pending_question
    )

    st.rerun()


# =========================================================
# Conversation display
# =========================================================

for message in (
    st.session_state.assistant_messages
):
    role = message.get(
        "role",
        "assistant",
    )

    with st.chat_message(
        role
    ):
        st.markdown(
            message.get(
                "content",
                "",
            )
        )

        if role == "assistant":
            display_tool_metadata(
                message.get(
                    "tools_used",
                    [],
                )
            )

            if (
                message.get(
                    "technical_error"
                )
            ):
                with st.expander(
                    "Détails techniques",
                    expanded=False,
                ):
                    st.code(
                        message[
                            "technical_error"
                        ]
                    )


# =========================================================
# Chat input
# =========================================================

user_prompt = st.chat_input(
    (
        "Ex. Quels sont mes 5 produits "
        "les plus urgents à commander ?"
    ),
    disabled=not service_available,
)


if user_prompt:
    process_user_message(
        user_prompt
    )

    st.rerun()


# =========================================================
# Footer
# =========================================================

st.divider()

st.caption(
    "StockPilot AI • Assistant métier local basé sur "
    "Qwen3 + FastAPI + PostgreSQL. "
    "Les recommandations ML constituent une aide "
    "à la décision et ne déclenchent aucune commande."
)