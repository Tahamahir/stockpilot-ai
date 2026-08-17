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


def assert_capability_tool(
    response,
    expected_topic,
):
    assert len(
        response["tools_used"]
    ) == 1

    tool = response[
        "tools_used"
    ][0]

    assert (
        tool["name"]
        == "get_stockpilot_capabilities"
    )

    assert (
        tool["arguments"]["topic"]
        == expected_topic
    )


def test_supplier_performance_capability(
    client,
):
    response = post_chat(
        client,
        "Que propose Supplier Performance ?",
    )

    assert_capability_tool(
        response,
        "supplier_performance",
    )

    answer = response["answer"]

    assert (
        "Supplier Performance"
        in answer
    )

    assert (
        "fournisseurs"
        in answer.lower()
    )


def test_demand_forecast_capability(
    client,
):
    response = post_chat(
        client,
        "Que propose Demand Forecast ?",
    )

    assert_capability_tool(
        response,
        "demand_forecast",
    )

    answer = response["answer"]

    assert (
        "Demand Forecast"
        in answer
    )

    assert (
        "prévisions"
        in answer.lower()
    )


def test_inventory_health_capability(
    client,
):
    response = post_chat(
        client,
        "Inventory Health, qu'est-ce qu'il propose ?",
    )

    assert_capability_tool(
        response,
        "inventory_health",
    )

    answer = response["answer"]

    assert (
        "Inventory Health"
        in answer
    )

    assert (
        "stock"
        in answer.lower()
    )


def test_replenishment_capability(
    client,
):
    response = post_chat(
        client,
        "Que propose le module Replenishment ?",
    )

    assert_capability_tool(
        response,
        "replenishment",
    )

    answer = response["answer"]

    assert (
        "réapprovisionnement"
        in answer.lower()
    )


def test_real_time_capability(
    client,
):
    response = post_chat(
        client,
        "Est-ce que StockPilot fonctionne en temps réel ?",
    )

    assert_capability_tool(
        response,
        "real_time",
    )

    answer = response["answer"]

    assert (
        "ne fonctionne pas actuellement "
        "en temps réel"
        in answer.lower()
    )


def test_supplier_data_not_capability(
    client,
):
    response = post_chat(
        client,
        "Quels sont mes fournisseurs les moins performants ?",
    )

    assert len(
        response["tools_used"]
    ) == 1

    assert (
        response[
            "tools_used"
        ][0]["name"]
        == "get_supplier_performance"
    )