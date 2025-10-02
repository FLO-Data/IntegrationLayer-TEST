import logging
import azure.functions as func
import pyodbc
import json
import os
import asyncio
import concurrent.futures
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

async def update_gitter_status(data: Dict[str, Any], conn_str: str) -> None:
    """Update gitter status using a separate thread."""
    station_id = data.get("station_id")
    status = data.get("status")
    status_timestamp = data.get("status_timestamp")
    shipping_id = data.get("shipping_id")
    current_workspace_id = data.get("current_workspace_id")
    
    # Use thread pool for database operations
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await asyncio.get_event_loop().run_in_executor(
            pool,
            execute_stored_procedure,
            conn_str,
            station_id,
            status,
            status_timestamp,
            shipping_id,
            current_workspace_id
        )

def execute_stored_procedure(conn_str: str, station_id: str, status: str, 
                            status_timestamp: str, shipping_id: str, current_workspace_id: str = None) -> None:
    """Execute the stored procedure in a separate thread."""
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute(
            """
            EXEC set_gitter_status 
                @station_id = ?,
                @status = ?,
                @status_timestamp = ?,
                @shipping_id = ?,
                @current_workspace_id = ?;
            """,
            (station_id, status, status_timestamp, shipping_id, current_workspace_id)
        )
        conn.commit()
        logging.info(f"Stored procedure executed successfully for station: {station_id}")

    except Exception as e:
        logging.error(f"Error executing stored procedure for station {station_id}: {e}")
        raise e

    finally:
        cursor.close()
        conn.close()

async def update_kovaci_linka_scan(data: Dict[str, Any], conn_str: str) -> None:
    """Update kovaci linka scan using a separate thread."""
    gitter_id = data.get("gitter_id")
    user = data.get("user")
    position = data.get("position")
    
    # Use thread pool for database operations
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await asyncio.get_event_loop().run_in_executor(
            pool,
            execute_kovaci_linka_procedure,
            conn_str,
            gitter_id,
            user,
            position
        )

def execute_kovaci_linka_procedure(conn_str: str, gitter_id: str, user: str, position: str) -> None:
    """Execute the stored procedure for kovaci linka scans in a separate thread."""
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute(
            """
            EXEC InsertKovaciLinkaScan 
                @gitter_id = ?,
                @user = ?,
                @position = ?;
            """,
            (gitter_id, user, position)
        )
        conn.commit()
        logging.info(f"Kovaci linka scan saved successfully for gitter: {gitter_id}")

    except Exception as e:
        logging.error(f"Error saving kovaci linka scan for gitter {gitter_id}: {e}")
        raise e

    finally:
        cursor.close()
        conn.close()

@bp.function_name(name="ChangeStatusHttpFunc")
@bp.route(route="ChangeStatus", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def http_function(req: func.HttpRequest) -> func.HttpResponse:
    """Process HTTP request to change gitter status."""
    conn_str = get_connection_string()
    
    try:
        # Parse the request body
        req_body = req.get_json()
        logging.info(f"Processing HTTP request: {req_body}")
        
        # Process request asynchronously
        await update_gitter_status(req_body, conn_str)
        
        return func.HttpResponse(
            body=json.dumps({"message": "Status updated successfully"}),
            mimetype="application/json",
            status_code=200
        )
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid request format. Expected JSON. Error: {e}")
        return func.HttpResponse(
            body=json.dumps({"error": "Invalid JSON format"}),
            mimetype="application/json",
            status_code=400
        )
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return func.HttpResponse(
            body=json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        ) 