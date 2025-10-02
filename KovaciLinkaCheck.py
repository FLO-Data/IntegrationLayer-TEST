import logging
import azure.functions as func
import pyodbc
import json
import os
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional

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

async def check_gitter_id_exists(gitter_id: str, conn_str: str) -> Optional[Dict[str, Any]]:
    """Check if gitter_id exists in kovaci_linka_scans table using a separate thread."""
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await asyncio.get_event_loop().run_in_executor(
            pool,
            execute_gitter_id_check,
            conn_str,
            gitter_id
        )

def execute_gitter_id_check(conn_str: str, gitter_id: str) -> Optional[Dict[str, Any]]:
    """Execute the query to check gitter_id existence in a separate thread."""
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Query to check if gitter_id exists
        cursor.execute(
            """
            SELECT TOP 1 
                gitter_id,
                employee_id,
                timestamp,
                position
            FROM [Traceability].[dbo].[kovaci_linka_scans] 
            WHERE gitter_id = ?
            ORDER BY timestamp DESC
            """,
            (gitter_id,)
        )
        
        row = cursor.fetchone()
        
        if row:
            # Gitter ID exists - return the data
            return {
                "exists": True,
                "gitter_id": row[0],
                "employee_id": row[1],
                "timestamp": row[2].isoformat() if row[2] else None,
                "position": row[3]
            }
        else:
            # Gitter ID doesn't exist - return None to trigger green blink
            return None

    except Exception as e:
        logging.error(f"Error checking gitter_id {gitter_id}: {e}")
        raise e

    finally:
        cursor.close()
        conn.close()

@bp.function_name(name="KovaciLinkaCheckHttpFunc")
@bp.route(route="KovaciLinkaCheck", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def http_function(req: func.HttpRequest) -> func.HttpResponse:
    """Check if gitter_id exists in kovaci_linka_scans table."""
    try:
        conn_str = get_connection_string()
        if not conn_str:
            logging.error("Database connection string is not configured")
            return func.HttpResponse(
                body=json.dumps({"error": "Database configuration error"}),
                mimetype="application/json",
                status_code=500
            )
        
        # Parse the request body
        try:
            req_body = req.get_json()
            logging.info(f"Processing kovaci linka check request: {req_body}")
        except ValueError as e:
            logging.error(f"Invalid JSON in request body: {e}")
            return func.HttpResponse(
                body=json.dumps({"error": "Invalid JSON format"}),
                mimetype="application/json",
                status_code=400
            )
        
        # Validate required fields
        if 'gitter_id' not in req_body:
            error_msg = "Missing required field: gitter_id"
            logging.error(error_msg)
            return func.HttpResponse(
                body=json.dumps({"error": error_msg}),
                mimetype="application/json",
                status_code=400
            )
        
        gitter_id = req_body.get("gitter_id")
        if not gitter_id or not gitter_id.strip():
            error_msg = "gitter_id cannot be empty"
            logging.error(error_msg)
            return func.HttpResponse(
                body=json.dumps({"error": error_msg}),
                mimetype="application/json",
                status_code=400
            )
        
        # Check gitter_id existence
        try:
            result = await check_gitter_id_exists(gitter_id.strip(), conn_str)
            
            if result is None:
                # Gitter ID doesn't exist - return empty response to trigger green blink
                return func.HttpResponse(
                    body=json.dumps({"exists": False, "message": "Gitter ID not found"}),
                    mimetype="application/json",
                    status_code=200
                )
            else:
                # Gitter ID exists - return the data
                return func.HttpResponse(
                    body=json.dumps(result),
                    mimetype="application/json",
                    status_code=200
                )
                
        except Exception as e:
            logging.error(f"Error checking gitter_id: {e}")
            return func.HttpResponse(
                body=json.dumps({"error": "Failed to check gitter_id"}),
                mimetype="application/json",
                status_code=500
            )
            
    except Exception as e:
        logging.error(f"Unexpected error in http_function: {e}")
        return func.HttpResponse(
            body=json.dumps({"error": "Internal server error"}),
            mimetype="application/json",
            status_code=500
        ) 