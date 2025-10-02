import azure.functions as func
# Import the blueprint (bp) from CheckInsert
from CheckInsert import bp as insert
from ReadStatus import bp as read_status_bp
from InfoStatus import bp as info_status_bp
from ChangeStatus import bp as change_status_bp
from KovaciLinkaScan import bp as kovaci_linka_bp
from KovaciLinkaCheck import bp as kovaci_linka_check_bp
from ProtocolPartInsert import bp as protocol_part_insert_bp

app = func.FunctionApp()
# Register your blueprint so Azure Functions sees it
app.register_functions(insert)
app.register_functions(read_status_bp)
app.register_functions(info_status_bp)
app.register_functions(change_status_bp)
app.register_functions(kovaci_linka_bp)
app.register_functions(kovaci_linka_check_bp)
app.register_functions(protocol_part_insert_bp)


