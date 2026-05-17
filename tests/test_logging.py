import logging

from app.utils.logging import setup_logging


def test_setup_logging_suppresses_http_client_info_logs():
    setup_logging("INFO")

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
