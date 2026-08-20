"""Generic DB connection manager. Defaults to SQLite; swap connect() for MySQL/Postgres drivers as needed."""
import sqlite3

from config.config_reader import ConfigReader
from utils.logger import get_logger

logger = get_logger(__name__)


class DBConnection:
    """Context-manager friendly wrapper around a DB-API 2.0 connection."""

    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or ConfigReader.get("db_connection_string", "test_data/test.db")
        self.connection = None

    def connect(self):
        if self.connection is None:
            logger.info(f"Connecting to database: {self.connection_string}")
            self.connection = sqlite3.connect(self.connection_string)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
