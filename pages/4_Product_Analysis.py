
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from database.db_connection import get_engine

st.set_page_config(
    page_title="RetailIQ | Product Analysis",
    page_icon="📦",
    layout="wide"
)

NAVY = "#142B4A"
TEAL = "#0D9488"
GREEN = "#16A34A"
AMBER = "#D97706"
RED = "#DC2626"
SLATE = "#64748B"

st.title("📦 Product Analysis")
st.caption(
    "Discover best-selling products, category performance, "
    "ratings, and inventory risks."
)


@st.cache_data(ttl=300)
def load_product_data():
    engine = get_engine()

    try:
        with engine.connect() as conn:
            summary = pd.read_sql(
                text("""
                    SELECT
                        COUNT(*) AS Total_Products,
                        AVG(Avg_Rating) AS Average_Rating,
                        SUM(Stock_Quantity) AS Total_Stock,
                        SUM(CASE WHEN Stock_Quantity = 0
                            THEN 1 ELSE 0 END) AS Out_Of_Stock
                    FROM products
                """),
                conn
            )

            category_data = pd.read_sql(
                text("""
                    SELECT
                        p.Category,
                        SUM(s.Total_Amount) AS Revenue,
                        SUM(s.Quantity) AS Units_Sold,
                        COUNT(DISTINCT s.Order_ID) AS Orders
                    FROM sales s
                    JOIN products p
                        ON s.Product_ID = p.Product_ID
                    WHERE s.Order_Status = 'Delivered'
                    GROUP BY p.Category
                    ORDER BY Revenue DESC
                """),
                conn
            )

            top_products = pd.read_sql(
                text("""
                    SELECT
                        p.Product_ID,
                        p.Product_Name,
                        p.Category,
                        p.Stock_Quantity,
                        p.Avg_Rating,
                        COALESCE(SUM(s.Total_Amount), 0) AS Revenue,
                        COALESCE(SUM(s.Quantity), 0) AS Units_Sold
                    FROM products p
                    LEFT JOIN sales s
                        ON p.Product_ID = s.Product_ID
                        AND s.Order_Status = 'Delivered'
                    GROUP BY
                        p.Product_ID,
                        p.Product_Name,
                        p.Category,
                        p.Stock_Quantity,
                        p.Avg_Rating
                    ORDER BY Revenue DESC
                    LIMIT 10
                """),
                conn
            )

            inventory = pd.read_sql(
                text("""
                    SELECT
                        Product_ID,
                        Product_Name,
                        Category,
                        Stock_Quantity,
                        Selling_Price,
                        Avg_Rating
                    FROM products
                    ORDER BY Stock_Quantity ASC
                """),
                conn
            )

        return summary, category_data, top_products, inventory

    finally:
        engine.dispose()


try:
    summary, category_data, top_products, inventory = load_product_data()

    total_products = int(summary.loc[0, "Total_Products"])
    average_rating = float(summary.loc[0, "Average_Rating"] or 0)
    total_stock = int(summary.loc[0, "Total_Stock"] or 0)
    out_of_stock = int(summary.loc[0, "Out_Of_Stock"] or 0)

    # KPI cards
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Products", f"{total_products:,}")
    col2.metric("Average Rating", f"{average_rating:.2f} / 5")
    col3.metric("Units in Stock", f"{total_stock:,}")
    col4.metric("Out-of-Stock Products", f"{out_of_stock:,}")

    st.divider()

    # Revenue by category
    st.subheader("Category Performance")
    st.caption("Compare revenue and units sold across product categories.")

    left, right = st.columns(2)

    with left:
        fig_category = px.bar(
            category_data.sort_values("Revenue", ascending=False),
            x="Category",
            y="Revenue",
            color="Revenue",
            color_continuous_scale=["#99D9D2", TEAL, NAVY],
            labels={"Revenue": "Delivered Revenue (₹)"}
        )

        fig_category.update_layout(
            template="plotly_white",
            showlegend=False,
            coloraxis_showscale=False,
            font_color=NAVY,
            xaxis_title=None,
            yaxis_title="Revenue (₹)",
            yaxis_tickformat="~s",
            margin=dict(l=10, r=10, t=20, b=10)
        )

        st.plotly_chart(fig_category, use_container_width=True)

    with right:
        fig_units = px.bar(
            category_data.sort_values("Units_Sold", ascending=False),
            x="Category",
            y="Units_Sold",
            color="Units_Sold",
            color_continuous_scale=["#99D9D2", TEAL, NAVY],
            labels={"Units_Sold": "Units Sold"}
        )

        fig_units.update_layout(
            template="plotly_white",
            showlegend=False,
            coloraxis_showscale=False,
            font_color=NAVY,
            xaxis_title=None,
            yaxis_title="Units Sold",
            yaxis_tickformat="~s",
            margin=dict(l=10, r=10, t=20, b=10)
        )

        st.plotly_chart(fig_units, use_container_width=True)

    if not category_data.empty:
        best_category = category_data.iloc[0]
        st.info(
            f"**Highest-revenue category:** {best_category['Category']} "
            f"generated ₹{float(best_category['Revenue']):,.0f} "
            "from delivered orders."
        )

    st.divider()

    # Top products
    st.subheader("Top 10 Products by Delivered Revenue")
    st.caption("Products ranked by revenue from delivered orders.")

    fig_top = px.bar(
        top_products.sort_values("Revenue", ascending=True),
        x="Revenue",
        y="Product_Name",
        color="Revenue",
        color_continuous_scale=["#99D9D2", TEAL, NAVY],
        orientation="h",
        hover_data=["Category", "Units_Sold", "Stock_Quantity", "Avg_Rating"],
        labels={
            "Revenue": "Delivered Revenue (₹)",
            "Product_Name": "Product",
            "Category": "Category",
            "Units_Sold": "Units Sold",
            "Stock_Quantity": "Stock",
            "Avg_Rating": "Rating"
        }
    )

    fig_top.update_layout(
        template="plotly_white",
        showlegend=False,
        coloraxis_showscale=False,
        font_color=NAVY,
        xaxis_title="Revenue (₹)",
        yaxis_title=None,
        xaxis_tickformat="~s",
        margin=dict(l=10, r=15, t=20, b=10)
    )

    st.plotly_chart(fig_top, use_container_width=True)

    st.divider()

    # Inventory
    st.subheader("Inventory Monitoring")
    st.caption(
        "Review the lowest-stock products. Low stock is a screening "
        "signal, not a confirmed stockout forecast."
    )

    low_stock_limit = st.slider(
        "Low-stock threshold (units)",
        min_value=1,
        max_value=100,
        value=10
    )

    low_stock = inventory[
        inventory["Stock_Quantity"] <= low_stock_limit
    ]

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Products at or Below Threshold", f"{len(low_stock):,}")

    with col2:
        st.metric(
            "Products With Stock Available",
            f"{(inventory['Stock_Quantity'] > 0).sum():,}"
        )

    if not low_stock.empty:
        st.dataframe(
            low_stock,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No products are at or below the selected threshold.")

    with st.expander("View all products"):
        st.dataframe(
            inventory,
            use_container_width=True,
            hide_index=True
        )

except Exception as e:
    st.error(f"Could not load product analysis: {e}")
    st.info(
        "Check the MySQL connection and ensure the products and sales "
        "tables contain the expected columns."
    )
