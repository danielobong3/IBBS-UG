import logging
import sys
import uuid
from pythonjsonlogger import jsonlogger
from contextvars import ContextVar

# trace id contextvar
TRACE_ID_CTX: ContextVar[str] = ContextVar("trace_id", default=None)


class TraceIdFilter(logging.Filter):
    def filter(self, record):
        trace_id = TRACE_ID_CTX.get(None)
        record.trace_id = trace_id
        return True


def setup_logging(level: int = logging.INFO):
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    fmt = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s')
    handler.setFormatter(fmt)
    handler.addFilter(TraceIdFilter())
    root.setLevel(level)
    root.handlers = []
    root.addHandler(handler)
