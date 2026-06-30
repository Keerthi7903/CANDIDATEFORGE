import os
import json
import logging
from jsonschema import validate, ValidationError

class Validator:
    def __init__(self, schema_path: str = None):
        if schema_path is None:
            schema_path = os.path.join("schemas", "output_schema.json")
        self.schema = {}
        try:
            if os.path.exists(schema_path):
                with open(schema_path, "r", encoding="utf-8") as f:
                    self.schema = json.load(f)
        except Exception as e:
            logging.error(f"Error loading JSON Schema: {e}")
            
    def validate(self, data: dict) -> None:
        """
        Validates data against the schema.
        Raises ValidationError if validation fails.
        """
        if not self.schema:
            logging.warning("No schema loaded. Skipping validation.")
            return
        validate(instance=data, schema=self.schema)
