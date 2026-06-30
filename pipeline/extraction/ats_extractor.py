import os
import yaml
import logging
from typing import Dict, Any
from pipeline.ingestion import RawRecord

class ATSExtractor:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join("config", "ats_field_map.yaml")
        self.field_map = {}
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    self.field_map = yaml.safe_load(f) or {}
            else:
                # Fallback mapping
                self.field_map = {
                    "applicant_name": "full_name",
                    "contact_email": "emails",
                    "contact_phone": "phones",
                    "job_title": "headline",
                    "work_history": "experience",
                    "tech_stack": "skills",
                    "education_info": "education"
                }
        except Exception as e:
            logging.error(f"Error loading ATS field map: {e}")
            
    def extract(self, raw_record: RawRecord) -> Dict[str, Any]:
        extracted = {}
        raw = raw_record.raw_fields
        if not raw:
            return extracted
            
        try:
            # Map simple fields
            # Name
            name_key = self._find_key("full_name")
            if name_key and name_key in raw:
                extracted["full_name"] = raw[name_key]
                
            # Emails
            email_key = self._find_key("emails")
            if email_key and email_key in raw:
                val = raw[email_key]
                extracted["emails"] = [val] if isinstance(val, str) else list(val)
                
            # Phones
            phone_key = self._find_key("phones")
            if phone_key and phone_key in raw:
                val = raw[phone_key]
                extracted["phones"] = [val] if isinstance(val, str) else list(val)
                
            # Headline
            headline_key = self._find_key("headline")
            if headline_key and headline_key in raw:
                extracted["headline"] = raw[headline_key]
                
            # Skills
            skills_key = self._find_key("skills")
            if skills_key and skills_key in raw:
                val = raw[skills_key]
                extracted["skills"] = list(val) if isinstance(val, list) else [val]
                
            # Experience (work_history)
            exp_key = self._find_key("experience")
            if exp_key and exp_key in raw:
                raw_exp = raw[exp_key]
                exp_list = []
                if isinstance(raw_exp, list):
                    for item in raw_exp:
                        exp_list.append({
                            "company": item.get("company"),
                            "title": item.get("role") or item.get("title"),
                            "start": item.get("from") or item.get("start"),
                            "end": item.get("to") or item.get("end"),
                            "summary": item.get("summary")
                        })
                extracted["experience"] = exp_list
                
            # Education (education_info)
            edu_key = self._find_key("education")
            if edu_key and edu_key in raw:
                raw_edu = raw[edu_key]
                edu_list = []
                if isinstance(raw_edu, dict):
                    edu_list.append({
                        "institution": raw_edu.get("college") or raw_edu.get("institution"),
                        "degree": raw_edu.get("degree"),
                        "field": raw_edu.get("branch") or raw_edu.get("field"),
                        "end_year": raw_edu.get("graduation_year") or raw_edu.get("end_year")
                    })
                elif isinstance(raw_edu, list):
                    for item in raw_edu:
                        edu_list.append({
                            "institution": item.get("college") or item.get("institution"),
                            "degree": item.get("degree"),
                            "field": item.get("branch") or item.get("field"),
                            "end_year": item.get("graduation_year") or item.get("end_year")
                        })
                extracted["education"] = edu_list
                
        except Exception as e:
            logging.error(f"Error during ATS extraction: {e}")
            raw_record.errors.append(f"Extraction error: {str(e)}")
            
        return extracted
        
    def _find_key(self, canonical_field: str) -> str:
        for k, v in self.field_map.items():
            if v == canonical_field:
                return k
        return ""
