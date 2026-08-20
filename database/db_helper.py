"""Convenience query helpers (execute/fetch_one/fetch_all) built on top of DBConnection."""
from database.db_connection import DBConnection
from utils.logger import get_logger

logger = get_logger(__name__)


class DBHelper:
    def __init__(self, connection: DBConnection = None):
        self.db = connection or DBConnection()

    def execute(self, query: str, params: tuple = ()):
        conn = self.db.connect()
        cursor = conn.cursor()
        logger.info(f"Executing query: {query} | params={params}")
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        cursor = self.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
