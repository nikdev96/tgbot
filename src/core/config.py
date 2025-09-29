"""
Configuration management for Translation Bot
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration"""
    name: str = "Translation Bot"
    version: str = "2.1.0"
    environment: str = "production"


@dataclass
class AudioConfig:
    """Audio processing configuration"""
    max_duration_seconds: int = 600
    input_sample_rate: int = 16000
    output_sample_rate: int = 48000
    temp_cleanup_timeout: int = 30


@dataclass
class TTSConfig:
    """Text-to-Speech configuration"""
    max_characters: int = 500
    timeout_seconds: int = 30
    voice: str = "alloy"
    model: str = "tts-1"
    speed: float = 1.0


@dataclass
class TranslationConfig:
    """Translation configuration"""
    max_retries: int = 3
    retry_delay_base: int = 2
    display_truncate_length: int = 100
    timeout_seconds: int = 30
    max_input_characters: int = 2000
    max_tokens: int = 500


@dataclass
class RateLimitsConfig:
    """Rate limiting configuration"""
    enabled: bool = True
    messages_per_minute: int = 10
    voice_messages_per_hour: int = 20
    admin_bypass: bool = True


@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "data/translator_bot.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    connection_timeout: int = 30


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    audit_enabled: bool = True
    max_log_size_mb: int = 50
    backup_count: int = 5


@dataclass
class OpenAIConfig:
    """OpenAI API configuration"""
    timeout_seconds: int = 30
    max_retries: int = 3
    model: str = "gpt-4o"


@dataclass
class SecurityConfig:
    """Security configuration"""
    max_users: int = 1000
    session_cleanup_hours: int = 72
    admin_session_timeout: int = 60


@dataclass
class Config:
    """Main configuration class"""
    app: AppConfig = field(default_factory=AppConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    rate_limits: RateLimitsConfig = field(default_factory=RateLimitsConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)


class ConfigManager:
    """Configuration manager for loading and validating config files"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self._config: Optional[Config] = None

    def load_config(self, environment: str = None) -> Config:
        """Load configuration from file or environment variables"""

        # Determine config file path
        if self.config_path:
            config_file = Path(self.config_path)
        else:
            # Auto-detect based on environment
            env = environment or os.getenv("ENVIRONMENT", "production")
            config_file = Path(f"config/{env}.yaml")

        # Load from file if exists
        if config_file.exists():
            logger.info(f"Loading configuration from {config_file}")
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        else:
            logger.warning(f"Config file {config_file} not found, using defaults")
            config_data = {}

        # Create config object
        config = self._create_config_from_dict(config_data)

        # Override with environment variables
        config = self._override_with_env_vars(config)

        # Validate configuration
        self._validate_config(config)

        self._config = config
        return config

    def _create_config_from_dict(self, data: Dict[str, Any]) -> Config:
        """Create Config object from dictionary data"""
        return Config(
            app=AppConfig(**data.get('app', {})),
            audio=AudioConfig(**data.get('audio', {})),
            tts=TTSConfig(**data.get('tts', {})),
            translation=TranslationConfig(**data.get('translation', {})),
            rate_limits=RateLimitsConfig(**data.get('rate_limits', {})),
            database=DatabaseConfig(**data.get('database', {})),
            logging=LoggingConfig(**data.get('logging', {})),
            openai=OpenAIConfig(**data.get('openai', {})),
            security=SecurityConfig(**data.get('security', {}))
        )

    def _override_with_env_vars(self, config: Config) -> Config:
        """Override config values with environment variables"""

        # Database path
        if os.getenv("DATABASE_PATH"):
            config.database.path = os.getenv("DATABASE_PATH")

        # OpenAI settings
        if os.getenv("OPENAI_MODEL"):
            config.openai.model = os.getenv("OPENAI_MODEL")

        # TTS settings
        if os.getenv("OPENAI_TTS_MODEL"):
            config.tts.model = os.getenv("OPENAI_TTS_MODEL")
        if os.getenv("OPENAI_TTS_VOICE"):
            config.tts.voice = os.getenv("OPENAI_TTS_VOICE")

        # Logging level
        if os.getenv("LOG_LEVEL"):
            config.logging.level = os.getenv("LOG_LEVEL")

        # Rate limiting
        if os.getenv("RATE_LIMIT_ENABLED"):
            config.rate_limits.enabled = os.getenv("RATE_LIMIT_ENABLED").lower() == "true"

        return config

    def _validate_config(self, config: Config):
        """Validate configuration values"""

        # Audio limits
        if config.audio.max_duration_seconds <= 0:
            raise ValueError("audio.max_duration_seconds must be positive")
        if config.audio.max_duration_seconds > 3600:  # 1 hour
            raise ValueError("audio.max_duration_seconds cannot exceed 3600 seconds")

        # TTS limits
        if config.tts.max_characters <= 0:
            raise ValueError("tts.max_characters must be positive")
        if config.tts.max_characters > 4000:  # OpenAI limit
            raise ValueError("tts.max_characters cannot exceed 4000")

        # TTS speed
        if not (0.25 <= config.tts.speed <= 4.0):
            raise ValueError("tts.speed must be between 0.25 and 4.0")

        # Retry limits
        if config.translation.max_retries < 0:
            raise ValueError("translation.max_retries cannot be negative")
        if config.translation.max_retries > 10:
            raise ValueError("translation.max_retries cannot exceed 10")

        # Input text limits
        if config.translation.max_input_characters <= 0:
            raise ValueError("translation.max_input_characters must be positive")
        if config.translation.max_input_characters > 10000:
            raise ValueError("translation.max_input_characters cannot exceed 10000")

        # Token limits
        if config.translation.max_tokens <= 0:
            raise ValueError("translation.max_tokens must be positive")
        if config.translation.max_tokens > 4000:  # OpenAI model limit
            raise ValueError("translation.max_tokens cannot exceed 4000")

        # Rate limits
        if config.rate_limits.messages_per_minute <= 0:
            raise ValueError("rate_limits.messages_per_minute must be positive")

        # Database path
        database_dir = Path(config.database.path).parent
        if not database_dir.exists():
            database_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Configuration validation passed")

    def get_config(self) -> Config:
        """Get current configuration"""
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        return self._config

    @property
    def config(self) -> Config:
        """Property access to configuration"""
        return self.get_config()


# Global configuration manager instance
config_manager = ConfigManager()

def get_config() -> Config:
    """Get global configuration instance"""
    return config_manager.get_config()

def load_config(environment: str = None, config_path: str = None) -> Config:
    """Load global configuration"""
    if config_path:
        config_manager.config_path = config_path
    return config_manager.load_config(environment)