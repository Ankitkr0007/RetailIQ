
import streamlit as st
import pandas as pd
from sqlalchemy import text
from database.db_connection import get_engine

st.set_page_config(
    page_title="RetailIQ | Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 RetailIQ Dashboard")
st.write("Your business performance at a glance.")

@st.cache_data(ttl=300)
def load_dashboard_metrics():
    engine = get_engine()

    try:
        with engine.connect() as conn:
            customers = conn.execute(
                text("SELECT COUNT(*) FROM customers")
            ).scalar_one()

            products = conn.execute(
                text("SELECT COUNT(*) FROM products")
            ).scalar_one()

            delivered_orders = conn.execute(
                text("""
                    SELECT COUNT(DISTINCT Order_ID)
                    FROM sales
                    WHERE Order_Status = 'Delivered'
                """)
            ).scalar_one()

            delivered_revenue = conn.execute(
                text("""
                    SELECT COALESCE(SUM(Total_Amount), 0)
                    FROM sales
                    WHERE Order_Status = 'Delivered'
                """)
            ).scalar_one()

        return customers, products, delivered_orders, delivered_revenue

    finally:
        engine.dispose()

try:
    customers, products, orders, revenue = load_dashboard_metrics()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Customers", f"{customers:,}")
    col2.metric("Total Products", f"{products:,}")
    col3.metric("Delivered Orders", f"{orders:,}")
    col4.metric("Delivered Revenue", f"₹{revenue:,.2f}")

except Exception as e:
    st.error(f"Could not load dashboard data: {e}")
    st.info(
        "Check your MySQL service, database credentials, "
        "and imported table names."
    )


st.divider()
st.subheader("Monthly Revenue Trend")

@st.cache_data(ttl=300)
def load_monthly_revenue():
    engine = get_engine()

    query = text("""
        SELECT
            DATE_FORMAT(Order_Date, '%Y-%m') AS Month,
            SUM(Total_Amount) AS Revenue
        FROM sales
        WHERE Order_Status = 'Delivered'
        GROUP BY DATE_FORMAT(Order_Date, '%Y-%m')
        ORDER BY Month
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df
    finally:
        engine.dispose()

try:
    monthly_revenue = load_monthly_revenue()

    if not monthly_revenue.empty:
        monthly_revenue["Month"] = pd.to_datetime(
            monthly_revenue["Month"],
            format="%Y-%m"
        )

        st.line_chart(
            monthly_revenue.set_index("Month")["Revenue"],
            y_label="Revenue (₹)",
            x_label="Month"
        )
    else:
        st.info("No delivered sales data available.")

except Exception as e:
    st.error(f"Could not load monthly revenue: {e}")
