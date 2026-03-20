
from callflow_tracer.auto_instrumentation import enable_auto_instrumentation

# Enable auto-instrumentation for selected libraries
enable_auto_instrumentation(["http","redis","boto3"])

print("Auto-instrumentation enabled for: http, redis, boto3")
