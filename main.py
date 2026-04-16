"""Main application entry point for AutoSplit."""
import logging
from flask import Flask, request, jsonify
from pathlib import Path

from config import Config
from image_parser import ImageParser
from alias_manager import AliasManager
from utr_tracker import UTRTracker
from splitwise_factory import create_splitwise_client, get_splitwise_mode
from drive_handler import DriveHandler
from expense_processor import ExpenseProcessor
from image_source import LocalFileSource, DriveSource, GCSSource, ImageSourceRouter

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize components
image_parser = ImageParser(tesseract_cmd=Config.TESSERACT_CMD)
alias_manager = AliasManager(aliases_file=Config.ALIASES_FILE)
utr_tracker = UTRTracker(tracking_file=Config.UTR_TRACKING_FILE)
splitwise_client = create_splitwise_client(mcp_handler=None)
drive_handler = DriveHandler(credentials_path=Config.GOOGLE_APPLICATION_CREDENTIALS)

# Build the image source router (order matters — first match wins)
image_source_router = ImageSourceRouter([
    GCSSource(),
    DriveSource(drive_handler),
    LocalFileSource(),
])

logger.info(f"Using Splitwise mode: {get_splitwise_mode()}")

# Initialize processor
processor = ExpenseProcessor(
    image_parser=image_parser,
    alias_manager=alias_manager,
    utr_tracker=utr_tracker,
    splitwise_client=splitwise_client,
    image_source_router=image_source_router,
)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'autosplit',
        'version': '2.0.0'
    })


@app.route('/process-drive-event', methods=['POST'])
def process_drive_event():
    """Process Google Drive or GCS upload event."""
    try:
        event_data = request.get_json(force=True, silent=True)

        if not event_data:
            logger.warning("No event data received")
            return jsonify({'success': False, 'error': 'No event data received'}), 400

        if event_data.get('kind') == 'storage#object':
            logger.info(f"Received GCS event: gs://{event_data.get('bucket')}/{event_data.get('name')}")
        else:
            logger.info(f"Received Drive event: {event_data.get('name')}")

        logger.debug(f"Full event data: {event_data}")

        result = processor.process_event(event_data)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Error in process_drive_event: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/process-image', methods=['POST'])
def process_image():
    """Manual endpoint to process a local image."""
    try:
        data = request.get_json()
        logger.info(f"Received request data: {data}")

        if not data or 'image_path' not in data:
            return jsonify({'success': False, 'error': 'image_path is required'}), 400

        image_path = data['image_path']
        group_name = data.get('group_name')

        if not Path(image_path).exists():
            return jsonify({'success': False, 'error': f'File not found: {image_path}'}), 400

        result = processor.process_image(image_path, group_name)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Error in process_image: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/aliases', methods=['GET'])
def get_aliases():
    """Get all aliases."""
    try:
        return jsonify({'success': True, 'aliases': alias_manager.aliases})
    except Exception as e:
        logger.error(f"Error getting aliases: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/aliases', methods=['POST'])
def add_alias():
    """Add a new alias."""
    try:
        data = request.get_json()
        if not data or 'canonical_name' not in data or 'alias' not in data:
            return jsonify({'success': False, 'error': 'canonical_name and alias are required'}), 400

        alias_manager.add_alias(data['canonical_name'], data['alias'])
        return jsonify({'success': True, 'message': 'Alias added successfully'})

    except Exception as e:
        logger.error(f"Error adding alias: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/utrs', methods=['GET'])
def get_utrs():
    """Get all processed UTRs."""
    try:
        return jsonify({'success': True, 'utrs': utr_tracker.get_all_utrs()})
    except Exception as e:
        logger.error(f"Error getting UTRs: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = Config.PORT
    logger.info(f"Starting AutoSplit service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
