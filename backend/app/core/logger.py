import logging
import sys
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        # Enforce UTC timestamps
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['level'] = record.levelname
        
        # Pull extra attributes if they exist
        log_record['run_id'] = getattr(record, 'run_id', None)
        log_record['agent'] = getattr(record, 'agent', None)
        log_record['event'] = getattr(record, 'event', None)

def setup_logging(environment: str = "production"):
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler(sys.stdout)
    
    if environment == "production":
        formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
        handler.setFormatter(formatter)
        root_logger.setLevel(logging.INFO)
    else:
        # Standard local readable format for development/tests
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s] %(message)s')
        handler.setFormatter(formatter)
        root_logger.setLevel(logging.DEBUG)
        
    root_logger.addHandler(handler)
    
    # Quiet down noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
