import azure.functions as func
import logging

app = func.FunctionApp()

@app.route(route="test", methods=["GET"])
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Test function processed a request.')

    return func.HttpResponse(
        "Hello from IntegrationLayer-TEST! This is a test function.",
        status_code=200
    )
