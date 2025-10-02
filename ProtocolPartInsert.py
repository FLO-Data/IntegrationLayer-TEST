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
    """Get the database connection string from environment variables and log the process."""
    logging.info("Attempting to get connection string for ProtocolPartInsert.")
    sql_server = os.getenv("AZURE_SQL_CONNECTION_STRING")
    sql_user = os.getenv("AZURE_SQL_DB_USER")
    sql_pwd = os.getenv("AZURE_SQL_DB_PASSWORD")
    sql_driver = os.getenv("AZURE_SQL_DRIVER", "{ODBC Driver 17 for SQL Server}")

    if not all([sql_server, sql_user, sql_pwd, sql_driver]):
        logging.error("DATABASE CONNECTION ERROR: One or more environment variables are not set for ProtocolPartInsert.")
        missing_vars = [var for var, value in {
            "AZURE_SQL_CONNECTION_STRING": sql_server,
            "AZURE_SQL_DB_USER": sql_user,
            "AZURE_SQL_DB_PASSWORD": "Set" if sql_pwd else None,
            "AZURE_SQL_DRIVER": sql_driver
        }.items() if not value]
        logging.error(f"Missing environment variables: {', '.join(missing_vars)}")
        raise ValueError("Database configuration is incomplete. Check Azure Function App settings.")

    logging.info(f"Successfully loaded DB config for ProtocolPartInsert. Server='{sql_server}', User='{sql_user}'")
    
    # Opravený connection string
    conn_str = (f"Driver={sql_driver};"
                f"Server={sql_server};"
                "Database=Traceability_TEST;"
                f"Uid={sql_user};"
                f"Pwd={sql_pwd};"
                "Encrypt=yes;"
                "TrustServerCertificate=no;"
                "Connection Timeout=30;")
    
    logging.info(f"Connection string created successfully (password hidden)")
    return conn_str

def execute_stored_procedure(conn_str: str, part_id: str, employee_id: str, station_id: str, 
                            status: str, status_timestamp: str, shipping_id: str = None, 
                            protocol_id: str = None) -> None:
    """Execute the stored procedure with detailed logging."""
    logging.info(f"Attempting to execute stored procedure 'insert_protocol_part' for part_id: {part_id}")
    try:
        with pyodbc.connect(conn_str, timeout=30) as conn:
            logging.info(f"DB connection successful for part_id: {part_id}.")
            cursor = conn.cursor()
            
            logging.info(f"Executing stored procedure with params: part_id={part_id}, protocol_id={protocol_id}, status={status}")
            cursor.execute(
                "{CALL insert_protocol_part (?, ?, ?, ?, ?, ?, ?)}",
                part_id,
                employee_id,
                station_id,
                status,
                status_timestamp,
                shipping_id,
                protocol_id
            )
            conn.commit()
            logging.info(f"Stored procedure executed and committed successfully for part_id: {part_id}")

    except pyodbc.Error as db_error:
        logging.error(f"DATABASE ERROR executing stored procedure for part_id {part_id}: {db_error}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred in execute_stored_procedure for part_id {part_id}: {e}", exc_info=True)
        raise

@bp.function_name(name="ProtocolPartInsertHttpFunc")
@bp.route(route="ProtocolPartInsert", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def http_function(req: func.HttpRequest) -> func.HttpResponse:
    """Process HTTP request to insert protocol part data with detailed logging."""
    logging.info("ProtocolPartInsert Azure function triggered.")
    
    try:
        # Zkontroluj, zda je request JSON
        if not req.headers.get('content-type', '').startswith('application/json'):
            logging.error("Invalid content-type. Expected application/json")
            return func.HttpResponse(
                body=json.dumps({"error": "Content-Type must be application/json"}),
                mimetype="application/json",
                status_code=400
            )
        
        req_body = req.get_json()
        logging.info(f"Received request body: {req_body}")
        
        part_id = req_body.get("part_id")
        protocol_id = req_body.get("protocol_id")
        if not part_id or not protocol_id:
            logging.error(f"Invalid request body. Missing part_id or protocol_id. Payload: {req_body}")
            return func.HttpResponse(
                body=json.dumps({"error": "Request body must contain 'part_id' and 'protocol_id'"}),
                mimetype="application/json",
                status_code=400
            )

        conn_str = get_connection_string()

        # Unpack data for the async call
        employee_id = req_body.get("employee_id")
        station_id = req_body.get("station_id")
        status = req_body.get("status")
        status_timestamp = req_body.get("status_timestamp")
        shipping_id = req_body.get("shipping_id")

        # Opravené async volání
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(
                pool,
                execute_stored_procedure,
                conn_str,
                part_id,
                employee_id,
                station_id,
                status,
                status_timestamp,
                shipping_id,
                protocol_id
            )
        
        logging.info(f"Successfully processed request for part_id: {part_id}, protocol_id: {protocol_id}")
        return func.HttpResponse(
            body=json.dumps({"message": "Protocol part data inserted successfully"}),
            mimetype="application/json",
            status_code=200
        )
        
    except ValueError as ve:
        # Catches JSON decoding errors or errors from get_connection_string
        logging.error(f"ValueError processing request: {ve}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": str(ve)}),
            mimetype="application/json",
            status_code=400
        )
    except pyodbc.Error as db_error:
        logging.error(f"Database error in ProtocolPartInsert: {db_error}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": "Database connection error. Check logs for details."}),
            mimetype="application/json",
            status_code=500
        )
    except Exception as e:
        logging.error(f"An unhandled exception occurred in ProtocolPartInsert: {e}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": "An internal server error occurred. Check logs for details."}),
            mimetype="application/json",
            status_code=500
        ) 