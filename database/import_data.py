
from pathlib import Path
import pandas as pd
import os
from sqlalchemy import create_engine, URL

# 1. Locate the processed CSV files
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data_processed"

# 2. Enter your MySQL connection details
DB_USER = "root"
DB_PASSWORD = os.getenv("MysqlDB_PASSWORD")
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "retailiq"

# 3. Create the database connection
connection_url = URL.create(
    "mysql+mysqlconnector",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)

engine = create_engine(connection_url)

# 4. Import each CSV into its own table
files = {
    "customers_processed.csv": "customers",
    "products_processed.csv": "products",
    "sales_processed.csv": "sales",
}

for filename, table_name in files.items():
    file_path = DATA_DIR / filename

    df = pd.read_csv(file_path)

    df.to_sql(
        name=table_name,
        con=engine,
        if_exists="replace",
        index=False,
        chunksize=5000,
    )

    print(f"Imported {len(df):,} rows into {table_name}")

engine.dispose()
print("Data import completed!")
