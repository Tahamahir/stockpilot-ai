from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from queries import load_supplier_performance_details


st.set_page_config(
    page_title="Supplier Performance | StockPilot AI",
    page_icon="🚚",
    layout="wide",
)


PERFORMANCE_TIER_LABELS = {
    "excellent": "Excellent",
    "good": "Bon",
    "needs_monitoring": "À surveiller",
    "critical": "Critique",
}


st.title("🚚 Performance des fournisseurs")

st.caption(
    "Évaluation des fournisseurs selon les délais de livraison, "
    "les quantités reçues et la fiabilité globale."
)


try:
    suppliers = load_supplier_performance_details()

except Exception as error:
    st.error("Impossible de charger les données fournisseurs.")
    st.exception(error)
    st.stop()


if suppliers.empty:
    st.warning("Aucune donnée fournisseur disponible.")
    st.stop()


numeric_columns = [
    "supplier_score",
    "quantity_fulfillment_rate_percentage",
    "on_time_delivery_rate_percentage",
    "average_expected_lead_time_days",
    "average_actual_lead_time_days",
    "average_delivery_delay_days",
]

for column in numeric_columns:
    suppliers[column] = pd.to_numeric(
        suppliers[column],
        errors="coerce",
    )


suppliers["performance_tier_label"] = (
    suppliers["supplier_performance_tier"]
    .map(PERFORMANCE_TIER_LABELS)
    .fillna(suppliers["supplier_performance_tier"])
)


# =========================================================
# Sidebar filters
# =========================================================
with st.sidebar:
    st.header("Filtres")

    tier_options = sorted(
        suppliers["performance_tier_label"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_tiers = st.multiselect(
        label="Niveau de performance",
        options=tier_options,
        default=tier_options,
    )

    minimum_score = st.slider(
        label="Score fournisseur minimal",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
    )

    supplier_search = st.text_input(
        label="Rechercher un fournisseur",
        placeholder="Nom ou code fournisseur",
    )

    only_late_suppliers = st.checkbox(
        label="Afficher uniquement les fournisseurs avec retards",
        value=False,
    )


# =========================================================
# Apply filters
# =========================================================
filtered_suppliers = suppliers.copy()

filtered_suppliers = filtered_suppliers[
    filtered_suppliers["performance_tier_label"]
    .isin(selected_tiers)
]

filtered_suppliers = filtered_suppliers[
    filtered_suppliers["supplier_score"]
    .fillna(0)
    >= minimum_score
]

if supplier_search:
    normalized_search = supplier_search.strip().lower()

    filtered_suppliers = filtered_suppliers[
        filtered_suppliers["supplier_name"]
        .fillna("")
        .str.lower()
        .str.contains(
            normalized_search,
            regex=False,
        )
        |
        filtered_suppliers["supplier_code"]
        .fillna("")
        .str.lower()
        .str.contains(
            normalized_search,
            regex=False,
        )
    ]

if only_late_suppliers:
    filtered_suppliers = filtered_suppliers[
        filtered_suppliers["late_deliveries"] > 0
    ]


if filtered_suppliers.empty:
    st.warning(
        "Aucun fournisseur ne correspond aux filtres sélectionnés."
    )
    st.stop()


# =========================================================
# KPI calculations
# =========================================================
supplier_count = len(filtered_suppliers)

average_supplier_score = float(
    filtered_suppliers["supplier_score"]
    .fillna(0)
    .mean()
)

average_on_time_rate = float(
    filtered_suppliers[
        "on_time_delivery_rate_percentage"
    ]
    .fillna(0)
    .mean()
)

average_fulfillment_rate = float(
    filtered_suppliers[
        "quantity_fulfillment_rate_percentage"
    ]
    .fillna(0)
    .mean()
)

total_purchase_orders = int(
    filtered_suppliers["total_purchase_orders"].sum()
)

late_deliveries = int(
    filtered_suppliers["late_deliveries"].sum()
)

suppliers_to_monitor = int(
    filtered_suppliers[
        "supplier_performance_tier"
    ]
    .isin(
        [
            "needs_monitoring",
            "critical",
        ]
    )
    .sum()
)

average_delivery_delay = float(
    filtered_suppliers["average_delivery_delay_days"]
    .dropna()
    .mean()
)

if pd.isna(average_delivery_delay):
    average_delivery_delay = 0.0


# =========================================================
# KPI display
# =========================================================
st.subheader("Indicateurs fournisseurs")

first_row = st.columns(4)

first_row[0].metric(
    label="Nombre de fournisseurs",
    value=supplier_count,
)

first_row[1].metric(
    label="Score moyen",
    value=f"{average_supplier_score:.2f}/100",
)

first_row[2].metric(
    label="Livraisons à temps",
    value=f"{average_on_time_rate:.2f} %",
)

first_row[3].metric(
    label="Taux de satisfaction des quantités",
    value=f"{average_fulfillment_rate:.2f} %",
)


second_row = st.columns(4)

second_row[0].metric(
    label="Commandes fournisseurs",
    value=f"{total_purchase_orders:,}",
)

second_row[1].metric(
    label="Livraisons en retard",
    value=f"{late_deliveries:,}",
)

second_row[2].metric(
    label="Fournisseurs à surveiller",
    value=suppliers_to_monitor,
)

second_row[3].metric(
    label="Retard moyen",
    value=f"{average_delivery_delay:.2f} jours",
)


# =========================================================
# Supplier score ranking
# =========================================================
st.divider()

st.subheader("Classement des fournisseurs")

ranking_data = filtered_suppliers.sort_values(
    [
        "supplier_score",
        "supplier_name",
    ],
    ascending=[
        True,
        True,
    ],
)

ranking_chart = px.bar(
    ranking_data,
    x="supplier_score",
    y="supplier_name",
    orientation="h",
    text_auto=".2f",
    hover_data={
        "supplier_code": True,
        "supplier_rank": True,
        "performance_tier_label": True,
        "on_time_delivery_rate_percentage": ":.2f",
        "quantity_fulfillment_rate_percentage": ":.2f",
        "total_purchase_orders": True,
    },
    labels={
        "supplier_score": "Score fournisseur",
        "supplier_name": "Fournisseur",
        "performance_tier_label": "Niveau",
        "on_time_delivery_rate_percentage":
            "Taux de livraison à temps",
        "quantity_fulfillment_rate_percentage":
            "Taux de satisfaction des quantités",
        "total_purchase_orders": "Nombre de commandes",
    },
)

ranking_chart.update_layout(
    xaxis_title="Score sur 100",
    yaxis_title=None,
    xaxis={
        "range": [
            0,
            100,
        ]
    },
)

st.plotly_chart(
    ranking_chart,
    use_container_width=True,
)


# =========================================================
# Reliability analysis
# =========================================================
left_column, right_column = st.columns(2)

with left_column:
    st.subheader("Fiabilité des livraisons")

    reliability_chart = px.scatter(
        filtered_suppliers,
        x="on_time_delivery_rate_percentage",
        y="quantity_fulfillment_rate_percentage",
        size="total_purchase_orders",
        hover_name="supplier_name",
        hover_data={
            "supplier_score": ":.2f",
            "supplier_rank": True,
            "average_delivery_delay_days": ":.2f",
            "total_purchase_orders": True,
        },
        labels={
            "on_time_delivery_rate_percentage":
                "Livraisons à temps (%)",
            "quantity_fulfillment_rate_percentage":
                "Quantités reçues (%)",
            "total_purchase_orders":
                "Nombre de commandes",
        },
        size_max=50,
    )

    reliability_chart.update_layout(
        xaxis={
            "range": [
                0,
                100,
            ]
        },
        yaxis={
            "range": [
                0,
                105,
            ]
        },
    )

    st.plotly_chart(
        reliability_chart,
        use_container_width=True,
    )


with right_column:
    st.subheader("Commandes par fournisseur")

    orders_chart_data = (
        filtered_suppliers[
            [
                "supplier_name",
                "delivered_orders",
                "open_orders",
                "cancelled_orders",
            ]
        ]
        .melt(
            id_vars="supplier_name",
            var_name="order_status",
            value_name="order_count",
        )
    )

    order_status_labels = {
        "delivered_orders": "Livrées",
        "open_orders": "Ouvertes",
        "cancelled_orders": "Annulées",
    }

    orders_chart_data["order_status"] = (
        orders_chart_data["order_status"]
        .map(order_status_labels)
    )

    orders_chart = px.bar(
        orders_chart_data,
        x="supplier_name",
        y="order_count",
        color="order_status",
        barmode="stack",
        labels={
            "supplier_name": "Fournisseur",
            "order_count": "Nombre de commandes",
            "order_status": "Statut",
        },
    )

    orders_chart.update_layout(
        xaxis_title=None,
        yaxis_title="Nombre de commandes",
        legend_title_text=None,
    )

    st.plotly_chart(
        orders_chart,
        use_container_width=True,
    )


# =========================================================
# Lead-time analysis
# =========================================================
st.divider()

st.subheader("Analyse des délais de livraison")

lead_time_data = filtered_suppliers[
    [
        "supplier_name",
        "average_expected_lead_time_days",
        "average_actual_lead_time_days",
    ]
].melt(
    id_vars="supplier_name",
    var_name="lead_time_type",
    value_name="lead_time_days",
)

lead_time_labels = {
    "average_expected_lead_time_days": "Délai prévu",
    "average_actual_lead_time_days": "Délai réel",
}

lead_time_data["lead_time_type"] = (
    lead_time_data["lead_time_type"]
    .map(lead_time_labels)
)

lead_time_chart = px.bar(
    lead_time_data,
    x="supplier_name",
    y="lead_time_days",
    color="lead_time_type",
    barmode="group",
    labels={
        "supplier_name": "Fournisseur",
        "lead_time_days": "Nombre de jours",
        "lead_time_type": "Type de délai",
    },
)

lead_time_chart.update_layout(
    xaxis_title=None,
    yaxis_title="Délai moyen en jours",
    legend_title_text=None,
)

st.plotly_chart(
    lead_time_chart,
    use_container_width=True,
)


# =========================================================
# Detailed supplier table
# =========================================================
st.divider()

st.subheader("Détail des performances")

supplier_columns = [
    "supplier_rank",
    "supplier_code",
    "supplier_name",
    "performance_tier_label",
    "supplier_score",
    "total_purchase_orders",
    "delivered_orders",
    "open_orders",
    "late_deliveries",
    "on_time_delivery_rate_percentage",
    "quantity_fulfillment_rate_percentage",
    "average_expected_lead_time_days",
    "average_actual_lead_time_days",
    "average_delivery_delay_days",
]

supplier_display = filtered_suppliers[
    supplier_columns
].rename(
    columns={
        "supplier_rank": "Rang",
        "supplier_code": "Code",
        "supplier_name": "Fournisseur",
        "performance_tier_label": "Niveau",
        "supplier_score": "Score",
        "total_purchase_orders": "Commandes",
        "delivered_orders": "Livrées",
        "open_orders": "Ouvertes",
        "late_deliveries": "En retard",
        "on_time_delivery_rate_percentage":
            "Livraisons à temps",
        "quantity_fulfillment_rate_percentage":
            "Quantités reçues",
        "average_expected_lead_time_days":
            "Délai prévu",
        "average_actual_lead_time_days":
            "Délai réel",
        "average_delivery_delay_days":
            "Retard moyen",
    }
)

supplier_display = supplier_display.sort_values(
    [
        "Rang",
        "Fournisseur",
    ]
)

st.dataframe(
    supplier_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Score": st.column_config.ProgressColumn(
            format="%.2f",
            min_value=0,
            max_value=100,
        ),
        "Livraisons à temps":
            st.column_config.NumberColumn(
                format="%.2f %%",
            ),
        "Quantités reçues":
            st.column_config.NumberColumn(
                format="%.2f %%",
            ),
        "Délai prévu":
            st.column_config.NumberColumn(
                format="%.2f jours",
            ),
        "Délai réel":
            st.column_config.NumberColumn(
                format="%.2f jours",
            ),
        "Retard moyen":
            st.column_config.NumberColumn(
                format="%.2f jours",
            ),
    },
)


# =========================================================
# CSV export
# =========================================================
csv_data = supplier_display.to_csv(
    index=False,
).encode("utf-8-sig")

st.download_button(
    label="⬇️ Exporter les performances fournisseurs",
    data=csv_data,
    file_name="stockpilot_performance_fournisseurs.csv",
    mime="text/csv",
)