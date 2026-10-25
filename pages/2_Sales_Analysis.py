
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from database.db_connection import get_engine

st.set_page_config(
    page_title="RetailIQ | Sales Analysis",
    page_icon="📈",
    layout="wide"
)

# RetailIQ color palette
NAVY = "#142B4A"
TEAL = "#0D9488"
GREEN = "#16A34A"
RED = "#DC2626"
AMBER = "#D97706"
SLATE = "#64748B"

st.title("📈 Sales Analysis")
st.caption("Understand revenue, payment preferences, and order performance.")

@st.cache_data(ttl=300)
def load_sales_data():
    engine = get_engine()

    try:
        with engine.connect() as conn:
            summary = pd.read_sql(
                text("""
                    SELECT
                        COUNT(DISTINCT Order_ID) AS Delivered_Orders,
                        COALESCE(SUM(Total_Amount), 0) AS Revenue,
                        COALESCE(AVG(Total_Amount), 0) AS Average_Order_Value
                    FROM sales
                    WHERE Order_Status = 'Delivered'
                """),
                conn
            )

            category_df = pd.read_sql(
                text("""
                    SELECT
                        p.Category,
                        SUM(s.Total_Amount) AS Revenue
                    FROM sales s
                    JOIN products p
                        ON s.Product_ID = p.Product_ID
                    WHERE s.Order_Status = 'Delivered'
                    GROUP BY p.Category
                    ORDER BY Revenue DESC
                """),
                conn
            )

            payment_df = pd.read_sql(
                text("""
                    SELECT
                        Payment_Mode,
                        COUNT(DISTINCT Order_ID) AS Orders
                    FROM sales
                    WHERE Order_Status = 'Delivered'
                    GROUP BY Payment_Mode
                    ORDER BY Orders DESC
                """),
                conn
            )

            status_df = pd.read_sql(
                text("""
                    SELECT
                        Order_Status,
                        COUNT(DISTINCT Order_ID) AS Orders
                    FROM sales
                    GROUP BY Order_Status
                """),
                conn
            )

        return summary, category_df, payment_df, status_df

    finally:
        engine.dispose()


try:
    summary, category_df, payment_df, status_df = load_sales_data()

    revenue = float(summary.loc[0, "Revenue"])
    orders = int(summary.loc[0, "Delivered_Orders"])
    avg_order_value = float(summary.loc[0, "Average_Order_Value"])

    # KPI cards
    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Delivered Revenue",
        f"₹{revenue:,.0f}",
        help="Revenue from delivered orders."
    )

    col2.metric(
        "Delivered Orders",
        f"{orders:,}",
        help="Number of unique delivered orders."
    )

    col3.metric(
        "Average Order Value",
        f"₹{avg_order_value:,.2f}",
        help="Average amount per delivered order."
    )

    st.divider()

    # Revenue by category
    st.subheader("Revenue by Product Category")
    st.caption("Compare the contribution of each category to delivered revenue.")

    if not category_df.empty:
        fig_category = px.bar(
            category_df,
            x="Category",
            y="Revenue",
            color="Revenue",
            color_continuous_scale=["#99D9D2", TEAL, NAVY],
            text="Revenue",
            labels={
                "Category": "Product Category",
                "Revenue": "Revenue (₹)"
            }
        )

        fig_category.update_traces(
            texttemplate="₹%{y:,.0f}",
            textposition="outside",
            cliponaxis=False
        )

        fig_category.update_layout(
            template="plotly_white",
            showlegend=False,
            coloraxis_showscale=False,
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font_color=NAVY,
            margin=dict(l=10, r=20, t=25, b=10),
            yaxis=dict(
                showgrid=True,
                gridcolor="#E8EEF4",
                tickformat="~s",
                title="Revenue (₹)"
            ),
            xaxis=dict(title=None)
        )

        st.plotly_chart(fig_category, use_container_width=True)

        top_category = category_df.iloc[0]["Category"]
        top_revenue = float(category_df.iloc[0]["Revenue"])
        revenue_share = top_revenue / revenue * 100 if revenue else 0

        st.info(
            f"**Top category:** {top_category} generated "
            f"₹{top_revenue:,.0f}, approximately "
            f"{revenue_share:.1f}% of delivered revenue."
        )

    st.divider()

    # Payment method and order status
    left, right = st.columns(2)

    with left:
        st.subheader("Payment Preferences")
        st.caption("Share of delivered orders by payment method.")

        if not payment_df.empty:
            fig_payment = px.pie(
                payment_df,
                names="Payment_Mode",
                values="Orders",
                hole=0.58,
                color="Payment_Mode",
                color_discrete_map={
                    "UPI": TEAL,
                    "COD": NAVY,
                    "Debit Card": "#60A5FA",
                    "Credit Card": "#A78BFA"
                }
            )

            fig_payment.update_traces(
                textposition="inside",
                textinfo="percent",
                hovertemplate=(
                    "%{label}<br>"
                    "Orders: %{value:,}<br>"
                    "Share: %{percent}<extra></extra>"
                )
            )

            fig_payment.update_layout(
                template="plotly_white",
                showlegend=True,
                legend_title_text="Payment Method",
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font_color=NAVY,
                margin=dict(l=10, r=10, t=20, b=10)
            )

            st.plotly_chart(fig_payment, use_container_width=True)

            preferred = payment_df.iloc[0]
            st.caption(
                f"Most used method: **{preferred['Payment_Mode']}** "
                f"({int(preferred['Orders']):,} orders)."
            )

    with right:
        st.subheader("Order Status Overview")
        st.caption("All orders, including cancelled and returned orders.")

        status_colors = {
            "Delivered": GREEN,
            "Cancelled": RED,
            "Returned": AMBER,
            "Shipped": "#3B82F6",
            "Processing": SLATE
        }

        if not status_df.empty:
            status_df["Color"] = status_df["Order_Status"].map(
                status_colors
            ).fillna(SLATE)

            fig_status = px.bar(
                status_df.sort_values("Orders", ascending=True),
                x="Orders",
                y="Order_Status",
                orientation="h",
                color="Order_Status",
                color_discrete_map=status_colors,
                text="Orders",
                labels={
                    "Orders": "Number of Orders",
                    "Order_Status": "Status"
                }
            )

            fig_status.update_traces(
                texttemplate="%{x:,}",
                textposition="outside",
                cliponaxis=False
            )

            fig_status.update_layout(
                template="plotly_white",
                showlegend=False,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font_color=NAVY,
                margin=dict(l=10, r=45, t=20, b=10),
                xaxis=dict(
                    showgrid=True,
                    gridcolor="#E8EEF4",
                    title="Number of Orders"
                ),
                yaxis=dict(title=None)
            )

            st.plotly_chart(fig_status, use_container_width=True)

except Exception as e:
    st.error(f"Could not load sales analysis: {e}")
    st.info(
        "Check your MySQL connection and confirm that the "
        "customers, products, and sales tables are available."
    )
