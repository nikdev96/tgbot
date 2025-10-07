"""
Core application components: Bot, Dispatcher, OpenAI client
"""
import logging
import os
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

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set as environment variables")

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