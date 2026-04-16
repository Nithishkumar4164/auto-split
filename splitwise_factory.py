"""Factory for creating Splitwise clients based on configuration."""
import logging
from config import Config
from splitwise_base import SplitwiseBase

logger = logging.getLogger(__name__)


def create_splitwise_client(mcp_handler=None) -> SplitwiseBase:
    """Create the appropriate Splitwise client based on SPLITWISE_MODE config."""
    mode = Config.SPLITWISE_MODE.lower()

    if mode == 'api':
        from splitwise_api_client import SplitwiseAPIClient

        if not Config.SPLITWISE_CONSUMER_KEY:
            raise ValueError("SPLITWISE_CONSUMER_KEY is required for API mode")
        if not Config.SPLITWISE_CONSUMER_SECRET:
            raise ValueError("SPLITWISE_CONSUMER_SECRET is required for API mode")
        if not Config.SPLITWISE_API_KEY:
            raise ValueError("SPLITWISE_API_KEY is required for API mode")

        logger.info("Creating Splitwise API client")
        return SplitwiseAPIClient(
            consumer_key=Config.SPLITWISE_CONSUMER_KEY,
            consumer_secret=Config.SPLITWISE_CONSUMER_SECRET,
            api_key=Config.SPLITWISE_API_KEY,
        )

    elif mode == 'mcp':
        from splitwise_mcp_client import SplitwiseMCPClient

        logger.info("Creating Splitwise MCP client")
        return SplitwiseMCPClient(mcp_handler=mcp_handler)

    else:
        raise ValueError(f"Invalid SPLITWISE_MODE: {mode}. Must be 'api' or 'mcp'")


def get_splitwise_mode() -> str:
    return Config.SPLITWISE_MODE.lower()
