import yaml
import os
from typing import Dict, Any

class PromptLoader:
    def __init__(self, prompts_path: str = "backend/app/prompts/prompts.yaml"):
        # Resolve absolute path based on project root assumption
        # Assuming run from root of project
        self.prompts_path = os.path.abspath(prompts_path)
        self._prompts = {}
        self._load_prompts()

    def _load_prompts(self):
        try:
            with open(self.prompts_path, "r", encoding="utf-8") as f:
                self._prompts = yaml.safe_load(f)
            print(f"Loaded {len(self._prompts)} prompts from {self.prompts_path}")
        except Exception as e:
            print(f"CRITICAL: Failed to load prompts from {self.prompts_path}: {e}")
            self._prompts = {}
    
    def reload(self):
        """Hot-reload prompts from disk."""
        self._load_prompts()

    def get(self, key: str, **kwargs) -> str:
        """
        Retrieves a prompt by key and formats it with kwargs.
        """
        template = self._prompts.get(key)
        if not template:
            raise KeyError(f"Prompt key '{key}' not found in {self.prompts_path}")
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise KeyError(f"Missing argument for prompt '{key}': {e}")

# Singleton Instance
# Adjust path if necessary depending on where main.py runs from.
# Usually 'backend/app/prompts/prompts.yaml' is relative to root.
prompts = PromptLoader()
