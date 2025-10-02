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

async def process_kovaci_linka_scan(data: Dict[str, Any], conn_str: str) -> None:
    """Process kovaci linka scan using a separate thread."""
    gitter_id = data.get("gitter_id")
    employee_id = data.get("employee_id")
    position = data.get("position")
    
    if not all([gitter_id, employee_id, position]):
        raise ValueError("Missing required fields: gitter_id, employee_id, or position")
    
    if position not in ['A', 'B']:
        raise ValueError("Position must be either 'A' or 'B'")
    
    # Use thread pool for database operations
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await asyncio.get_event_loop().run_in_executor(
            pool,
            execute_kovaci_linka_procedure,
            conn_str,
            gitter_id,
            employee_id,
            position
        )

def execute_kovaci_linka_procedure(conn_str: str, gitter_id: str, employee_id: str, position: str) -> None:
    """Execute the stored procedure for kovaci linka scans in a separate thread."""
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute(
            """
            EXEC InsertKovaciLinkaScan 
                @gitter_id = ?,
                @employee_id = ?,
                @position = ?;
            """,
            (gitter_id, employee_id, position)
        )
        conn.commit()
        logging.info(f"Kovaci linka scan saved successfully for gitter: {gitter_id}")

    except Exception as e:
        logging.error(f"Error saving kovaci linka scan for gitter {gitter_id}: {e}")
        raise e

    finally:
        cursor.close()
        conn.close()

@bp.function_name(name="KovaciLinkaScanHttpFunc")
@bp.route(route="KovaciLinkaScan", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def http_function(req: func.HttpRequest) -> func.HttpResponse:
    """Process HTTP request for kovaci linka scan."""
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
            logging.info(f"Processing kovaci linka scan request: {req_body}")
        except ValueError as e:
            logging.error(f"Invalid JSON in request body: {e}")
            return func.HttpResponse(
                body=json.dumps({"error": "Invalid JSON format"}),
                mimetype="application/json",
                status_code=400
            )
        
        # Validate required fields
        required_fields = ['gitter_id', 'employee_id', 'position']
        missing_fields = [field for field in required_fields if field not in req_body]
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            logging.error(error_msg)
            return func.HttpResponse(
                body=json.dumps({"error": error_msg}),
                mimetype="application/json",
                status_code=400
            )
        
        # Process request asynchronously
        try:
            await process_kovaci_linka_scan(req_body, conn_str)
            return func.HttpResponse(
                body=json.dumps({"message": "Scan saved successfully"}),
                mimetype="application/json",
                status_code=200
            )
        except ValueError as e:
            logging.error(f"Validation error: {e}")
            return func.HttpResponse(
                body=json.dumps({"error": str(e)}),
                mimetype="application/json",
                status_code=400
            )
        except Exception as e:
            logging.error(f"Error processing scan: {e}")
            return func.HttpResponse(
                body=json.dumps({"error": "Failed to process scan"}),
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