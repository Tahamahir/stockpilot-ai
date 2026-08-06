from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from queries import load_sales_analytics_details


st.set_page_config(
    page_title="Sales Analytics | StockPilot AI",
    page_icon="📈",
    layout="wide",
)


st.title("📈 Analyse des ventes")

st.caption(
    "Suivi du chiffre d’affaires, des quantités vendues, "
    "des marges et des performances commerciales."
)


try:
    sales = load_sales_analytics_details()

except Exception as error:
    st.error("Impossible de charger les données de vente.")
    st.exception(error)
    st.stop()


if sales.empty:
    st.warning("Aucune donnée de vente disponible.")
    st.stop()


sales["sale_date"] = pd.to_datetime(
    sales["sale_date"],
    errors="coerce",
)

sales = sales.dropna(subset=["sale_date"])


# =========================================================
# Sidebar filters
# =========================================================
minimum_date = sales["sale_date"].min().date()
maximum_date = sales["sale_date"].max().date()

with st.sidebar:
    st.header("Filtres")

    selected_date_range = st.date_input(
        label="Période",
        value=(minimum_date, maximum_date),
        min_value=minimum_date,
        max_value=maximum_date,
    )

    store_options = sorted(
        sales["store_name"]
        .fillna("Magasin non renseigné")
        .unique()
        .tolist()
    )

    selected_stores = st.multiselect(
        label="Magasins",
        options=store_options,
        default=store_options,
    )

    category_options = sorted(
        sales["category_name"]
        .fillna("Sans catégorie")
        .unique()
        .tolist()
    )

    selected_categories = st.multiselect(
        label="Catégories",
        options=category_options,
        default=category_options,
    )

    product_search = st.text_input(
        label="Rechercher un produit",
        placeholder="Nom du produit ou SKU",
    )

    aggregation_level = st.selectbox(
        label="Granularité du graphique",
        options=[
            "Jour",
            "Semaine",
            "Mois",
        ],
        index=0,
    )


# =========================================================
# Apply filters
# =========================================================
filtered_sales = sales.copy()

filtered_sales["store_display"] = (
    filtered_sales["store_name"]
    .fillna("Magasin non renseigné")
)

filtered_sales["category_display"] = (
    filtered_sales["category_name"]
    .fillna("Sans catégorie")
)

if isinstance(selected_date_range, tuple):
    if len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
    else:
        start_date = selected_date_range[0]
        end_date = selected_date_range[0]
else:
    start_date = selected_date_range
    end_date = selected_date_range

filtered_sales = filtered_sales[
    filtered_sales["sale_date"].dt.date.between(
        start_date,
        end_date,
    )
]

filtered_sales = filtered_sales[
    filtered_sales["store_display"].isin(selected_stores)
]

filtered_sales = filtered_sales[
    filtered_sales["category_display"].isin(
        selected_categories
    )
]

if product_search:
    normalized_search = product_search.strip().lower()

    filtered_sales = filtered_sales[
        filtered_sales["product_name"]
        .fillna("")
        .str.lower()
        .str.contains(
            normalized_search,
            regex=False,
        )
        |
        filtered_sales["sku"]
        .fillna("")
        .str.lower()
        .str.contains(
            normalized_search,
            regex=False,
        )
    ]


if filtered_sales.empty:
    st.warning(
        "Aucune vente ne correspond aux filtres sélectionnés."
    )
    st.stop()


# =========================================================
# KPI calculations
# =========================================================
total_revenue = float(
    filtered_sales["net_revenue"].sum()
)

total_gross_margin = float(
    filtered_sales["gross_margin"].sum()
)

total_quantity = float(
    filtered_sales["total_quantity_sold"].sum()
)

total_transactions = int(
    filtered_sales["transaction_count"].sum()
)

total_discount = float(
    filtered_sales["total_discount_amount"].sum()
)

average_basket = (
    total_revenue / total_transactions
    if total_transactions > 0
    else 0
)

margin_rate = (
    total_gross_margin / total_revenue * 100
    if total_revenue > 0
    else 0
)


# =========================================================
# KPI display
# =========================================================
st.subheader("Indicateurs commerciaux")

first_row = st.columns(4)

first_row[0].metric(
    label="Chiffre d’affaires",
    value=f"{total_revenue:,.2f} MAD",
)

first_row[1].metric(
    label="Marge brute",
    value=f"{total_gross_margin:,.2f} MAD",
)

first_row[2].metric(
    label="Quantité vendue",
    value=f"{total_quantity:,.0f}",
)

first_row[3].metric(
    label="Transactions",
    value=f"{total_transactions:,}",
)


second_row = st.columns(4)

second_row[0].metric(
    label="Panier moyen",
    value=f"{average_basket:,.2f} MAD",
)

second_row[1].metric(
    label="Taux de marge",
    value=f"{margin_rate:.2f} %",
)

second_row[2].metric(
    label="Remises accordées",
    value=f"{total_discount:,.2f} MAD",
)

second_row[3].metric(
    label="Produits vendus",
    value=filtered_sales["product_id"].nunique(),
)


# =========================================================
# Time aggregation
# =========================================================
if aggregation_level == "Jour":
    filtered_sales["period"] = (
        filtered_sales["sale_date"].dt.date
    )

elif aggregation_level == "Semaine":
    filtered_sales["period"] = (
        filtered_sales["sale_date"]
        .dt.to_period("W")
        .apply(lambda value: value.start_time.date())
    )

else:
    filtered_sales["period"] = (
        filtered_sales["sale_date"]
        .dt.to_period("M")
        .astype(str)
    )


sales_evolution = (
    filtered_sales
    .groupby(
        "period",
        as_index=False,
    )
    .agg(
        net_revenue=("net_revenue", "sum"),
        gross_margin=("gross_margin", "sum"),
        total_quantity_sold=(
            "total_quantity_sold",
            "sum",
        ),
    )
    .sort_values("period")
)


# =========================================================
# Evolution charts
# =========================================================
st.divider()

st.subheader("Évolution des ventes")

revenue_chart = px.line(
    sales_evolution,
    x="period",
    y=[
        "net_revenue",
        "gross_margin",
    ],
    markers=True,
    labels={
        "period": "Période",
        "value": "Montant en MAD",
        "variable": "Indicateur",
    },
)

revenue_chart.update_layout(
    xaxis_title=None,
    yaxis_title="Montant en MAD",
    legend_title_text=None,
)

st.plotly_chart(
    revenue_chart,
    use_container_width=True,
)


# =========================================================
# Category and store analysis
# =========================================================
left_column, right_column = st.columns(2)

with left_column:
    st.subheader("Ventes par catégorie")

    category_summary = (
        filtered_sales
        .groupby(
            "category_display",
            as_index=False,
        )
        .agg(
            net_revenue=("net_revenue", "sum"),
            total_quantity_sold=(
                "total_quantity_sold",
                "sum",
            ),
            gross_margin=("gross_margin", "sum"),
        )
        .sort_values(
            "net_revenue",
            ascending=False,
        )
    )

    category_chart = px.bar(
        category_summary,
        x="category_display",
        y="net_revenue",
        text_auto=".3s",
        labels={
            "category_display": "Catégorie",
            "net_revenue": "Chiffre d’affaires",
        },
    )

    category_chart.update_layout(
        xaxis_title=None,
        yaxis_title="Chiffre d’affaires en MAD",
    )

    st.plotly_chart(
        category_chart,
        use_container_width=True,
    )


with right_column:
    st.subheader("Ventes par magasin")

    store_summary = (
        filtered_sales
        .groupby(
            "store_display",
            as_index=False,
        )
        .agg(
            net_revenue=("net_revenue", "sum"),
            total_quantity_sold=(
                "total_quantity_sold",
                "sum",
            ),
            gross_margin=("gross_margin", "sum"),
        )
        .sort_values(
            "net_revenue",
            ascending=False,
        )
    )

    store_chart = px.bar(
        store_summary,
        x="store_display",
        y="net_revenue",
        text_auto=".3s",
        labels={
            "store_display": "Magasin",
            "net_revenue": "Chiffre d’affaires",
        },
    )

    store_chart.update_layout(
        xaxis_title=None,
        yaxis_title="Chiffre d’affaires en MAD",
    )

    st.plotly_chart(
        store_chart,
        use_container_width=True,
    )


# =========================================================
# Top products
# =========================================================
st.divider()

st.subheader("Produits les plus performants")

product_summary = (
    filtered_sales
    .groupby(
        [
            "sku",
            "product_name",
            "category_display",
        ],
        as_index=False,
    )
    .agg(
        total_quantity_sold=(
            "total_quantity_sold",
            "sum",
        ),
        net_revenue=("net_revenue", "sum"),
        gross_margin=("gross_margin", "sum"),
        transaction_count=(
            "transaction_count",
            "sum",
        ),
    )
)

product_summary["margin_rate_percentage"] = (
    product_summary["gross_margin"]
    / product_summary["net_revenue"].replace(0, pd.NA)
    * 100
).fillna(0)

top_products = (
    product_summary
    .sort_values(
        "net_revenue",
        ascending=False,
    )
    .head(20)
)


top_products_chart = px.bar(
    top_products.sort_values(
        "net_revenue",
        ascending=True,
    ),
    x="net_revenue",
    y="product_name",
    orientation="h",
    text_auto=".3s",
    hover_data={
        "sku": True,
        "category_display": True,
        "total_quantity_sold": True,
        "gross_margin": ":,.2f",
    },
    labels={
        "net_revenue": "Chiffre d’affaires",
        "product_name": "Produit",
    },
)

top_products_chart.update_layout(
    xaxis_title="Chiffre d’affaires en MAD",
    yaxis_title=None,
)

st.plotly_chart(
    top_products_chart,
    use_container_width=True,
)


# =========================================================
# Detailed table
# =========================================================
st.subheader("Détail des performances produits")

product_display = product_summary.rename(
    columns={
        "sku": "SKU",
        "product_name": "Produit",
        "category_display": "Catégorie",
        "total_quantity_sold": "Quantité vendue",
        "net_revenue": "Chiffre d’affaires",
        "gross_margin": "Marge brute",
        "transaction_count": "Transactions",
        "margin_rate_percentage": "Taux de marge",
    }
)

st.dataframe(
    product_display.sort_values(
        "Chiffre d’affaires",
        ascending=False,
    ),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Chiffre d’affaires": st.column_config.NumberColumn(
            format="%.2f MAD",
        ),
        "Marge brute": st.column_config.NumberColumn(
            format="%.2f MAD",
        ),
        "Taux de marge": st.column_config.NumberColumn(
            format="%.2f %%",
        ),
    },
)


# =========================================================
# CSV export
# =========================================================
csv_data = product_display.to_csv(
    index=False,
).encode("utf-8-sig")

st.download_button(
    label="⬇️ Exporter l’analyse des ventes",
    data=csv_data,
    file_name="stockpilot_analyse_ventes.csv",
    mime="text/csv",
)