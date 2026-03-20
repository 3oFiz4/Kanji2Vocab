
from callflow_tracer.plugin_system import get_plugin_manager
import json

manager = get_plugin_manager()
analyzers = manager.list_analyzers()
print(json.dumps(analyzers))
