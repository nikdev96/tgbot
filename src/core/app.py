"""
Core application components: Bot, Dispatcher, OpenAI client
"""
import logging
import os
import re
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables (needed for critical secrets)
load_dotenv()

# Load configuration first
from .config import load_config
config = load_config()

# Configure logging with config
logging.basicConfig(
    level=getattr(logging, config.logging.level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Create audit logger for admin actions
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Get required environment variables (secrets not in config files)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def validate_env_vars():
    """Validate required environment variables"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_BOT_TOKEN.strip():
        raise ValueError("TELEGRAM_BOT_TOKEN must be set and not empty")

    # Telegram bot token format: <bot_id>:<bot_token>
    # Example: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
    if not re.match(r'^\d+:[A-Za-z0-9_-]+$', TELEGRAM_BOT_TOKEN):
        raise ValueError(
            "TELEGRAM_BOT_TOKEN format is invalid. "
            "Expected format: <bot_id>:<bot_token> (e.g., 123456789:ABCdefGHI...)"
        )

    if not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
        raise ValueError("OPENAI_API_KEY must be set and not empty")

    # OpenAI API keys should start with 'sk-'
    if not OPENAI_API_KEY.startswith('sk-'):
        logger.warning(
            "OPENAI_API_KEY does not start with 'sk-'. "
            "This may indicate an invalid API key format."
        )

# Validate environment variables on startup
validate_env_vars()
logger.info("Environment variables validated successfully")

# Initialize FSM storage
storage = MemoryStorage()

# Initialize global objects using config values
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=storage)
openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    timeout=config.openai.timeout_seconds,
    max_retries=config.openai.max_retries
)

# Initialize database manager
from ..storage.database import DatabaseManager
db = DatabaseManager(config.database.path)