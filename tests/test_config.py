"""
Tests for configuration system
"""
import os
import pytest
import tempfile
from pathlib import Path
from src.config import ConfigManager, Config, load_config


class TestConfigManager:
    """Test configuration loading and validation"""

    def test_default_config(self):
        """Test that default configuration loads correctly"""
        config_manager = ConfigManager()
        config = config_manager._create_config_from_dict({})

        # Verify defaults
        assert config.app.name == "Translation Bot"
        assert config.app.version == "2.1.0"
        assert config.audio.max_duration_seconds == 600
        assert config.tts.max_characters == 500
        assert config.tts.voice == "alloy"
        assert config.translation.max_retries == 3

    def test_config_from_yaml(self):
        """Test loading configuration from YAML file"""
        # Create temporary config file
        config_data = """
app:
  name: "Test Bot"
  version: "1.0.0"

audio:
  max_duration_seconds: 300

tts:
  max_characters: 200
  voice: "nova"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp.write(config_data)
            tmp_path = tmp.name

        try:
            config_manager = ConfigManager(tmp_path)
            config = config_manager.load_config()

            assert config.app.name == "Test Bot"
            assert config.app.version == "1.0.0"
            assert config.audio.max_duration_seconds == 300
            assert config.tts.max_characters == 200
            assert config.tts.voice == "nova"
            # Defaults should still apply
            assert config.translation.max_retries == 3

        finally:
            Path(tmp_path).unlink()

    def test_environment_variable_override(self):
        """Test that environment variables override config values"""
        # Set environment variables
        original_env = {}
        test_vars = {
            "OPENAI_MODEL": "gpt-3.5-turbo",
            "OPENAI_TTS_VOICE": "echo",
            "LOG_LEVEL": "DEBUG",
            "RATE_LIMIT_ENABLED": "false"
        }

        for key, value in test_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            config_manager = ConfigManager()
            config = config_manager._create_config_from_dict({})
            config = config_manager._override_with_env_vars(config)

            assert config.openai.model == "gpt-3.5-turbo"
            assert config.tts.voice == "echo"
            assert config.logging.level == "DEBUG"
            assert config.rate_limits.enabled is False

        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    def test_config_validation(self):
        """Test configuration validation"""
        config_manager = ConfigManager()

        # Test valid config
        valid_config = Config()
        config_manager._validate_config(valid_config)  # Should not raise

        # Test invalid audio duration
        invalid_config = Config()
        invalid_config.audio.max_duration_seconds = 0
        with pytest.raises(ValueError, match="audio.max_duration_seconds must be positive"):
            config_manager._validate_config(invalid_config)

        # Test invalid TTS characters
        invalid_config = Config()
        invalid_config.tts.max_characters = 5000  # Exceeds OpenAI limit
        with pytest.raises(ValueError, match="tts.max_characters cannot exceed 4000"):
            config_manager._validate_config(invalid_config)

        # Test invalid TTS speed
        invalid_config = Config()
        invalid_config.tts.speed = 5.0  # Exceeds OpenAI limit
        with pytest.raises(ValueError, match="tts.speed must be between 0.25 and 4.0"):
            config_manager._validate_config(invalid_config)

        # Test invalid retry count
        invalid_config = Config()
        invalid_config.translation.max_retries = 15  # Too high
        with pytest.raises(ValueError, match="translation.max_retries cannot exceed 10"):
            config_manager._validate_config(invalid_config)

    def test_production_config_file(self):
        """Test that production config file loads correctly"""
        config = load_config('production')

        assert config.app.name == "Translation Bot"
        assert config.app.environment == "production"
        assert config.audio.max_duration_seconds == 600
        assert config.tts.max_characters == 500
        assert config.rate_limits.enabled is True
        assert config.database.path == "data/translator_bot.db"

    def test_development_config_file(self):
        """Test that development config file loads correctly"""
        config = load_config('development')

        assert config.app.name == "Translation Bot (Dev)"
        assert config.app.environment == "development"
        assert config.audio.max_duration_seconds == 300  # Shorter for dev
        assert config.tts.max_characters == 200  # Shorter for dev
        assert config.rate_limits.enabled is False  # Disabled for dev
        assert config.database.path == "data/translator_bot_dev.db"

    def test_config_property_access(self):
        """Test that config properties can be accessed correctly"""
        config = load_config('production')

        # Test nested property access
        assert config.app.name == "Translation Bot"
        assert config.audio.input_sample_rate == 16000
        assert config.audio.output_sample_rate == 48000
        assert config.tts.model == "tts-1"
        assert config.translation.retry_delay_base == 2
        assert config.openai.timeout_seconds == 30

    def test_config_immutability_protection(self):
        """Test that config loading is consistent"""
        config1 = load_config('production')
        config2 = load_config('production')

        # Should have same values
        assert config1.app.name == config2.app.name
        assert config1.audio.max_duration_seconds == config2.audio.max_duration_seconds
        assert config1.tts.max_characters == config2.tts.max_characters

    def test_missing_config_file(self):
        """Test behavior when config file doesn't exist"""
        config_manager = ConfigManager("nonexistent_config.yaml")
        config = config_manager.load_config()

        # Should use defaults when file doesn't exist
        assert config.app.name == "Translation Bot"
        assert config.audio.max_duration_seconds == 600