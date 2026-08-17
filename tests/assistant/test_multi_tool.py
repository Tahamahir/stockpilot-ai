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
ACTIVE_ENTITIES_CONTEXT = {
    "last_tool": "get_product_forecast",
    "limit": 5,
    "urgency": "",
    "sku": "SKU-00113",
    "store_name": "Magasin Casablanca",
    "topic": "",
    "active_sku": "SKU-00113",
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
    "active_entities": [
        {
            "sku": "SKU-00105",
            "store_name": "Magasin Casablanca",
        },
        {
            "sku": "SKU-00113",
            "store_name": "Magasin Casablanca",
        },
    ],
}

def tool_names(
    response,
):
    return [
        tool["name"]
        for tool
        in response["tools_used"]
    ]


def test_sales_and_suppliers_multi_tool(
    client,
):
    response = post_chat(
        client,
        (
            "Donne-moi ma performance commerciale "
            "et les fournisseurs les moins performants"
        ),
    )

    names = tool_names(
        response
    )

    assert names == [
        "get_sales_performance",
        "get_supplier_performance",
    ]

    answer = response[
        "answer"
    ]

    # Verified sales facts
    assert (
        "64 623 593,69 MAD"
        in answer
    )

    assert (
        "997 546 unités"
        in answer
    )

    assert (
        "38,59 %"
        in answer
    )

    # Verified supplier ranking
    assert (
        "Fournisseur 01"
        in answer
    )

    assert (
        "Fournisseur 07"
        in answer
    )

    assert (
        "Fournisseur 02"
        in answer
    )


def test_inventory_and_replenishment_multi_tool(
    client,
):
    response = post_chat(
        client,
        (
            "Donne-moi l'état du stock "
            "et les 3 réapprovisionnements "
            "les plus urgents"
        ),
    )

    names = tool_names(
        response
    )

    assert (
        "get_inventory_summary"
        in names
    )

    assert (
        "get_replenishment_priorities"
        in names
    )

    assert len(
        names
    ) == 2

    answer = response[
        "answer"
    ]

    # Inventory locked facts
    assert (
        "240 positions produit-magasin"
        in answer
    )

    assert (
        "570 174,81 MAD"
        in answer
    )

    # Replenishment locked ranking
    assert (
        "SKU-00105"
        in answer
    )

    assert (
        "SKU-00017"
        in answer
    )

    assert (
        "SKU-00113"
        in answer
    )

    context = response[
        "context"
    ]

    assert len(
        context[
            "recent_entities"
        ]
    ) == 3


def test_ranked_forecast_comparison(
    client,
):
    response = post_chat(
        client,
        (
            "Compare la prevision "
            "du premier et du troisieme"
        ),
        RANKING_CONTEXT,
    )

    names = tool_names(
        response
    )

    assert names == [
        "get_product_forecast",
        "get_product_forecast",
    ]

    tools = response[
        "tools_used"
    ]

    assert (
        tools[0][
            "arguments"
        ][
            "sku"
        ]
        == "SKU-00105"
    )

    assert (
        tools[1][
            "arguments"
        ][
            "sku"
        ]
        == "SKU-00113"
    )

    answer = response[
        "answer"
    ]

    assert (
        "Comparaison des prévisions"
        in answer
    )

    assert (
        "172.67 unités"
        in answer
    )

    assert (
        "158.86 unités"
        in answer
    )

    assert (
        "13.81 unités"
        in answer
    )

    # Ensure individual locked forecast blocks
    # are not duplicated after comparison.
    assert (
        answer.count(
            "SKU-00105"
        )
        <= 2
    )

    assert (
        answer.count(
            "SKU-00113"
        )
        <= 2
    )

    context = response[
        "context"
    ]

    assert len(
        context[
            "recent_entities"
        ]
    ) == 3


def test_multi_forecast_preserves_ranking_memory(
    client,
):
    response = post_chat(
        client,
        (
            "Compare la prevision "
            "du premier et du troisieme"
        ),
        RANKING_CONTEXT,
    )

    recent_entities = (
        response[
            "context"
        ][
            "recent_entities"
        ]
    )

    assert (
        recent_entities[0]["sku"]
        == "SKU-00105"
    )

    assert (
        recent_entities[1]["sku"]
        == "SKU-00017"
    )

    assert (
        recent_entities[2]["sku"]
        == "SKU-00113"
    )


def test_replenishment_multi_tool_keeps_locked_ranking(
    client,
):
    response = post_chat(
        client,
        (
            "Donne-moi l'état du stock "
            "et les 3 réapprovisionnements "
            "les plus urgents"
        ),
    )

    answer = response[
        "answer"
    ]

    first_position = (
        answer.find(
            "SKU-00105"
        )
    )

    second_position = (
        answer.find(
            "SKU-00017"
        )
    )

    third_position = (
        answer.find(
            "SKU-00113"
        )
    )

    assert (
        first_position
        != -1
    )

    assert (
        second_position
        != -1
    )

    assert (
        third_position
        != -1
    )

    assert (
        first_position
        < second_position
        < third_position
    )
    ACTIVE_ENTITIES_CONTEXT = {
    "last_tool": "get_product_forecast",
    "limit": 5,
    "urgency": "",
    "sku": "SKU-00113",
    "store_name": "Magasin Casablanca",
    "topic": "",
    "active_sku": "SKU-00113",
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
    "active_entities": [
        {
            "sku": "SKU-00105",
            "store_name": "Magasin Casablanca",
        },
        {
            "sku": "SKU-00113",
            "store_name": "Magasin Casablanca",
        },
    ],
}


def test_active_entities_group_forecast_question(
    client,
):
    response = post_chat(
        client,
        "Lequel a la plus forte prevision ?",
        ACTIVE_ENTITIES_CONTEXT,
    )

    tools = response[
        "tools_used"
    ]

    assert len(
        tools
    ) == 2

    assert (
        tools[0]["name"]
        == "get_product_forecast"
    )

    assert (
        tools[1]["name"]
        == "get_product_forecast"
    )

    assert (
        tools[0]["arguments"]["sku"]
        == "SKU-00105"
    )

    assert (
        tools[1]["arguments"]["sku"]
        == "SKU-00113"
    )

    answer = response[
        "answer"
    ]

    assert (
        "172.67 unités"
        in answer
    )

    assert (
        "158.86 unités"
        in answer
    )

    assert (
        "13.81 unités"
        in answer
    )

    active_entities = (
        response[
            "context"
        ][
            "active_entities"
        ]
    )

    assert len(
        active_entities
    ) == 2

    assert (
        active_entities[0]["sku"]
        == "SKU-00105"
    )

    assert (
        active_entities[1]["sku"]
        == "SKU-00113"
    )


def test_active_entities_change_store_for_group(
    client,
):
    response = post_chat(
        client,
        "Compare-les maintenant a Rabat",
        ACTIVE_ENTITIES_CONTEXT,
    )

    tools = response[
        "tools_used"
    ]

    assert len(
        tools
    ) == 2

    assert (
        tools[0]["arguments"]["sku"]
        == "SKU-00105"
    )

    assert (
        "Rabat"
        in tools[0]["arguments"]["store_name"]
    )

    assert (
        tools[1]["arguments"]["sku"]
        == "SKU-00113"
    )

    assert (
        "Rabat"
        in tools[1]["arguments"]["store_name"]
    )

    answer = response[
        "answer"
    ]

    assert (
        "167.47 unités"
        in answer
    )

    assert (
        "143.65 unités"
        in answer
    )

    assert (
        "23.82 unités"
        in answer
    )

    context = response[
        "context"
    ]

    active_entities = context[
        "active_entities"
    ]

    assert len(
        active_entities
    ) == 2

    assert (
        active_entities[0]["sku"]
        == "SKU-00105"
    )

    assert (
        active_entities[1]["sku"]
        == "SKU-00113"
    )

    assert (
        "Rabat"
        in active_entities[0]["store_name"]
    )

    assert (
        "Rabat"
        in active_entities[1]["store_name"]
    )

    # The historical ranking must remain intact.
    assert (
        context[
            "recent_entities"
        ][0]["store_name"]
        == "Magasin Casablanca"
    )