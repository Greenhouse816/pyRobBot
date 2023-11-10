"""Management of embeddings/chat history storage and retrieval."""
import datetime
import json
import sqlite3
from pathlib import Path

import pandas as pd


class EmbeddingsDatabase:
    """Class for managing an SQLite database storing embeddings and associated data."""

    def __init__(self, db_path: Path, embedding_model: str):
        """Initialise the EmbeddingsDatabase object.

        Args:
            db_path (Path): The path to the SQLite database file.
            embedding_model (str): The embedding model associated with this database.
        """
        self.db_path = db_path
        self.embedding_model = embedding_model
        self.create()

    def create(self):
        """Create the necessary tables and triggers in the SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)

        # SQL to create 'embedding_model' table with 'embedding_model' as primary key
        create_embedding_model_table = """
        CREATE TABLE IF NOT EXISTS embedding_model (
            created_timestamp INTEGER NOT NULL,
            embedding_model TEXT NOT NULL,
            PRIMARY KEY (embedding_model)
        )
        """

        # SQL to create 'messages' table
        create_messages_table = """
        CREATE TABLE IF NOT EXISTS messages (
            timestamp INTEGER NOT NULL,
            chat_model TEXT NOT NULL,
            message_exchange TEXT NOT NULL,
            embedding TEXT
        )
        """

        with conn:
            # Create tables
            conn.execute(create_embedding_model_table)
            conn.execute(create_messages_table)

            # Triggers to prevent modification after insertion
            conn.execute(
                """
            CREATE TRIGGER IF NOT EXISTS prevent_embedding_model_modification
            BEFORE UPDATE ON embedding_model
            BEGIN
                SELECT RAISE(FAIL, 'modification not allowed');
            END;
            """
            )

            conn.execute(
                """
            CREATE TRIGGER IF NOT EXISTS prevent_messages_modification
            BEFORE UPDATE ON messages
            BEGIN
                SELECT RAISE(FAIL, 'modification not allowed');
            END;
            """
            )

        # Close the connection to the database
        conn.close()

    def get_embedding_model(self):
        """Retrieve the database's embedding model.

        Returns:
            str: The embedding model or None if teh database is not yet initialised.
        """
        conn = sqlite3.connect(self.db_path)
        query = "SELECT embedding_model FROM embedding_model;"
        # Execute the query and fetch the result
        embedding_model = None
        with conn:
            cur = conn.cursor()
            cur.execute(query)
            result = cur.fetchone()
            embedding_model = result[0] if result else None

        conn.close()

        return embedding_model

    def insert_message_exchange(self, chat_model, message_exchange, embedding):
        """Insert a message exchange into the database's 'messages' table.

        Args:
            chat_model (str): The chat model.
            message_exchange: The message exchange.
            embedding: The embedding associated with the message exchange.

        Raises:
            ValueError: If the database already contains a different embedding model.
        """
        stored_embedding_model = self.get_embedding_model()
        if stored_embedding_model is None:
            self._init_database()
        elif stored_embedding_model != self.embedding_model:
            raise ValueError(
                "Database already contains a different embedding model: "
                f"{self.get_embedding_model()}.\n"
                "Cannot continue."
            )

        timestamp = int(datetime.datetime.utcnow().timestamp())
        message_exchange = json.dumps(message_exchange)
        embedding = json.dumps(embedding)
        conn = sqlite3.connect(self.db_path)
        sql = "INSERT INTO messages "
        sql += "(timestamp, chat_model, message_exchange, embedding) VALUES (?, ?, ?, ?);"
        with conn:
            conn.execute(sql, (timestamp, chat_model, message_exchange, embedding))
        conn.close()

    def get_messages_dataframe(self):
        """Retrieve msg exchanges from the `messages` table. Return them as a DataFrame.

        Returns:
            pd.DataFrame: A DataFrame containing the message exchanges.
        """
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM messages;"
        messages_df = pd.read_sql_query(query, conn)
        conn.close()
        return messages_df

    def _init_database(self):
        """Initialise the 'embedding_model' table in the database."""
        conn = sqlite3.connect(self.db_path)
        create_time = int(datetime.datetime.utcnow().timestamp())
        sql = "INSERT INTO embedding_model "
        sql += "(created_timestamp, embedding_model) VALUES (?, ?);"
        with conn:
            conn.execute(sql, (create_time, self.embedding_model))
        conn.close()
