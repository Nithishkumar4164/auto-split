"""RQ job definitions for AutoSplit."""
from pathlib import Path

from config import Config
from image_parser import ImageParser
from alias_manager import AliasManager
from utr_tracker import UTRTracker
from splitwise_factory import create_splitwise_client
from expense_processor import ExpenseProcessor


def process_expense_job(image_path: str, group_name: str) -> dict:
    """Process an uploaded invoice image and create a Splitwise expense."""
    parser = ImageParser(tesseract_cmd=Config.TESSERACT_CMD)
    aliases = AliasManager(aliases_file=Config.ALIASES_FILE)
    tracker = UTRTracker(tracking_file=Config.UTR_TRACKING_FILE)
    client = create_splitwise_client()
    processor = ExpenseProcessor(parser, aliases, tracker, client)
    try:
        return processor.process(image_path, group_name)
    finally:
        Path(image_path).unlink(missing_ok=True)
