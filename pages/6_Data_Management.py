
import streamlit as st
import pandas as pd
from sqlalchemy import text
from database.db_connection import get_engine

st.set_page_config(
    page_title="RetailIQ | Data Management",
    page_icon="🗄️",
    layout="wide"
)

NAVY = "#142B4A"
TEAL = "#0D9488"
GREEN = "#16A34A"
AMBER = "#D97706"

st.title("🗄️ Data Management")
st.caption("Inspect database tables and check data quality.")

TABLES = ["customers", "products", "sales"]


@st.cache_data(ttl=300)
def load_table_overview():
    engine = get_engine()

    try:
        with engine.connect() as conn:
            results = []

            for table in TABLES:
                count = conn.execute(
                    text(f"SELECT COUNT(*) FROM `{table}`")
                ).scalar_one()

                results.append({
                    "Table": table,
                    "Records": count
                })

            return pd.DataFrame(results)

    finally:
        engine.dispose()


@st.cache_data(ttl=300)
def load_preview(table, limit):
    if table not in TABLES:
        raise ValueError("Invalid table selected.")

    engine = get_engine()

    try:
        with engine.connect() as conn:
            return pd.read_sql(
                text(f"SELECT * FROM `{table}` LIMIT :row_limit"),
                conn,
                params={"row_limit": limit}
            )
    finally:
        engine.dispose()


@st.cache_data(ttl=300)
def load_quality_report():
    engine = get_engine()

    try:
        with engine.connect() as conn:
            reports = []

            for table in TABLES:
                result = pd.read_sql(
                    text("""
                        SELECT
                            COUNT(*) AS Total_Rows
                        FROM `{table_name}`
                    """.replace("{table_name}", table)),
                    conn
                )

                reports.append({
                    "Table": table,
                    "Total Rows": int(result.loc[0, "Total_Rows"])
                })

            return pd.DataFrame(reports)

    finally:
        engine.dispose()


try:
    overview = load_table_overview()

    # Database overview
    st.subheader("Database Overview")

    col1, col2, col3 = st.columns(3)

    for col, table in zip(
        [col1, col2, col3],
        ["customers", "products", "sales"]
    ):
        count = int(
            overview.loc[overview["Table"] == table, "Records"].iloc[0]
        )
        col.metric(f"{table.title()} Records", f"{count:,}")

    st.divider()

    st.subheader("Table Record Counts")
    st.dataframe(
        overview,
        use_container_width=True,
        hide_index=True
    )

    # Preview data
    st.divider()
    st.subheader("Explore Database Records")

    selected_table = st.selectbox(
        "Select a table",
        TABLES
    )

    preview_limit = st.selectbox(
        "Number of rows to preview",
        [10, 25, 50, 100],
        index=1
    )

    preview = load_preview(selected_table, preview_limit)

    st.dataframe(
        preview,
        use_container_width=True,
        hide_index=True
    )

    # Download current table data
    csv_data = preview.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Preview as CSV",
        data=csv_data,
        file_name=f"{selected_table}_preview.csv",
        mime="text/csv"
    )

    # Basic database quality checks
    st.divider()
    st.subheader("Data Quality Overview")

    quality = load_quality_report()
    st.dataframe(
        quality,
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "This version is read-only. It previews records and reports "
        "row counts without modifying the database."
    )

except Exception as e:
    st.error(f"Could not load database information: {e}")
    st.info(
        "Check your MySQL connection and confirm that all three "
        "tables exist."
    )
