import logging
from . import RawRecord

class RecruiterNotesIngester:
    def ingest(self, filepath: str) -> RawRecord:
        errors = []
        raw_fields = {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            raw_fields = {"text": content}
        except Exception as e:
            err_msg = f"Failed to ingest recruiter notes: {str(e)}"
            logging.error(err_msg)
            errors.append(err_msg)
        return RawRecord(source_name="recruiter_notes", raw_fields=raw_fields, errors=errors)
