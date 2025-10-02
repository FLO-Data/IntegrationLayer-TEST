import os
import json
import logging
import pyodbc
import azure.functions as func
import asyncio
import concurrent.futures
from typing import Dict, Tuple, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)

bp = func.Blueprint()
@bp.function_name(name="GetInfoStatus")
@bp.route(route="InfoStatus", methods=["GET"])
def InfoStatus(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("InfoStatus function processing a request")
    part_id = req.params.get('part_id')
    
    if not part_id:
        try:
            req_body = req.get_json()
            logging.info(f"Attempting to get part_id from request body: {req_body}")
        except ValueError:
            logging.warning("No JSON body in request")
            pass
        else:
            part_id = req_body.get('part_id')
            
    if not part_id:
        logging.error("No part_id provided in request")
        return func.HttpResponse(
            "Please pass part_id in the query string or request body",
            status_code=400
        )

    logging.info(f"Processing request for part_id: {part_id}")
    
    # Get the connection string from environment variables
    try:
        conn_str = get_connection_string()
        logging.info("Successfully built connection string")
    except Exception as e:
        logging.error(f"Error building connection string: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Database configuration error"}),
            status_code=500,
            mimetype="application/json"
        )
    
    try:
        # Process request with concurrent database operations
        logging.info("Starting database query")
        response_data, status_code = process_request(part_id, conn_str)
        logging.info(f"Query completed with status code: {status_code}")
        
        if status_code != 200:
            return func.HttpResponse(
                json.dumps(response_data),
                status_code=status_code,
                mimetype="application/json"
            )
            
        response = json.dumps(response_data, default=str)
        logging.info("Successfully processed request")
        
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

def fetch_part_info(conn_str: str, part_id: str) -> Optional[Dict[str, Any]]:
    """Get the detailed status information for the given part from transaction_log."""
    with pyodbc.connect(conn_str) as conn:
        with conn.cursor() as cursor:
            # Query from transaction_log table with history
            info_query = """
                SELECT 
                    coalesce(tl.part_id, hps.part_id) as 'Part_ID',
                    cst.station_name as 'Station',
                    coalesce(tl.status, hps.status) as 'Rezim_Cteni',
                    coalesce(tl.status_timestamp, hps.status_timestamp) as 'Timestamp',
                    coalesce(tl.employee_id, hps.employee_id) as 'Employee',
                    coalesce(tl.shipping_id, hps.shipping_id) as 'Gitterbox_ID',
                    hps.status as 'History_Status',
                    case when hps.status is not null then 'zmena statusu' else null end as zmena
                FROM dbo.traceability_log tl
                FULL OUTER JOIN dbo.h_part_status hps 
                    ON tl.part_id = hps.part_id 
                    AND tl.status_timestamp = hps.status_timestamp
                LEFT JOIN dbo.c_station cst 
                    ON cst.station_id = coalesce(tl.station_id, hps.station_id)
                WHERE coalesce(tl.part_id, hps.part_id) = ?
                ORDER BY coalesce(tl.status_timestamp, hps.status_timestamp) DESC
            """
            cursor.execute(info_query, (part_id,))
            rows = cursor.fetchall()
            
            if not rows:
                return None
            
            # Convert the results to a list of dictionaries
            result = []
            for row in rows:
                result.append({
                    'part_id': row[0],
                    'station_id': row[1],
                    'rezim_cteni': row[2],
                    'timestamp': row[3],
                    'employee_id': row[4],
                    'gitterbox_id': row[5],
                    'history_status': row[6],
                    'zmena': row[7]
                })
            
            return {'part_history': result}

def process_request(part_id: str, conn_str: str) -> Tuple[Dict[str, Any], int]:
    """Process the request with concurrent database operations using thread pool."""
    try:
        # Run info operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            part_info_future = executor.submit(fetch_part_info, conn_str, part_id)
            
            # Get info data result
            part_info = part_info_future.result()
            
            # Create response data structure
            response_data = {}
            if part_info:
                response_data = part_info
            else:
                response_data = {"message": "No record found for part ID: " + part_id}
                
            return response_data, 200
    except Exception as e:
        logging.error(f"Error in process_request: {e}")
        return {"error": str(e)}, 500