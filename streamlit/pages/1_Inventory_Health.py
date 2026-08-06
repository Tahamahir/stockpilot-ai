from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from queries import load_inventory_health_details


st.set_page_config(
    page_title="Inventory Health | StockPilot AI",
    page_icon="📦",
    layout="wide",
)


STATUS_LABELS = {
    "out_of_stock": "Rupture de stock",
    "backorder_risk": "Risque de commandes en attente",
    "no_recent_sales": "Aucune vente récente",
    "critical": "Critique",
    "low_stock": "Stock faible",
    "overstock": "Surstock",
    "healthy": "Stock sain",
}


st.title("📦 Santé des stocks")

st.caption(
    "Analyse des niveaux de stock et recommandations "
    "automatiques de réapprovisionnement."
)


try:
    inventory = load_inventory_health_details()
    required_columns = {
    "store_id",
    "store_name",
    }

    missing_columns = required_columns.difference(
    inventory.columns
    )

    if missing_columns:
        st.error(
        "Colonnes manquantes dans les données : "
        + ", ".join(sorted(missing_columns))
        )

        st.write(
        "Colonnes actuellement reçues :",
        inventory.columns.tolist(),
        )

        st.stop()

except Exception as error:
    st.error("Impossible de charger les données de stock.")
    st.exception(error)
    st.stop()


if inventory.empty:
    st.warning("Aucune donnée disponible dans le mart de stock.")
    st.stop()


inventory["inventory_health_label"] = (
    inventory["inventory_health_status"]
    .map(STATUS_LABELS)
    .fillna(inventory["inventory_health_status"])
)


# =========================================================
# Sidebar filters
# =========================================================
with st.sidebar:
    st.header("Filtres")

    inventory["store_display"] = (
    inventory["store_name"]
    .fillna(inventory["store_id"].astype(str))
    )

    store_options = sorted(
    inventory["store_display"]
    .dropna()
    .unique()
    .tolist()
    )

    selected_stores = st.multiselect(
        label="Magasins",
        options=store_options,
        default=store_options,
    )

    category_options = sorted(
        inventory["category_name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_categories = st.multiselect(
        label="Catégories",
        options=category_options,
        default=category_options,
    )

    status_options = sorted(
        inventory["inventory_health_label"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_statuses = st.multiselect(
        label="État du stock",
        options=status_options,
        default=status_options,
    )

    search_text = st.text_input(
        label="Rechercher un produit",
        placeholder="Nom du produit ou SKU",
    )

    only_recommendations = st.checkbox(
        label="Afficher uniquement les produits à commander",
        value=False,
    )


# =========================================================
# Apply filters
# =========================================================
filtered_inventory = inventory.copy()

filtered_inventory = filtered_inventory[
    filtered_inventory["store_display"]
    .isin(selected_stores)
]

filtered_inventory = filtered_inventory[
    filtered_inventory["category_name"]
    .astype(str)
    .isin(selected_categories)
]

filtered_inventory = filtered_inventory[
    filtered_inventory["inventory_health_label"]
    .isin(selected_statuses)
]

if search_text:
    normalized_search = search_text.strip().lower()

    filtered_inventory = filtered_inventory[
        filtered_inventory["product_name"]
        .fillna("")
        .str.lower()
        .str.contains(
            normalized_search,
            regex=False,
        )
        |
        filtered_inventory["sku"]
        .fillna("")
        .str.lower()
        .str.contains(
            normalized_search,
            regex=False,
        )
    ]

if only_recommendations:
    filtered_inventory = filtered_inventory[
        filtered_inventory["recommended_order_quantity"] > 0
    ]


# =========================================================
# KPI
# =========================================================
st.subheader("Indicateurs de stock")

out_of_stock_count = int(
    (
        filtered_inventory["inventory_health_status"]
        == "out_of_stock"
    ).sum()
)

low_stock_count = int(
    (
        filtered_inventory["inventory_health_status"]
        == "low_stock"
    ).sum()
)

critical_count = int(
    (
        filtered_inventory["inventory_health_status"]
        == "critical"
    ).sum()
)

recommended_units = float(
    filtered_inventory["recommended_order_quantity"].sum()
)

stock_value = float(
    filtered_inventory["stock_value_at_cost"].sum()
)

kpi_row = st.columns(5)

kpi_row[0].metric(
    label="Produits-magasin analysés",
    value=len(filtered_inventory),
)

kpi_row[1].metric(
    label="Ruptures",
    value=out_of_stock_count,
)

kpi_row[2].metric(
    label="Stocks faibles",
    value=low_stock_count,
)

kpi_row[3].metric(
    label="Produits critiques",
    value=critical_count,
)

kpi_row[4].metric(
    label="Quantité recommandée",
    value=f"{recommended_units:,.0f}",
)

st.metric(
    label="Valeur du stock filtré",
    value=f"{stock_value:,.2f} MAD",
)


# =========================================================
# Charts
# =========================================================
st.divider()

left_column, right_column = st.columns(2)

with left_column:
    st.subheader("Répartition par état")

    status_summary = (
        filtered_inventory
        .groupby(
            "inventory_health_label",
            as_index=False,
        )
        .agg(
            product_store_count=(
                "inventory_health_key",
                "count",
            ),
            recommended_units=(
                "recommended_order_quantity",
                "sum",
            ),
        )
        .sort_values(
            "product_store_count",
            ascending=False,
        )
    )

    status_chart = px.bar(
        status_summary,
        x="inventory_health_label",
        y="product_store_count",
        text_auto=True,
        labels={
            "inventory_health_label": "État du stock",
            "product_store_count": "Nombre de produits-magasin",
        },
    )

    status_chart.update_layout(
        xaxis_title=None,
        yaxis_title="Nombre de produits-magasin",
    )

    st.plotly_chart(
        status_chart,
        use_container_width=True,
    )


with right_column:
    st.subheader("Réapprovisionnement par catégorie")

    category_summary = (
        filtered_inventory
        .groupby(
            "category_name",
            as_index=False,
        )
        .agg(
            recommended_units=(
                "recommended_order_quantity",
                "sum",
            )
        )
        .sort_values(
            "recommended_units",
            ascending=False,
        )
        .head(10)
    )

    category_chart = px.bar(
        category_summary,
        x="recommended_units",
        y="category_name",
        orientation="h",
        text_auto=True,
        labels={
            "recommended_units": "Quantité recommandée",
            "category_name": "Catégorie",
        },
    )

    category_chart.update_layout(
        xaxis_title="Quantité recommandée",
        yaxis_title=None,
        yaxis={
            "categoryorder": "total ascending",
        },
    )

    st.plotly_chart(
        category_chart,
        use_container_width=True,
    )


# =========================================================
# Priority recommendations
# =========================================================
st.divider()

st.subheader("Priorités de réapprovisionnement")

priority_inventory = (
    filtered_inventory[
        filtered_inventory["recommended_order_quantity"] > 0
    ]
    .sort_values(
        [
            "recommended_order_quantity",
            "backorders",
        ],
        ascending=[False, False],
    )
)

priority_columns = [
    "sku",
    "product_name",
    "category_name",
    "store_display",
    "inventory_health_label",
    "stock_on_hand",
    "quantity_on_order",
    "backorders",
    "average_daily_sales_30d",
    "days_of_stock",
    "reorder_point_units",
    "recommended_order_quantity",
]

priority_display = priority_inventory[
    priority_columns
].rename(
    columns={
        "sku": "SKU",
        "product_name": "Produit",
        "category_name": "Catégorie",
        "store_display": "Magasin",
        "inventory_health_label": "État",
        "stock_on_hand": "Stock disponible",
        "quantity_on_order": "Quantité commandée",
        "backorders": "Backorders",
        "average_daily_sales_30d": "Vente moyenne/jour",
        "days_of_stock": "Couverture en jours",
        "reorder_point_units": "Point de commande",
        "recommended_order_quantity": "Quantité recommandée",
    }
)

st.dataframe(
    priority_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Vente moyenne/jour": st.column_config.NumberColumn(
            format="%.2f",
        ),
        "Couverture en jours": st.column_config.NumberColumn(
            format="%.2f",
        ),
        "Quantité recommandée": st.column_config.NumberColumn(
            format="%.0f",
        ),
    },
)


# =========================================================
# CSV export
# =========================================================
csv_data = priority_display.to_csv(
    index=False,
).encode("utf-8-sig")

st.download_button(
    label="⬇️ Exporter les recommandations en CSV",
    data=csv_data,
    file_name="stockpilot_recommandations_stock.csv",
    mime="text/csv",
    disabled=priority_display.empty,
)


# =========================================================
# Full filtered dataset
# =========================================================
with st.expander("Afficher toutes les données filtrées"):
    st.dataframe(
        filtered_inventory,
        use_container_width=True,
        hide_index=True,
    )