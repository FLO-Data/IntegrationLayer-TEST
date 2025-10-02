import os
import json
import logging
import pyodbc
import azure.functions as func
import asyncio
import concurrent.futures
from typing import Dict, Tuple, Any, Optional

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

def fetch_part_status(conn_str: str, part_id: str) -> Optional[Dict[str, Any]]:
    """Get the status data for the given part."""
    with pyodbc.connect(conn_str) as conn:
        with conn.cursor() as cursor:
            # Get the current status from part_status table
            status_query = """
                SELECT last_status, station_id, status_timestamp, create_timestamp, employee_id,shipping_id
                FROM dbo.part_status 
                WHERE part_id = ?
            """
            cursor.execute(status_query, part_id)
            status_row = cursor.fetchone()
            
            if not status_row:
                return None
            
            # Convert station_id to string to match frontend expectations
            station_id = str(status_row[1]) if status_row[1] is not None else None
            
            result = {
                'part_id': part_id,
                'latest_status': status_row[0],      # last_status
                'latest_workspace_id': station_id,    # station_id as string
                'status_timestamp': status_row[2],    # status_timestamp
                'create_timestamp': status_row[3],    # create_timestamp
                'employee_id': status_row[4],          # employee_id
                'shipping_id': status_row[5]          # shipping_id
            }
            
            return result

def process_request(part_id: str, conn_str: str) -> Tuple[Dict[str, Any], int]:
    """Process the request with concurrent database operations using thread pool."""
    try:
        # Run constraint and status operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            part_status_future = executor.submit(fetch_part_status, conn_str, part_id)
            
            # Get status data result
            part_status = part_status_future.result()
            
            # Create response data structure
            response_data = {}
            if part_status:
                response_data = part_status  # Return the entire part_status directly
            else:
                response_data = {"message": "No record found for part ID: " + part_id}
                
            return response_data, 200
    except Exception as e:
        logging.error(f"Error in process_request: {e}")
        return {"error": str(e)}, 500

@bp.function_name(name="ReadStatus")
@bp.route(route="readstatus", methods=["GET"])
def read_status(req: func.HttpRequest) -> func.HttpResponse:
    part_id = req.params.get('part_id')
    
    if not part_id:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            part_id = req_body.get('part_id')
            
    if not part_id:
        return func.HttpResponse(
            "Please pass part_id in the query string or request body",
            status_code=400
        )

    conn_str = get_connection_string()
    
    try:
        # Process request with concurrent database operations
        response_data, status_code = process_request(part_id, conn_str)
        
        if status_code != 200:
            return func.HttpResponse(
                json.dumps(response_data),
                status_code=status_code,
                mimetype="application/json"
            )
            
        response = json.dumps(response_data, default=str)
        
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

    return func.HttpResponse(
        response,
        status_code=200,
        mimetype="application/json"
    )