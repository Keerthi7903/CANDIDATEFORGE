import os
import yaml
import logging

class SkillNormalizer:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join("config", "skill_aliases.yaml")
        self.aliases = {}
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    self.aliases = yaml.safe_load(f) or {}
            self.aliases = {k.lower(): v.lower() for k, v in self.aliases.items()}
        except Exception as e:
            logging.error(f"Error loading skill aliases in normalizer: {e}")
            
    def normalize(self, skill_name: str) -> tuple[str, bool]:
        if not skill_name:
            return "", False
            
        cleaned = skill_name.strip().lower()
        if cleaned in self.aliases:
            return self.aliases[cleaned], True
            
        if cleaned in self.aliases.values():
            return cleaned, True
            
        for alias, canonical in self.aliases.items():
            if cleaned == canonical:
                return canonical, True
            if cleaned.replace(" ", "-") == canonical or cleaned.replace("-", " ") == canonical:
                return canonical, True
                
        return cleaned, False
