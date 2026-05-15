"""Main application entry point for AutoSplit."""
import logging
import uuid
from pathlib import Path

from flask import Flask, request, jsonify
from redis import Redis
from rq import Queue
from rq.job import Job
from werkzeug.utils import secure_filename

from config import Config
from image_parser import ImageParser
from alias_manager import AliasManager
from utr_tracker import UTRTracker
from splitwise_factory import create_splitwise_client, get_splitwise_mode

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Shared components (read-only, safe to share with the worker)
alias_manager = AliasManager(aliases_file=Config.ALIASES_FILE)
utr_tracker = UTRTracker(tracking_file=Config.UTR_TRACKING_FILE)
splitwise_client = create_splitwise_client(mcp_handler=None)

# Redis / job queue
redis_conn = Redis.from_url(Config.REDIS_URL)
q = Queue(connection=redis_conn)

logger.info(f"Using Splitwise mode: {get_splitwise_mode()}")


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'autosplit', 'version': '3.0.0'})


@app.route('/upload', methods=['POST'])
def upload():
    """Receive an invoice image from Termux and enqueue a processing job."""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400

    image_file = request.files['image']
    group_name = request.form.get('group', '')

    if not image_file.filename:
        return jsonify({'success': False, 'error': 'Empty filename'}), 400

    upload_dir = Path(Config.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}_{secure_filename(image_file.filename)}"
    image_path = str(upload_dir / filename)
    image_file.save(image_path)

    logger.info(f"Saved upload: {image_path} (group={group_name!r})")

    job = q.enqueue(
        'jobs.process_expense_job',
        image_path,
        group_name,
        job_timeout=120,
    )

    return jsonify({'success': True, 'job_id': job.id})


@app.route('/jobs/<job_id>', methods=['GET'])
def job_status(job_id):
    """Return the status and result of an RQ job."""
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        return jsonify({'success': False, 'error': 'Job not found'}), 404

    status = job.get_status()
    return jsonify({
        'id': job.id,
        'status': str(status),
        'result': job.result,
        'error': str(job.latest_result().exc_string) if status == 'failed' else None,
    })


@app.route('/groups', methods=['GET'])
def get_groups():
    """Return the list of Splitwise groups (for Termux group selection)."""
    try:
        groups = splitwise_client.get_groups()
        return jsonify({'success': True, 'groups': [g['name'] for g in groups]})
    except Exception as e:
        logger.error(f"Error fetching groups: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/aliases', methods=['GET'])
def get_aliases():
    try:
        return jsonify({'success': True, 'aliases': alias_manager.aliases})
    except Exception as e:
        logger.error(f"Error getting aliases: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/aliases', methods=['POST'])
def add_alias():
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
    try:
        return jsonify({'success': True, 'utrs': utr_tracker.get_all_utrs()})
    except Exception as e:
        logger.error(f"Error getting UTRs: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = Config.PORT
    logger.info(f"Starting AutoSplit service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
