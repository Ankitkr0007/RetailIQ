
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from database.db_connection import get_engine

import joblib
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_DIR / "models"

kmeans = joblib.load(MODELS_DIR / "customer_kmeans.pkl")
scaler = joblib.load(MODELS_DIR / "customer_scaler.pkl")

customer_clusters = pd.read_csv(
    MODELS_DIR / "customer_clusters.csv"
)

st.set_page_config(
    page_title="RetailIQ | Customer Insights",
    page_icon="👥",
    layout="wide"
)

NAVY = "#142B4A"
TEAL = "#0D9488"
GREEN = "#16A34A"
AMBER = "#D97706"

st.title("👥 Customer Insights")
st.caption("Understand customer value, spending patterns, and loyalty.")

@st.cache_data(ttl=300)
def load_customer_data():
    engine = get_engine()

    try:
        with engine.connect() as conn:
            overview = pd.read_sql(
                text("""
                    SELECT
                        COUNT(*) AS Total_Customers,
                        AVG(Total_Spent) AS Average_Spent,
                        AVG(Total_Orders) AS Average_Orders
                    FROM customers
                """),
                conn
            )

            tier_data = pd.read_sql(
                text("""
                    SELECT
                        Customer_Tier,
                        COUNT(*) AS Customers,
                        AVG(Total_Spent) AS Average_Spent,
                        SUM(Total_Spent) AS Total_Spent
                    FROM customers
                    GROUP BY Customer_Tier
                    ORDER BY Total_Spent DESC
                """),
                conn
            )

            spending_data = pd.read_sql(
                text("""
                    SELECT
                        Customer_ID,
                        Customer_Tier,
                        Total_Spent,
                        Total_Orders,
                        Age_Group
                    FROM customers
                """),
                conn
            )

        return overview, tier_data, spending_data

    finally:
        engine.dispose()


try:
    overview, tier_data, spending_data = load_customer_data()

    total_customers = int(overview.loc[0, "Total_Customers"])
    avg_spent = float(overview.loc[0, "Average_Spent"] or 0)
    avg_orders = float(overview.loc[0, "Average_Orders"] or 0)

    # Customer KPI cards
    col1, col2, col3 = st.columns(3)

    col1.metric("Total Customers", f"{total_customers:,}")
    col2.metric("Average Customer Spend", f"₹{avg_spent:,.2f}")
    col3.metric("Average Orders per Customer", f"{avg_orders:,.2f}")

    st.divider()

    # Customer tier comparison
    st.subheader("Customer Tier Analysis")
    st.caption("Compare the size and value of each customer tier.")

    left, right = st.columns(2)

    with left:
        fig_count = px.bar(
            tier_data,
            x="Customer_Tier",
            y="Customers",
            color="Customer_Tier",
            color_discrete_map={
                "Platinum": NAVY,
                "Gold": "#D4A72C",
                "Silver": "#94A3B8"
            },
            text="Customers",
            labels={
                "Customer_Tier": "Customer Tier",
                "Customers": "Number of Customers"
            }
        )

        fig_count.update_traces(
            texttemplate="%{y:,}",
            textposition="outside"
        )

        fig_count.update_layout(
            template="plotly_white",
            showlegend=False,
            font_color=NAVY,
            margin=dict(l=10, r=15, t=25, b=10),
            yaxis=dict(title="Customers", gridcolor="#E8EEF4"),
            xaxis=dict(title=None)
        )

        st.plotly_chart(fig_count, use_container_width=True)

    with right:
        fig_spend = px.bar(
            tier_data,
            x="Customer_Tier",
            y="Average_Spent",
            color="Customer_Tier",
            color_discrete_map={
                "Platinum": NAVY,
                "Gold": "#D4A72C",
                "Silver": "#94A3B8"
            },
            text="Average_Spent",
            labels={
                "Customer_Tier": "Customer Tier",
                "Average_Spent": "Average Customer Spend (₹)"
            }
        )

        fig_spend.update_traces(
            texttemplate="₹%{y:,.0f}",
            textposition="outside"
        )

        fig_spend.update_layout(
            template="plotly_white",
            showlegend=False,
            font_color=NAVY,
            margin=dict(l=10, r=15, t=25, b=10),
            yaxis=dict(title="Average Spend (₹)", gridcolor="#E8EEF4"),
            xaxis=dict(title=None)
        )

        st.plotly_chart(fig_spend, use_container_width=True)

    # Spending distribution
    st.divider()
    st.subheader("Customer Spending Distribution")
    st.caption("Explore how spending varies between individual customers.")

    fig_distribution = px.histogram(
        spending_data,
        x="Total_Spent",
        color="Customer_Tier",
        color_discrete_map={
            "Platinum": NAVY,
            "Gold": "#D4A72C",
            "Silver": "#94A3B8"
        },
        nbins=40,
        labels={
            "Total_Spent": "Customer Total Spend (₹)",
            "count": "Number of Customers",
            "Customer_Tier": "Customer Tier"
        },
        opacity=0.8
    )

    fig_distribution.update_layout(
        template="plotly_white",
        barmode="group",
        font_color=NAVY,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(gridcolor="#E8EEF4"),
        yaxis=dict(title="Number of Customers", gridcolor="#E8EEF4")
    )

    st.plotly_chart(fig_distribution, use_container_width=True)

    # Customer-level data preview
    with st.expander("View customer data sample"):
        st.dataframe(
            spending_data.head(100),
            use_container_width=True,
            hide_index=True
        )

    # Initial business insight
    if not tier_data.empty:
        top_tier = tier_data.iloc[0]["Customer_Tier"]
        st.info(
            f"**Highest total spending tier:** {top_tier}. "
            "Use the charts above to compare customer volume "
            "with average spending."
        )

except Exception as e:
    st.error(f"Could not load customer insights: {e}")
    st.info(
        "Check your MySQL connection and confirm that the "
        "customers table contains the required columns."
    )


st.divider()
st.subheader("🤖 AI-Powered Customer Segmentation")
st.caption("Customer groups generated by the trained K-Means model.")

cluster_summary = (
    customer_clusters
    .groupby("Cluster")
    .agg(Customers=("Customer_ID", "count"))
    .reset_index()
)

st.dataframe(cluster_summary, use_container_width=True)

st.bar_chart(
    cluster_summary.set_index("Cluster")["Customers"],
    y_label="Number of Customers"
)