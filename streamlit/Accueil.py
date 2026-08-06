from __future__ import annotations

import plotly.express as px
import streamlit as st

from database import test_database_connection
from queries import (
    load_inventory_health_summary,
    load_overview_metrics,
)


st.set_page_config(
    page_title="StockPilot AI",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.title("📦 StockPilot AI")

st.caption(
    "Demand forecasting and inventory optimization dashboard"
)

st.divider()


try:
    connection_information = test_database_connection()
    metrics = load_overview_metrics()
    inventory_summary = load_inventory_health_summary()

except Exception as error:
    st.error("Impossible de se connecter à PostgreSQL.")

    st.exception(error)
    st.stop()


with st.sidebar:
    st.header("Connexion")

    st.success("PostgreSQL connecté")

    st.write(
        f"**Base :** "
        f"{connection_information['database_name']}"
    )

    st.write(
        f"**Utilisateur :** "
        f"{connection_information['database_user']}"
    )

    st.write(
        f"**Schéma par défaut :** "
        f"{connection_information['current_schema']}"
    )


st.subheader("Vue d’ensemble")

first_row = st.columns(4)

first_row[0].metric(
    label="Chiffre d’affaires",
    value=f"{metrics['total_revenue']:,.2f} MAD",
)

first_row[1].metric(
    label="Marge brute",
    value=f"{metrics['total_gross_margin']:,.2f} MAD",
)

first_row[2].metric(
    label="Quantité vendue",
    value=f"{metrics['total_quantity_sold']:,.0f}",
)

first_row[3].metric(
    label="Valeur actuelle du stock",
    value=f"{metrics['current_stock_value']:,.2f} MAD",
)


second_row = st.columns(4)

second_row[0].metric(
    label="Produits en rupture",
    value=int(metrics["out_of_stock_count"]),
)

second_row[1].metric(
    label="Produits en stock faible",
    value=int(metrics["low_stock_count"]),
)

second_row[2].metric(
    label="Produits critiques",
    value=int(metrics["critical_stock_count"]),
)

second_row[3].metric(
    label="Quantité recommandée",
    value=f"{metrics['recommended_order_quantity']:,.0f}",
)


st.divider()

left_column, right_column = st.columns([2, 1])

with left_column:
    st.subheader("État actuel des stocks")

    status_chart = px.bar(
        inventory_summary,
        x="inventory_health_status",
        y="product_store_count",
        labels={
            "inventory_health_status": "Statut",
            "product_store_count": "Nombre de produits-magasin",
        },
        text_auto=True,
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
    st.subheader("Fournisseurs")

    st.metric(
        label="Nombre de fournisseurs",
        value=int(metrics["supplier_count"]),
    )

    st.metric(
        label="Score fournisseur moyen",
        value=f"{metrics['average_supplier_score']:.2f}/100",
    )


st.divider()

st.subheader("Résumé des recommandations")

st.dataframe(
    inventory_summary,
    use_container_width=True,
    hide_index=True,
)