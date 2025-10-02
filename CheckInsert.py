import logging
import azure.functions as func
import pyodbc
import json
import os
import asyncio
import concurrent.futures
from azure.storage.queue import QueueClient
from typing import Dict, Any


# Create a Blueprint for registering with the Functions host
bp = func.Blueprint()

def get_connection_string() -> str:
    """Get the database connection string from environment variables."""
    sql_conn_str = os.getenv("AZURE_SQL_CONNECTION_STRING")
    sql_user = os.getenv("AZURE_SQL_DB_USER")
    sql_pwd = os.getenv("AZURE_SQL_DB_PASSWORD")
    sql_driver = os.getenv("AZURE_SQL_DRIVER")

    return (f"Driver={sql_driver};"
            f"Server={sql_conn_str};"
            "Database=Traceability_TEST;"
            f"Uid={sql_user};"
            f"Pwd={sql_pwd};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=60;")

async def insert_traceability_log(data: Dict[str, Any], conn_str: str) -> None:
    """Insert data into traceability_log table using a separate thread."""
    part_id = data.get("part_id")
    employee_id = data.get("employee_id")
    station_id = data.get("station_id")
    status = data.get("status")
    status_timestamp = data.get("status_timestamp")
    shipping_id = data.get("shipping_id")
    
    # Use thread pool for database operations
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await asyncio.get_event_loop().run_in_executor(
            pool,
            execute_stored_procedure,
            conn_str,
            part_id,
            employee_id,
            station_id,
            status,
            status_timestamp,
            shipping_id
        )

def execute_stored_procedure(conn_str: str, part_id: str, employee_id: str, station_id: str, 
                            status: str, status_timestamp: str, shipping_id: str = None) -> None:
    """Execute the stored procedure in a separate thread."""
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute(
            """
            EXEC InsertTraceabilityLog 
                @part_id = ?,
                @employee_id = ?,
                @station_id = ?,
                @status = ?,
                @status_timestamp = ?,
                @shipping_id = ?;
            """,
            (part_id, employee_id, station_id, status, status_timestamp, shipping_id)
        )
        conn.commit()
        logging.info(f"Stored procedure executed successfully for code: {part_id}")

    except Exception as e:
        logging.error(f"Error executing stored procedure for code {part_id}: {e}")
        raise e

    finally:
        cursor.close()
        conn.close()

@bp.function_name(name="QueueFunc")
@bp.queue_trigger(
    arg_name="msg",
    queue_name="operations-log-insert",
    connection="AzureWebJobsStorage"
)
async def queue_function(msg: func.QueueMessage) -> None:
    """Process queue message."""
    conn_str = get_connection_string()
    
    try:
        # Decode and parse the queue message
        message_body = msg.get_body().decode("utf-8")
        logging.info(f"Processing queue message: {message_body}")
        
        data = json.loads(message_body)
        
        # Process message asynchronously
        await insert_traceability_log(data, conn_str)
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid message format. Expected JSON. Error: {e}")
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        raise