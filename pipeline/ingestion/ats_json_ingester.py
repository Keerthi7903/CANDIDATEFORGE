import json
import logging
from . import RawRecord

class ATSJsonIngester:
    def ingest(self, filepath: str) -> RawRecord:
        errors = []
        raw_fields = {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_fields = json.load(f)
        except Exception as e:
            err_msg = f"Failed to ingest ATS JSON: {str(e)}"
            logging.error(err_msg)
            errors.append(err_msg)
        return RawRecord(source_name="ats_json", raw_fields=raw_fields, errors=errors)
