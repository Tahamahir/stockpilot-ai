def post_chat(client, message, context=None):
    response = client.post(
        "/chat",
        json={
            "message": message,
            "context": context or {},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def assert_single_tool(response, expected_tool_name):
    assert "tools_used" in response
    assert len(response["tools_used"]) == 1
    assert response["tools_used"][0]["name"] == expected_tool_name


def test_inventory_summary(client):
    response = post_chat(
        client,
        "Donne-moi l'état actuel de mon stock",
    )

    assert_single_tool(response, "get_inventory_summary")

    assert response["route"]["tool"] == "get_inventory_summary"
    assert response["context"]["last_tool"] == "get_inventory_summary"

    answer = response["answer"]
    assert "240 positions produit-magasin" in answer
    assert "13" in answer
    assert "198" in answer
    assert "570 174,81 MAD" in answer
    assert "29 466 unités" in answer


def test_sales_performance(client):
    response = post_chat(
        client,
        "Quelle est ma performance commerciale ?",
    )

    assert_single_tool(response, "get_sales_performance")

    assert response["route"]["tool"] == "get_sales_performance"
    assert response["context"]["last_tool"] == "get_sales_performance"

    answer = response["answer"]
    assert "Performance commerciale" in answer
    assert "64 623 593,69 MAD" in answer
    assert "997 546 unités" in answer
    assert "148 485" in answer
    assert "435,22 MAD" in answer
    assert "24 939 305,75 MAD" in answer
    assert "38,59 %" in answer


def test_supplier_performance(client):
    response = post_chat(
        client,
        "Quels sont mes fournisseurs les moins performants ?",
    )

    assert_single_tool(response, "get_supplier_performance")

    assert response["route"]["tool"] == "get_supplier_performance"
    assert response["context"]["last_tool"] == "get_supplier_performance"

    answer = response["answer"]
    assert "Fournisseurs présentant le plus de problèmes de livraison" in answer
    assert "Fournisseur 01" in answer
    assert "SUP-001" in answer
    assert "47,95 % de livraisons à temps" in answer
    assert "Fournisseur 07" in answer
    assert "Fournisseur 02" in answer


def test_product_forecast_explicit(client):
    response = post_chat(
        client,
        "Quelle est la prévision de SKU-00017 à Rabat ?",
    )

    assert_single_tool(response, "get_product_forecast")

    assert response["route"]["tool"] == "get_product_forecast"
    assert response["route"]["sku"] == "SKU-00017"
    assert response["route"]["store_name"] == "Rabat"

    assert response["context"]["last_tool"] == "get_product_forecast"
    assert response["context"]["active_sku"] == "SKU-00017"
    assert response["context"]["active_store"] == "Rabat"

    answer = response["answer"]
    assert "SKU-00017" in answer
    assert "Magasin Rabat" in answer
    assert "103,54 unités" in answer
    assert "2025-12-31" in answer
    assert "2026-01-29" in answer


def test_replenishment_top_3(client):
    response = post_chat(
        client,
        "Quels sont les 3 réapprovisionnements les plus urgents ?",
    )

    assert_single_tool(response, "get_replenishment_priorities")

    assert response["route"]["tool"] == "get_replenishment_priorities"
    assert response["route"]["limit"] == 3

    assert response["context"]["last_tool"] == "get_replenishment_priorities"
    assert response["context"]["active_sku"] == "SKU-00105"
    assert response["context"]["active_store"] == "Magasin Casablanca"

    recent_entities = response["context"]["recent_entities"]
    assert len(recent_entities) == 3

    assert recent_entities[0]["rank"] == 1
    assert recent_entities[0]["sku"] == "SKU-00105"
    assert recent_entities[0]["store_name"] == "Magasin Casablanca"

    assert recent_entities[1]["rank"] == 2
    assert recent_entities[1]["sku"] == "SKU-00017"
    assert recent_entities[1]["store_name"] == "Magasin Rabat"

    assert recent_entities[2]["rank"] == 3
    assert recent_entities[2]["sku"] == "SKU-00113"
    assert recent_entities[2]["store_name"] == "Magasin Casablanca"

    answer = response["answer"]
    assert "La priorité principale est **SKU-00105**" in answer
    assert "SKU-00017" in answer
    assert "SKU-00113" in answer
    assert "172,7 unités" in answer
    assert "103,6 unités" in answer
    assert "158,8 unités" in answer