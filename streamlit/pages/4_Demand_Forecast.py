from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from queries import (
    load_latest_demand_forecasts,
    load_latest_replenishment_recommendations,
)


st.set_page_config(
    page_title="Prévisions de demande | StockPilot AI",
    page_icon="🤖",
    layout="wide",
)


st.title("🤖 Prévisions de demande")

st.caption(
    "Prévisions ML de la demande sur les 30 prochains jours "
    "par produit et magasin."
)


# =========================================================
# Load data
# =========================================================

try:
    forecasts = load_latest_demand_forecasts()
    replenishment = (
        load_latest_replenishment_recommendations()
    )

except Exception as error:
    st.error(
        "Impossible de charger les prévisions ML."
    )
    st.exception(error)
    st.stop()


if forecasts.empty:
    st.warning(
        "Aucune prévision terminée n'est disponible."
    )
    st.stop()


# =========================================================
# Basic cleaning
# =========================================================

forecasts["forecast_date"] = pd.to_datetime(
    forecasts["forecast_date"]
)

numeric_columns = [
    "predicted_quantity",
    "stock_on_hand",
    "quantity_on_order",
    "backorders",
    "inventory_position",
    "days_of_stock",
    "recommended_order_quantity",
]

for column in numeric_columns:
    forecasts[column] = pd.to_numeric(
        forecasts[column],
        errors="coerce",
    ).fillna(0.0)


# =========================================================
# Metadata
# =========================================================

metadata = forecasts.iloc[0]

with st.expander(
    "Informations sur le modèle",
    expanded=False,
):
    metadata_columns = st.columns(5)

    metadata_columns[0].metric(
        "Version MLflow",
        int(metadata["model_version"]),
    )

    metadata_columns[1].metric(
        "Alias",
        str(metadata["model_alias"]),
    )

    metadata_columns[2].metric(
        "Horizon",
        f"{int(metadata['horizon_days'])} jours",
    )

    metadata_columns[3].metric(
        "Début prévision",
        str(
            pd.to_datetime(
                metadata["forecast_start_date"]
            ).date()
        ),
    )

    metadata_columns[4].metric(
        "Fin prévision",
        str(
            pd.to_datetime(
                metadata["forecast_end_date"]
            ).date()
        ),
    )

    st.caption(
        f"Forecast run : "
        f"{metadata['forecast_run_id']}"
    )


# =========================================================
# Sidebar filters
# =========================================================

with st.sidebar:

    st.header("Filtres prévisions")

    store_options = sorted(
        forecasts["store_name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_stores = st.multiselect(
        "Magasins",
        options=store_options,
        default=store_options,
    )

    category_options = sorted(
        forecasts["category_name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_categories = st.multiselect(
        "Catégories",
        options=category_options,
        default=category_options,
    )

    search_text = st.text_input(
        "Produit",
        placeholder="Nom ou SKU",
    )


# =========================================================
# Apply filters
# =========================================================

filtered = forecasts.copy()

filtered = filtered[
    filtered["store_name"]
    .astype(str)
    .isin(selected_stores)
]

filtered = filtered[
    filtered["category_name"]
    .astype(str)
    .isin(selected_categories)
]


if search_text:

    normalized_search = (
        search_text
        .strip()
        .lower()
    )

    filtered = filtered[
        (
            filtered["product_name"]
            .fillna("")
            .str.lower()
            .str.contains(
                normalized_search,
                regex=False,
            )
        )
        |
        (
            filtered["sku"]
            .fillna("")
            .str.lower()
            .str.contains(
                normalized_search,
                regex=False,
            )
        )
    ]


if filtered.empty:
    st.warning(
        "Aucune prévision ne correspond aux filtres."
    )
    st.stop()


# =========================================================
# Product-store summary
# =========================================================

series_summary = (
    filtered
    .groupby(
        [
            "tenant_id",
            "store_id",
            "store_name",
            "product_id",
            "sku",
            "product_name",
            "category_name",
        ],
        as_index=False,
    )
    .agg(
        forecast_30d=(
            "predicted_quantity",
            "sum",
        ),
        average_daily_forecast=(
            "predicted_quantity",
            "mean",
        ),
        stock_on_hand=(
            "stock_on_hand",
            "first",
        ),
        quantity_on_order=(
            "quantity_on_order",
            "first",
        ),
        backorders=(
            "backorders",
            "first",
        ),
        inventory_position=(
            "inventory_position",
            "first",
        ),
        current_days_of_stock=(
            "days_of_stock",
            "first",
        ),
        current_recommended_order=(
            "recommended_order_quantity",
            "first",
        ),
        inventory_health_status=(
            "inventory_health_status",
            "first",
        ),
    )
)


# =========================================================
# Projected stock gap
# =========================================================

series_summary["forecast_stock_gap"] = (
    series_summary["forecast_30d"]
    - series_summary["inventory_position"]
).clip(lower=0)


series_summary[
    "forecast_coverage_ratio"
] = (
    series_summary[
        "inventory_position"
    ]
    /
    series_summary[
        "forecast_30d"
    ].replace(0, pd.NA)
)


# =========================================================
# KPI
# =========================================================

total_forecast = float(
    filtered["predicted_quantity"].sum()
)

number_of_days = int(
    filtered["forecast_date"].nunique()
)

average_daily_demand = (
    total_forecast / number_of_days
    if number_of_days
    else 0
)

series_count = len(
    series_summary
)

risk_count = int(
    (
        series_summary[
            "forecast_stock_gap"
        ] > 0
    ).sum()
)

forecast_gap_units = float(
    series_summary[
        "forecast_stock_gap"
    ].sum()
)


st.subheader(
    "Indicateurs prévisionnels"
)

kpi_columns = st.columns(5)


kpi_columns[0].metric(
    "Demande prévue",
    f"{total_forecast:,.0f} unités",
)


kpi_columns[1].metric(
    "Demande moyenne / jour",
    f"{average_daily_demand:,.0f}",
)


kpi_columns[2].metric(
    "Produits-magasin",
    f"{series_count:,}",
)


kpi_columns[3].metric(
    "Risque de stock insuffisant",
    risk_count,
)


kpi_columns[4].metric(
    "Écart de stock estimé",
    f"{forecast_gap_units:,.0f} unités",
)


# =========================================================
# Demand timeline
# =========================================================

st.divider()

st.subheader(
    "Évolution de la demande prévue"
)


daily_forecast = (
    filtered
    .groupby(
        "forecast_date",
        as_index=False,
    )
    .agg(
        predicted_quantity=(
            "predicted_quantity",
            "sum",
        )
    )
)


timeline_chart = px.line(
    daily_forecast,
    x="forecast_date",
    y="predicted_quantity",
    markers=True,
    labels={
        "forecast_date":
            "Date",
        "predicted_quantity":
            "Quantité prévue",
    },
)


timeline_chart.update_layout(
    xaxis_title=None,
    yaxis_title="Unités prévues",
)


st.plotly_chart(
    timeline_chart,
    use_container_width=True,
)


# =========================================================
# Category / store charts
# =========================================================

left_column, right_column = (
    st.columns(2)
)


with left_column:

    st.subheader(
        "Demande par catégorie"
    )

    category_forecast = (
        filtered
        .groupby(
            "category_name",
            as_index=False,
        )
        .agg(
            predicted_quantity=(
                "predicted_quantity",
                "sum",
            )
        )
        .sort_values(
            "predicted_quantity",
            ascending=False,
        )
    )

    category_chart = px.bar(
        category_forecast,
        x="predicted_quantity",
        y="category_name",
        orientation="h",
        text_auto=".0f",
        labels={
            "predicted_quantity":
                "Demande prévue",
            "category_name":
                "Catégorie",
        },
    )

    category_chart.update_layout(
        xaxis_title="Unités prévues",
        yaxis_title=None,
        yaxis={
            "categoryorder":
                "total ascending"
        },
    )

    st.plotly_chart(
        category_chart,
        use_container_width=True,
    )


with right_column:

    st.subheader(
        "Demande par magasin"
    )

    store_forecast = (
        filtered
        .groupby(
            "store_name",
            as_index=False,
        )
        .agg(
            predicted_quantity=(
                "predicted_quantity",
                "sum",
            )
        )
        .sort_values(
            "predicted_quantity",
            ascending=False,
        )
    )

    store_chart = px.bar(
        store_forecast,
        x="store_name",
        y="predicted_quantity",
        text_auto=".0f",
        labels={
            "store_name":
                "Magasin",
            "predicted_quantity":
                "Demande prévue",
        },
    )

    store_chart.update_layout(
        xaxis_title=None,
        yaxis_title="Unités prévues",
    )

    st.plotly_chart(
        store_chart,
        use_container_width=True,
    )


# =========================================================
# Replenishment risk
# =========================================================

st.divider()

st.subheader(
    "Priorités selon la demande prévue"
)


priority = (
    series_summary[
        series_summary[
            "forecast_stock_gap"
        ] > 0
    ]
    .sort_values(
        "forecast_stock_gap",
        ascending=False,
    )
)


priority_display = priority[
    [
        "sku",
        "product_name",
        "category_name",
        "store_name",
        "forecast_30d",
        "average_daily_forecast",
        "inventory_position",
        "forecast_stock_gap",
        "current_days_of_stock",
        "inventory_health_status",
    ]
].rename(
    columns={
        "sku":
            "SKU",
        "product_name":
            "Produit",
        "category_name":
            "Catégorie",
        "store_name":
            "Magasin",
        "forecast_30d":
            "Demande prévue 30j",
        "average_daily_forecast":
            "Demande moyenne/jour",
        "inventory_position":
            "Position de stock",
        "forecast_stock_gap":
            "Écart prévisionnel",
        "current_days_of_stock":
            "Couverture actuelle",
        "inventory_health_status":
            "État actuel",
    }
)


st.dataframe(
    priority_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Demande prévue 30j":
            st.column_config.NumberColumn(
                format="%.1f",
            ),

        "Demande moyenne/jour":
            st.column_config.NumberColumn(
                format="%.2f",
            ),

        "Position de stock":
            st.column_config.NumberColumn(
                format="%.0f",
            ),

        "Écart prévisionnel":
            st.column_config.NumberColumn(
                format="%.1f",
            ),

        "Couverture actuelle":
            st.column_config.NumberColumn(
                format="%.1f jours",
            ),
    },
)


# =========================================================
# Export
# =========================================================

csv_data = (
    priority_display
    .to_csv(
        index=False
    )
    .encode(
        "utf-8-sig"
    )
)


st.download_button(
    label=(
        "⬇️ Exporter les priorités "
        "prévisionnelles"
    ),
    data=csv_data,
    file_name=(
        "stockpilot_previsions_demande.csv"
    ),
    mime="text/csv",
    disabled=priority_display.empty,
)

# =========================================================
# Optimized replenishment recommendations
# =========================================================

st.divider()

st.subheader(
    "🛒 Recommandations de réapprovisionnement ML"
)

st.caption(
    "Recommandations calculées à partir de la demande prévue, "
    "du lead time fournisseur, du stock de sécurité, "
    "du MOQ et de la taille des colis."
)


# =========================================================
# Apply same filters
# =========================================================

filtered_replenishment = replenishment.copy()

filtered_replenishment = (
    filtered_replenishment[
        filtered_replenishment[
            "store_name"
        ]
        .astype(str)
        .isin(selected_stores)
    ]
)

filtered_replenishment = (
    filtered_replenishment[
        filtered_replenishment[
            "category_name"
        ]
        .astype(str)
        .isin(selected_categories)
    ]
)


if search_text:

    normalized_search = (
        search_text
        .strip()
        .lower()
    )

    filtered_replenishment = (
        filtered_replenishment[
            (
                filtered_replenishment[
                    "product_name"
                ]
                .fillna("")
                .str.lower()
                .str.contains(
                    normalized_search,
                    regex=False,
                )
            )
            |
            (
                filtered_replenishment[
                    "sku"
                ]
                .fillna("")
                .str.lower()
                .str.contains(
                    normalized_search,
                    regex=False,
                )
            )
        ]
    )


# =========================================================
# Labels
# =========================================================

URGENCY_LABELS = {
    "critical": "Critique",
    "high": "Élevée",
    "medium": "Moyenne",
    "planned": "Planifiée",
    "no_order": "Aucune commande",
}


filtered_replenishment[
    "urgency_label"
] = (
    filtered_replenishment[
        "urgency_level"
    ]
    .map(URGENCY_LABELS)
    .fillna(
        filtered_replenishment[
            "urgency_level"
        ]
    )
)


# =========================================================
# KPI
# =========================================================

orders = filtered_replenishment[
    filtered_replenishment[
        "recommended_order_quantity"
    ] > 0
].copy()


products_to_order = len(orders)

total_order_quantity = float(
    orders[
        "recommended_order_quantity"
    ].sum()
)

critical_orders = int(
    (
        orders["urgency_level"]
        == "critical"
    ).sum()
)

high_orders = int(
    (
        orders["urgency_level"]
        == "high"
    ).sum()
)


replenishment_kpis = st.columns(4)


replenishment_kpis[0].metric(
    "Produits à commander",
    products_to_order,
)


replenishment_kpis[1].metric(
    "Quantité recommandée",
    f"{total_order_quantity:,.0f} unités",
)


replenishment_kpis[2].metric(
    "Commandes critiques",
    critical_orders,
)


replenishment_kpis[3].metric(
    "Priorité élevée",
    high_orders,
)


# =========================================================
# Urgency chart
# =========================================================

urgency_summary = (
    filtered_replenishment
    .groupby(
        "urgency_label",
        as_index=False,
    )
    .agg(
        products=(
            "recommendation_id",
            "count",
        ),
        units_to_order=(
            "recommended_order_quantity",
            "sum",
        ),
    )
)


left, right = st.columns(2)


with left:

    st.subheader(
        "Répartition des priorités"
    )

    urgency_chart = px.bar(
        urgency_summary,
        x="urgency_label",
        y="products",
        text_auto=True,
        labels={
            "urgency_label":
                "Priorité",
            "products":
                "Produits-magasin",
        },
    )

    urgency_chart.update_layout(
        xaxis_title=None,
        yaxis_title="Produits-magasin",
    )

    st.plotly_chart(
        urgency_chart,
        use_container_width=True,
    )


with right:

    st.subheader(
        "Quantités à commander"
    )

    order_chart = px.bar(
        urgency_summary,
        x="urgency_label",
        y="units_to_order",
        text_auto=".0f",
        labels={
            "urgency_label":
                "Priorité",
            "units_to_order":
                "Quantité",
        },
    )

    order_chart.update_layout(
        xaxis_title=None,
        yaxis_title="Unités",
    )

    st.plotly_chart(
        order_chart,
        use_container_width=True,
    )


# =========================================================
# Priority table
# =========================================================

st.subheader(
    "Plan d'achat recommandé"
)


order_display = orders[
    [
        "sku",
        "product_name",
        "category_name",
        "store_name",

        "forecast_30d",
        "forecast_lead_time",
        "lead_time_days",

        "inventory_position",
        "safety_stock_units",

        "minimum_order_quantity",
        "package_size",

        "recommended_order_quantity",

        "estimated_stockout_date",
        "urgency_label",
    ]
].rename(
    columns={
        "sku":
            "SKU",

        "product_name":
            "Produit",

        "category_name":
            "Catégorie",

        "store_name":
            "Magasin",

        "forecast_30d":
            "Prévision 30j",

        "forecast_lead_time":
            "Demande lead time",

        "lead_time_days":
            "Lead time",

        "inventory_position":
            "Position stock",

        "safety_stock_units":
            "Stock sécurité",

        "minimum_order_quantity":
            "MOQ",

        "package_size":
            "Colis",

        "recommended_order_quantity":
            "Quantité à commander",

        "estimated_stockout_date":
            "Rupture estimée",

        "urgency_label":
            "Priorité",
    }
)


st.dataframe(
    order_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Prévision 30j":
            st.column_config.NumberColumn(
                format="%.1f",
            ),

        "Demande lead time":
            st.column_config.NumberColumn(
                format="%.1f",
            ),

        "Stock sécurité":
            st.column_config.NumberColumn(
                format="%.1f",
            ),

        "Quantité à commander":
            st.column_config.NumberColumn(
                format="%.0f",
            ),
    },
)


# =========================================================
# Export purchase plan
# =========================================================

purchase_csv = (
    order_display
    .to_csv(
        index=False
    )
    .encode(
        "utf-8-sig"
    )
)


st.download_button(
    label="⬇️ Exporter le plan d'achat ML",
    data=purchase_csv,
    file_name=(
        "stockpilot_plan_achat_ml.csv"
    ),
    mime="text/csv",
    disabled=order_display.empty,
)
# =========================================================
# Raw forecast data
# =========================================================

with st.expander(
    "Afficher les prévisions journalières"
):

    st.dataframe(
        filtered[
            [
                "forecast_date",
                "store_name",
                "sku",
                "product_name",
                "category_name",
                "predicted_quantity",
                "horizon_day",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )