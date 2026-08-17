def post_chat(
    client,
    message,
    context=None,
):
    response = client.post(
        "/chat",
        json={
            "message": message,
            "context": context or {},
        },
    )

    assert (
        response.status_code == 200
    ), response.text

    return response.json()


RANKING_CONTEXT = {
    "last_tool": "get_replenishment_priorities",
    "limit": 3,
    "urgency": "",
    "sku": "",
    "store_name": "",
    "topic": "",
    "active_sku": "SKU-00105",
    "active_store": "Magasin Casablanca",
    "recent_entities": [
        {
            "rank": 1,
            "sku": "SKU-00105",
            "store_name": "Magasin Casablanca",
        },
        {
            "rank": 2,
            "sku": "SKU-00017",
            "store_name": "Magasin Rabat",
        },
        {
            "rank": 3,
            "sku": "SKU-00113",
            "store_name": "Magasin Casablanca",
        },
    ],
}


def test_active_entity_forecast_followup(
    client,
):
    response = post_chat(
        client,
        "Et sa prevision ?",
        RANKING_CONTEXT,
    )

    assert len(
        response["tools_used"]
    ) == 1

    tool = response[
        "tools_used"
    ][0]

    assert (
        tool["name"]
        == "get_product_forecast"
    )

    assert (
        tool["arguments"]["sku"]
        == "SKU-00105"
    )

    assert (
        "Casablanca"
        in tool["arguments"]["store_name"]
    )

    context = response["context"]

    assert (
        context["active_sku"]
        == "SKU-00105"
    )

    assert (
        "Casablanca"
        in context["active_store"]
    )

    assert len(
        context["recent_entities"]
    ) == 3


def test_change_store_preserves_active_sku(
    client,
):
    context = {
        "last_tool": "get_product_forecast",
        "limit": 5,
        "urgency": "",
        "sku": "SKU-00105",
        "store_name": "Magasin Casablanca",
        "topic": "",
        "active_sku": "SKU-00105",
        "active_store": "Magasin Casablanca",
        "recent_entities": [],
    }

    response = post_chat(
        client,
        "Et à Rabat ?",
        context,
    )

    tool = response[
        "tools_used"
    ][0]

    assert (
        tool["name"]
        == "get_product_forecast"
    )

    assert (
        tool["arguments"]["sku"]
        == "SKU-00105"
    )

    assert (
        "Rabat"
        in tool["arguments"]["store_name"]
    )

    assert (
        response["context"]["active_sku"]
        == "SKU-00105"
    )

    assert (
        "Rabat"
        in response[
            "context"
        ][
            "active_store"
        ]
    )


def test_change_sku_preserves_store(
    client,
):
    context = {
        "last_tool": "get_product_forecast",
        "limit": 5,
        "urgency": "",
        "sku": "SKU-00105",
        "store_name": "Rabat",
        "topic": "",
        "active_sku": "SKU-00105",
        "active_store": "Rabat",
        "recent_entities": [],
    }

    response = post_chat(
        client,
        "Et pour SKU-00017 ?",
        context,
    )

    tool = response[
        "tools_used"
    ][0]

    assert (
        tool["name"]
        == "get_product_forecast"
    )

    assert (
        tool["arguments"]["sku"]
        == "SKU-00017"
    )

    assert (
        "Rabat"
        in tool["arguments"]["store_name"]
    )

    assert (
        response["context"]["active_sku"]
        == "SKU-00017"
    )

    assert (
        "Rabat"
        in response[
            "context"
        ][
            "active_store"
        ]
    )


def test_capability_preserves_active_entity(
    client,
):
    context = {
        "last_tool": "get_product_forecast",
        "limit": 5,
        "urgency": "",
        "sku": "SKU-00017",
        "store_name": "Rabat",
        "topic": "",
        "active_sku": "SKU-00017",
        "active_store": "Rabat",
        "recent_entities": [],
    }

    response = post_chat(
        client,
        "Que propose Demand Forecast ?",
        context,
    )

    tool = response[
        "tools_used"
    ][0]

    assert (
        tool["name"]
        == "get_stockpilot_capabilities"
    )

    assert (
        tool["arguments"]["topic"]
        == "demand_forecast"
    )

    assert (
        response["context"]["active_sku"]
        == "SKU-00017"
    )

    assert (
        response["context"]["active_store"]
        == "Rabat"
    )


def test_forecast_followup_after_capability(
    client,
):
    context = {
        "last_tool": "get_stockpilot_capabilities",
        "limit": 5,
        "urgency": "",
        "sku": "",
        "store_name": "",
        "topic": "demand_forecast",
        "active_sku": "SKU-00017",
        "active_store": "Rabat",
        "recent_entities": [],
    }

    response = post_chat(
        client,
        "Et sa prevision ?",
        context,
    )

    tool = response[
        "tools_used"
    ][0]

    assert (
        tool["name"]
        == "get_product_forecast"
    )

    assert (
        tool["arguments"]["sku"]
        == "SKU-00017"
    )

    assert (
        "Rabat"
        in tool["arguments"]["store_name"]
    )

    assert (
        response["context"]["active_sku"]
        == "SKU-00017"
    )


def test_second_ranked_entity_reference(
    client,
):
    response = post_chat(
        client,
        "Et la prevision du deuxieme ?",
        RANKING_CONTEXT,
    )

    tool = response[
        "tools_used"
    ][0]

    assert (
        tool["name"]
        == "get_product_forecast"
    )

    assert (
        tool["arguments"]["sku"]
        == "SKU-00017"
    )

    assert (
        "Rabat"
        in tool["arguments"]["store_name"]
    )

    context = response["context"]

    assert (
        context["active_sku"]
        == "SKU-00017"
    )

    assert (
        "Rabat"
        in context["active_store"]
    )

    # Ranking memory must survive the follow-up.
    assert len(
        context["recent_entities"]
    ) == 3

    assert (
        context[
            "recent_entities"
        ][1]["sku"]
        == "SKU-00017"
    )


def test_generic_message_preserves_memory(
    client,
):
    context = {
        "last_tool": "get_product_forecast",
        "limit": 5,
        "urgency": "",
        "sku": "SKU-00017",
        "store_name": "Rabat",
        "topic": "",
        "active_sku": "SKU-00017",
        "active_store": "Rabat",
        "recent_entities": [],
    }

    response = post_chat(
        client,
        "Bonjour",
        context,
    )

    assert (
        response["tools_used"]
        == []
    )

    assert (
        response["context"]["active_sku"]
        == "SKU-00017"
    )

    assert (
        response["context"]["active_store"]
        == "Rabat"
    )