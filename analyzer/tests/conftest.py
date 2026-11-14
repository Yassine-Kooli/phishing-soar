"""Point the analyzer at temporary state before app.py is imported (it reads env at import)."""
import os
import sys
import tempfile

ANALYZER = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ANALYZER)

_tmp = tempfile.mkdtemp(prefix="analyzer-test-")
os.environ.setdefault("STATE_DIR", os.path.join(_tmp, "state"))
os.environ.setdefault("DATA_DIR", os.path.join(_tmp, "data"))
os.environ.setdefault("QUARANTINE_DIR", os.path.join(_tmp, "quarantine"))
os.environ.setdefault("RULES_DIR", os.path.join(ANALYZER, "yara-rules"))
os.environ.setdefault("IOC_FILE", os.path.join(ANALYZER, "ioc", "domains.txt"))
os.environ.setdefault("BASE_HOSTS", os.path.join(_tmp, "no-base.hosts"))  # absent: no base entries
