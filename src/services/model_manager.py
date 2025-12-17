"""
Model selection management for admin
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Available OpenAI models for translation
AVAILABLE_MODELS = {
    "gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "description": "⚡ Fastest, most cost-effective",
        "icon": "⚡"
    },
    "gpt-4o": {
        "name": "GPT-4o",
        "description": "🚀 Most capable, slower",
        "icon": "🚀"
    }
}


class ModelManager:
    """Manages current translation model selection"""

    def __init__(self, config_path: str = "data/model_config.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._current_model = None
        self._load_config()

    def _load_config(self):
        """Load model configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self._current_model = data.get("current_model")
                    logger.info(f"Loaded model config: {self._current_model}")
            except Exception as e:
                logger.error(f"Failed to load model config: {e}")
                self._current_model = None

        # Set default if not loaded
        if not self._current_model:
            from ..core.config import get_config
            config = get_config()
            self._current_model = config.openai.model
            self._save_config()
            logger.info(f"Using default model from config: {self._current_model}")

    def _save_config(self):
        """Save model configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump({"current_model": self._current_model}, f, indent=2)
            logger.info(f"Saved model config: {self._current_model}")
        except Exception as e:
            logger.error(f"Failed to save model config: {e}")

    def get_current_model(self) -> str:
        """Get currently selected model"""
        return self._current_model

    def set_model(self, model: str) -> bool:
        """Set current model (must be in AVAILABLE_MODELS)"""
        if model not in AVAILABLE_MODELS:
            logger.error(f"Invalid model: {model}")
            return False

        self._current_model = model
        self._save_config()
        logger.info(f"Model changed to: {model}")
        return True

    def get_model_info(self, model: Optional[str] = None) -> Dict:
        """Get information about a model"""
        target_model = model or self._current_model
        return AVAILABLE_MODELS.get(target_model, {})

    def get_all_models(self) -> Dict:
        """Get all available models"""
        return AVAILABLE_MODELS


# Global model manager instance
_model_manager = None


def get_model_manager() -> ModelManager:
    """Get global model manager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
