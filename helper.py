import uuid
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import inspect

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LIB_DIR = Path(__file__).parent / "lib"
LIB_DIR.mkdir(exist_ok=True)
CHECKPOINT_FILE = LIB_DIR / "checkpoints.json"

def get_logger():
    # Identify the importing script's filename
    calling_file = inspect.stack()[1].filename
    log_name = Path(calling_file).stem
    log_file = LOG_DIR / f"{log_name}.log"

    logger = logging.getLogger(log_name)
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(uuid)s] %(message)s')

    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 5 MB
        backupCount=3
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Generate one UUID per run
    run_uuid = str(uuid.uuid4())

    # Add UUID to every log record
    class ContextFilter(logging.Filter):
        def filter(self, record):
            record.uuid = run_uuid
            return True

    logger.addFilter(ContextFilter())

    return logger

def _get_checkpoint_file():
    calling_file = inspect.stack()[2].filename
    file_stem = Path(calling_file).stem
    return LIB_DIR / f"{file_stem}_checkpoint.json"

def checkpoint_get(key, default=None):
    file_path = _get_checkpoint_file()
    if not file_path.exists():
        return default
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data.get(key, default)
    except Exception as e:
        return default

def checkpoint_save(key, value):
    file_path = _get_checkpoint_file()
    data = {}
    if file_path.exists():
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception:
            pass  # Skip loading if corrupt
    data[key] = value
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
