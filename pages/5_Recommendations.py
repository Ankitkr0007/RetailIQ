
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from database.db_connection import get_engine
import joblib
from pathlib import Path


# Project paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_DIR / "models"

# Load saved recommendation artifacts
@st.cache_resource
def load_recommendation_model():
    customer_product_matrix = joblib.load(
        MODELS_DIR / "customer_product_matrix.pkl"
    )

    knn = joblib.load(
        MODELS_DIR / "product_recommender_knn.pkl"
    )

    products_full = pd.read_pickle(
        MODELS_DIR / "recommendation_products.pkl"
    )

    return customer_product_matrix, knn, products_full


def recommend_products(
    customer_id,
    customer_product_matrix,
    knn,
    products_full,
    n_recommendations=5
):
    if customer_id not in customer_product_matrix.index:
        return pd.DataFrame()

    customer_vector = customer_product_matrix.loc[[customer_id]]

    distances, indices = knn.kneighbors(customer_vector)

    # Exclude the target customer
    similar_indices = indices[0][1:]
    similar_distances = distances[0][1:]

    similar_customers = customer_product_matrix.iloc[similar_indices]

    # Weight product purchases by customer similarity
    similarities = 1 - similar_distances
    product_scores = similar_customers.T.dot(similarities)

    # Exclude products the customer already purchased
    purchased_products = customer_product_matrix.loc[customer_id]
    product_scores = product_scores[purchased_products == 0]
    product_scores = product_scores[product_scores > 0]

    top_products = product_scores.sort_values(
        ascending=False
    ).head(n_recommendations)

    recommendations = (
        top_products.rename("Recommendation_Score")
        .rename_axis("Product_ID")
        .reset_index()
        .merge(
            products_full,
            on="Product_ID",
            how="left",
            validate="one_to_one"
        )
    )

    recommendations["Display_Name"] = (
        recommendations["Product_Name"].astype(str)
        + " ("
        + recommendations["Product_ID"].astype(str)
        + ")"
    )

    columns = [
        "Product_ID",
        "Display_Name",
        "Category",
        "Recommendation_Score",
        "Selling_Price",
        "Avg_Rating",
        "Stock_Quantity"
    ]

    return recommendations[
        [col for col in columns if col in recommendations.columns]
    ]



st.set_page_config(
    page_title="RetailIQ | Recommendations",
    page_icon="💡",
    layout="wide"
)

NAVY = "#142B4A"
TEAL = "#0D9488"
GREEN = "#16A34A"
AMBER = "#D97706"
RED = "#DC2626"

st.title("💡 Business Recommendations")
st.caption(
    "Discover opportunities to improve sales, inventory, "
    "and customer engagement."
)


@st.cache_data(ttl=300)
def load_recommendation_data():
    engine = get_engine()

    try:
        with engine.connect() as conn:
            category_data = pd.read_sql(
                text("""
                    SELECT
                        p.Category,
                        SUM(s.Total_Amount) AS Revenue,
                        SUM(s.Quantity) AS Units_Sold
                    FROM sales s
                    JOIN products p
                        ON s.Product_ID = p.Product_ID
                    WHERE s.Order_Status = 'Delivered'
                    GROUP BY p.Category
                    ORDER BY Revenue DESC
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
                        Avg_Rating,
                        Selling_Price
                    FROM products
                    ORDER BY Stock_Quantity ASC
                """),
                conn
            )

            order_status = pd.read_sql(
                text("""
                    SELECT
                        Order_Status,
                        COUNT(DISTINCT Order_ID) AS Orders
                    FROM sales
                    GROUP BY Order_Status
                """),
                conn
            )

            customer_tiers = pd.read_sql(
                text("""
                    SELECT
                        Customer_Tier,
                        COUNT(*) AS Customers,
                        AVG(Total_Spent) AS Average_Spent
                    FROM customers
                    GROUP BY Customer_Tier
                """),
                conn
            )

        return category_data, inventory, order_status, customer_tiers

    finally:
        engine.dispose()


try:
    category_data, inventory, order_status, customer_tiers = (
        load_recommendation_data()
    )

    st.subheader("Priority Business Opportunities")

    # 1. Inventory opportunities
    low_stock = inventory[inventory["Stock_Quantity"] <= 10]

    if not low_stock.empty:
        st.warning(
            f"**Inventory review:** {len(low_stock):,} products "
            "have 10 or fewer units in stock. Review their recent "
            "sales before deciding whether to reorder."
        )
    else:
        st.success(
            "No products currently have 10 or fewer units in stock."
        )

    # 2. Cancellation opportunities
    status_totals = order_status.set_index("Order_Status")["Orders"]
    total_orders = int(status_totals.sum())
    cancelled = int(status_totals.get("Cancelled", 0))
    cancellation_rate = (
        cancelled / total_orders * 100 if total_orders else 0
    )

    if cancellation_rate >= 5:
        st.warning(
            f"**Review cancellations:** {cancellation_rate:.2f}% "
            "of orders are cancelled. Investigate common causes "
            "before deciding on corrective action."
        )
    else:
        st.info(
            f"Cancellation rate: {cancellation_rate:.2f}% "
            "of all orders."
        )

    # 3. Top category opportunity
    if not category_data.empty:
        top_category = category_data.iloc[0]
        st.info(
            f"**Strongest category by revenue:** "
            f"{top_category['Category']} generated "
            f"₹{top_category['Revenue']:,.0f} in delivered revenue. "
            "Review its best-selling products and stock availability "
            "before increasing inventory."
        )

    st.divider()

    # Category revenue opportunity
    st.subheader("Category Performance")

    fig = px.bar(
        category_data.sort_values("Revenue", ascending=True),
        x="Revenue",
        y="Category",
        orientation="h",
        color="Revenue",
        color_continuous_scale=["#99D9D2", TEAL, NAVY],
        labels={
            "Revenue": "Delivered Revenue (₹)",
            "Category": "Category"
        }
    )

    fig.update_layout(
        template="plotly_white",
        showlegend=False,
        coloraxis_showscale=False,
        font_color=NAVY,
        xaxis_tickformat="~s",
        margin=dict(l=10, r=15, t=20, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Inventory review table
    st.subheader("Products to Review for Restocking")

    stock_limit = st.slider(
        "Show products with stock at or below",
        min_value=1,
        max_value=100,
        value=10
    )

    inventory_review = inventory[
        inventory["Stock_Quantity"] <= stock_limit
    ].copy()

    if not inventory_review.empty:
        st.dataframe(
            inventory_review,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No products meet the selected stock threshold.")

    st.divider()

    # Customer tier opportunity
    st.subheader("Customer Engagement Opportunities")

    if not customer_tiers.empty:
        customer_tiers["Average_Spent"] = (
            customer_tiers["Average_Spent"].round(2)
        )

        st.dataframe(
            customer_tiers.sort_values(
                "Average_Spent",
                ascending=False
            ),
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "Consider targeted offers and retention campaigns "
            "for different customer tiers. Validate campaign results "
            "before assuming they will increase sales."
        )

except Exception as e:
    st.error(f"Could not load recommendations: {e}")
    st.info(
        "Check the database connection and required table columns."
    )


st.divider()

st.subheader("Personalized Product Recommendations")

try:
    customer_product_matrix, knn, products_full = (
        load_recommendation_model()
    )

    customer_ids = customer_product_matrix.index.tolist()

    selected_customer = st.selectbox(
        "Select a customer",
        options=customer_ids,
        index=0
    )

    number_of_recommendations = st.slider(
        "Number of recommendations",
        min_value=5,
        max_value=20,
        value=10
    )

    if st.button("Generate Recommendations", type="primary"):
        recommendations = recommend_products(
            selected_customer,
            customer_product_matrix,
            knn,
            products_full,
            number_of_recommendations
        )

        if recommendations.empty:
            st.info("No recommendations are available for this customer.")
        else:
            st.caption(
                "Recommendations are based on similar customers' "
                "purchase histories. Scores are ranking values, "
                "not purchase probabilities."
            )

            st.dataframe(
                recommendations,
                use_container_width=True,
                hide_index=True
            )

except FileNotFoundError:
    st.error(
        "Recommendation model files are missing. "
        "Please check your project's models folder."
    )



    
# ============================================================
# INVENTORY & STOCK RECOMMENDATIONS
# ============================================================

st.divider()
st.header("Inventory & Stock Recommendations")
st.caption(
    "Identify products that may need replenishment using "
    "current inventory and recent delivered sales."
)

@st.cache_data(ttl=300)
def get_inventory_recommendations():
    engine = get_engine()

    try:
        with engine.connect() as conn:
            products = pd.read_sql(
                text("""
                    SELECT
                        Product_ID,
                        Product_Name,
                        Category,
                        Selling_Price,
                        Stock_Quantity
                    FROM products
                """),
                conn
            )

            sales = pd.read_sql(
                text("""
                    SELECT Product_ID, Order_Date, Quantity
                    FROM sales
                    WHERE Order_Status = 'Delivered'
                """),
                conn
            )
    finally:
        engine.dispose()

    if sales.empty:
        products["Units_Sold_30_Days"] = 0
    else:
        sales["Order_Date"] = pd.to_datetime(
            sales["Order_Date"], errors="coerce"
        )
        sales["Quantity"] = pd.to_numeric(
            sales["Quantity"], errors="coerce"
        )

        reference_date = sales["Order_Date"].max()
        start_date = reference_date - pd.Timedelta(days=29)

        recent_sales = sales[
            sales["Order_Date"].between(start_date, reference_date)
        ]

        recent_demand = (
            recent_sales.groupby("Product_ID")["Quantity"]
            .sum()
            .reset_index(name="Units_Sold_30_Days")
        )

        products = products.merge(
            recent_demand,
            on="Product_ID",
            how="left"
        )

        products["Units_Sold_30_Days"] = (
            products["Units_Sold_30_Days"].fillna(0)
        )

    products["Average_Daily_Demand"] = (
        products["Units_Sold_30_Days"] / 30
    )

    demand = products["Average_Daily_Demand"]

    products["Days_of_Stock_Left"] = (
        products["Stock_Quantity"]
        / demand.replace(0, float("nan"))
    )

    # Initial 30-day inventory target
    products["Target_Stock_Quantity"] = (
        demand * 30
    ).apply(__import__("math").ceil)

    products["Suggested_Restock_Quantity"] = (
        products["Target_Stock_Quantity"]
        - products["Stock_Quantity"]
    ).clip(lower=0)

    def stock_action(row):
        if row["Units_Sold_30_Days"] == 0:
            return "Review Demand"
        elif row["Days_of_Stock_Left"] <= 7:
            return "High Priority"
        elif row["Days_of_Stock_Left"] <= 14:
            return "Medium Priority"
        elif row["Suggested_Restock_Quantity"] > 0:
            return "Consider Restocking"
        return "Stock Sufficient"

    products["Stock_Action"] = products.apply(
        stock_action, axis=1
    )

    return products, reference_date


try:
    inventory, inventory_reference_date = get_inventory_recommendations()

    # Summary metrics
    total_products = len(inventory)
    restock_count = int(
        (inventory["Suggested_Restock_Quantity"] > 0).sum()
    )
    review_count = int(
        (inventory["Stock_Action"] == "Review Demand").sum()
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Products Analyzed", f"{total_products:,}")
    col2.metric("Products to Restock", f"{restock_count:,}")
    col3.metric("Review Demand", f"{review_count:,}")

    st.caption(
        f"Demand reference date: {inventory_reference_date:%d %b %Y}"
    )

    st.subheader("Restock Recommendations")

    restock_table = inventory[
        inventory["Suggested_Restock_Quantity"] > 0
    ].sort_values(
        ["Days_of_Stock_Left", "Suggested_Restock_Quantity"],
        ascending=[True, False]
    )

    if restock_table.empty:
        st.info(
            "No products currently exceed the 30-day target "
            "stock level. This does not guarantee that stock "
            "will be sufficient for future demand."
        )
    else:
        display_columns = [
            "Product_ID",
            "Product_Name",
            "Category",
            "Stock_Quantity",
            "Units_Sold_30_Days",
            "Days_of_Stock_Left",
            "Suggested_Restock_Quantity",
            "Stock_Action"
        ]

        st.dataframe(
            restock_table[display_columns].round(2),
            use_container_width=True,
            hide_index=True
        )

        csv_data = restock_table[display_columns].to_csv(index=False)

        st.download_button(
            "Download Restock Recommendations",
            data=csv_data,
            file_name="retailiq_restock_recommendations.csv",
            mime="text/csv"
        )

    st.subheader("Products Requiring Demand Review")

    review_table = inventory[
        inventory["Stock_Action"] == "Review Demand"
    ][
        [
            "Product_ID",
            "Product_Name",
            "Category",
            "Stock_Quantity",
            "Selling_Price"
        ]
    ]

    if review_table.empty:
        st.success("All products have recent delivered sales.")
    else:
        st.dataframe(
            review_table,
            use_container_width=True,
            hide_index=True
        )

except Exception as e:
    st.error(f"Unable to load inventory recommendations: {e}")
