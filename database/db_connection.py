
import os
from sqlalchemy import URL, create_engine

def get_engine():
    password = os.getenv("MysqlDB_PASSWORD")

    if not password:
        raise ValueError(
            "MYSQL_PASSWORD environment variable is not set."
        )

    connection_url = URL.create(
        "mysql+mysqlconnector",
        username="root",
        password=password,
        host="localhost",
        port=3306,
        database="retailiq",
    )

    return create_engine(
        connection_url,
        pool_pre_ping=True,
    )
