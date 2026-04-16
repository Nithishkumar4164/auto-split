"""Image source abstraction for unified image ingestion from local files, Drive, and GCS."""
import logging
import os
import requests
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from config import Config

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}


def is_image_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in IMAGE_EXTENSIONS


class ResolvedImage:
    """Result of resolving an image source to a local file."""

    def __init__(self, local_path: str, group_name: Optional[str] = None):
        self.local_path = local_path
        self.group_name = group_name
        self._is_temp = False

    def mark_temporary(self):
        self._is_temp = True
        return self

    def cleanup(self):
        if self._is_temp and os.path.exists(self.local_path):
            os.unlink(self.local_path)
            logger.debug(f"Cleaned up temp file: {self.local_path}")


class ImageSource(ABC):
    """Abstract image source that resolves event data to a local image file."""

    @abstractmethod
    def can_handle(self, event_data: dict) -> bool:
        """Return True if this source can handle the given event data."""

    @abstractmethod
    def resolve(self, event_data: dict) -> Optional[ResolvedImage]:
        """Download/locate the image and return a ResolvedImage, or None on failure."""


class LocalFileSource(ImageSource):
    """Resolves a local file path to a ResolvedImage."""

    def can_handle(self, event_data: dict) -> bool:
        return 'image_path' in event_data

    def resolve(self, event_data: dict) -> Optional[ResolvedImage]:
        image_path = event_data['image_path']
        if not Path(image_path).exists():
            logger.error(f"File not found: {image_path}")
            return None
        group_name = event_data.get('group_name')
        return ResolvedImage(local_path=image_path, group_name=group_name)


class DriveSource(ImageSource):
    """Resolves a Google Drive event to a local image file."""

    def __init__(self, drive_handler):
        self.drive_handler = drive_handler

    def can_handle(self, event_data: dict) -> bool:
        return (
            'id' in event_data
            and 'name' in event_data
            and event_data.get('kind') != 'storage#object'
        )

    def resolve(self, event_data: dict) -> Optional[ResolvedImage]:
        processed = self.drive_handler.process_drive_event(event_data)
        if not processed:
            return None

        file_id = processed['file_id']
        file_name = processed['file_name']
        group_name = processed.get('group_name')

        temp_dir = Path('/tmp/autosplit')
        temp_dir.mkdir(exist_ok=True)
        local_path = str(temp_dir / file_name)

        if not self.drive_handler.download_file(file_id, local_path):
            logger.error(f"Failed to download Drive file: {file_id}")
            return None

        return ResolvedImage(local_path=local_path, group_name=group_name).mark_temporary()


class GCSSource(ImageSource):
    """Resolves a GCS storage event to a local image file."""

    def can_handle(self, event_data: dict) -> bool:
        return (
            event_data.get('kind') == 'storage#object'
            and bool(event_data.get('bucket'))
        )

    def resolve(self, event_data: dict) -> Optional[ResolvedImage]:
        bucket_name = event_data.get('bucket')
        file_name = event_data.get('name')
        media_link = event_data.get('mediaLink')

        if not bucket_name or not file_name:
            logger.warning("Missing bucket or name in GCS event")
            return None

        if not is_image_file(file_name):
            logger.info(f"Skipping non-image file: {file_name}")
            return None

        group_name = self._parse_gcs_path(file_name)

        temp_dir = Path('/tmp/autosplit')
        temp_dir.mkdir(exist_ok=True)
        local_path = str(temp_dir / Path(file_name).name)

        if not self._download(bucket_name, file_name, local_path, media_link):
            return None

        return ResolvedImage(local_path=local_path, group_name=group_name).mark_temporary()

    @staticmethod
    def _parse_gcs_path(file_path: str) -> Optional[str]:
        parts = Path(file_path).parts
        if len(parts) >= 2:
            return parts[0]
        return None

    @staticmethod
    def _download(bucket_name: str, blob_name: str, destination: str, media_link: Optional[str] = None) -> bool:
        try:
            from google.cloud import storage
            from google.oauth2 import service_account
            gcs_available = True
        except ImportError:
            gcs_available = False

        os.makedirs(os.path.dirname(destination), exist_ok=True)

        if gcs_available:
            try:
                credentials_path = Config.GOOGLE_APPLICATION_CREDENTIALS
                if credentials_path and os.path.exists(credentials_path):
                    credentials = service_account.Credentials.from_service_account_file(
                        credentials_path,
                        scopes=['https://www.googleapis.com/auth/cloud-platform']
                    )
                    storage_client = storage.Client(credentials=credentials, project=Config.GOOGLE_CLOUD_PROJECT)
                else:
                    storage_client = storage.Client(project=Config.GOOGLE_CLOUD_PROJECT)

                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.download_to_filename(destination)
                logger.info(f"Downloaded gs://{bucket_name}/{blob_name} to {destination}")
                return True
            except Exception as e:
                logger.error(f"GCS client download failed: {e}", exc_info=True)
                if not media_link:
                    return False

        if media_link:
            try:
                headers = {}
                if gcs_available:
                    try:
                        from google.oauth2 import service_account as sa
                        creds_path = Config.GOOGLE_APPLICATION_CREDENTIALS
                        if creds_path and os.path.exists(creds_path):
                            creds = sa.Credentials.from_service_account_file(
                                creds_path, scopes=['https://www.googleapis.com/auth/cloud-platform']
                            )
                            from google.auth.transport.requests import Request as AuthRequest
                            creds.refresh(AuthRequest())
                            headers = {'Authorization': f'Bearer {creds.token}'}
                    except Exception as e:
                        logger.warning(f"Could not refresh credentials for mediaLink auth: {e}")

                response = requests.get(media_link, headers=headers, timeout=30)
                response.raise_for_status()
                with open(destination, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded from mediaLink to {destination}")
                return True
            except Exception as e:
                logger.error(f"mediaLink download failed: {e}", exc_info=True)
                return False

        logger.error("No download method available for GCS")
        return False


class ImageSourceRouter:
    """Routes incoming event data to the appropriate ImageSource."""

    def __init__(self, sources: list[ImageSource]):
        self.sources = sources

    def resolve(self, event_data: dict) -> Optional[ResolvedImage]:
        for source in self.sources:
            if source.can_handle(event_data):
                logger.info(f"Routing to {source.__class__.__name__}")
                return source.resolve(event_data)
        logger.warning(f"No image source can handle event: {list(event_data.keys())}")
        return None
