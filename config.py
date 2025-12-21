"""Configuration module for AutoSplit application."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    # Google Cloud Configuration
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', '')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    
    # Google Drive Configuration
    DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', '')
    SPLITWISE_ROOT_FOLDER = os.getenv('SPLITWISE_ROOT_FOLDER', 'Splitwise')
    
    # Application Configuration
    PORT = int(os.getenv('PORT', 8090))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # File Paths
    UTR_TRACKING_FILE = os.getenv('UTR_TRACKING_FILE', 'processed_utrs.json')
    ALIASES_FILE = os.getenv('ALIAS_FILE_PATH', './aliases.json')
    
    # OCR Configuration
    TESSERACT_CMD = os.getenv('TESSERACT_CMD', '/usr/bin/tesseract')
    
    # Supported image formats
    SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png']
    
    # Splitwise Configuration
    SPLITWISE_MODE = os.getenv('SPLITWISE_MODE', 'api')  # 'api' or 'mcp'
    SPLITWISE_CONSUMER_KEY = os.getenv('SPLITWISE_CONSUMER_KEY', '')
    SPLITWISE_CONSUMER_SECRET = os.getenv('SPLITWISE_CONSUMER_SECRET', '')
    SPLITWISE_API_KEY = os.getenv('SPLITWISE_API_KEY', '')

