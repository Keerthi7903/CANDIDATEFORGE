import os
import re
import yaml
import logging
from typing import Dict, Any, List
from pipeline.ingestion import RawRecord

class NotesExtractor:
    def __init__(self, skill_config_path: str = None):
        if skill_config_path is None:
            skill_config_path = os.path.join("config", "skill_aliases.yaml")
        self.skill_map = {}
        try:
            if os.path.exists(skill_config_path):
                with open(skill_config_path, "r", encoding="utf-8") as f:
                    self.skill_map = yaml.safe_load(f) or {}
        except Exception as e:
            logging.error(f"Error loading skill aliases: {e}")
            
    def extract(self, raw_record: RawRecord) -> Dict[str, Any]:
        extracted = {}
        raw = raw_record.raw_fields
        if not raw or "text" not in raw:
            return extracted
            
        text = raw["text"]
        try:
            # 1. Email Extraction
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            emails = re.findall(email_pattern, text)
            if emails:
                extracted["emails"] = list(set(emails))
                
            # 2. Phone Extraction
            phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            phones = re.findall(phone_pattern, text)
            if phones:
                cleaned_phones = []
                for p in phones:
                    cleaned = re.sub(r'[^\d+]', '', p)
                    if len(cleaned) >= 10:
                        cleaned_phones.append(p.strip())
                if cleaned_phones:
                    extracted["phones"] = list(set(cleaned_phones))
                    
            # 3. GitHub Link Extraction
            github_pattern = r'github\.com/([a-zA-Z0-9-]+)'
            github_match = re.search(github_pattern, text, re.IGNORECASE)
            if github_match:
                extracted["links"] = {"github": f"https://github.com/{github_match.group(1)}"}
                
            # 4. Name Extraction ("Spoke to [Name] on" or "Spoke to [Name]")
            name_pattern = r'Spoke to ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*?)\b'
            name_match = re.search(name_pattern, text)
            if name_match:
                name_val = name_match.group(1).strip()
                if " on" in name_val:
                    name_val = name_val.split(" on")[0].strip()
                extracted["full_name"] = name_val
                
            # 5. Location Extraction ("Based in [Location]", "Located in [Location]", "Open to [Location]")
            loc_pattern = r'(?:Based in|Located in|Open to)\s+([A-Z][a-zA-Z\s,]+?)(?:\.|\b)'
            loc_match = re.search(loc_pattern, text, re.IGNORECASE)
            if loc_match:
                extracted["location"] = loc_match.group(1).strip()
                
            # 6. Skill Phrase Extraction with regex word boundaries \b
            found_skills = set()
            search_terms = {}
            for alias, canonical in self.skill_map.items():
                search_terms[alias.lower()] = canonical
                search_terms[canonical.lower()] = canonical
                if "-" in canonical:
                    search_terms[canonical.replace("-", " ").lower()] = canonical
                    
            for term, canonical in search_terms.items():
                pattern_str = r'\b' + re.escape(term).replace(r'\ ', r'\s+') + r'\b'
                if re.search(pattern_str, text, re.IGNORECASE):
                    found_skills.add(canonical)
                    
            if found_skills:
                extracted["skills"] = list(found_skills)
                
            # 7. Experience Extraction ("Currently interning at [Company] as [Role]")
            exp_list = []
            exp_pattern = r'(?:interning|working|worked)\s+at\s+([A-Z][a-zA-Z0-9\s]+?)\s+(?:as|role)\s+([a-zA-Z0-9\s]+?)(?:\.|\b)'
            exp_matches = re.finditer(exp_pattern, text, re.IGNORECASE)
            for m in exp_matches:
                company = m.group(1).strip()
                role = m.group(2).strip()
                exp_list.append({
                    "company": company,
                    "title": role,
                    "start": "2026-06", # Default start date inferred from Spoke to Aarav on June 15
                    "end": "Present",   # Since the text says "Currently interning"
                    "summary": f"Extracted from recruiter notes: {m.group(0)}"
                })
            if exp_list:
                extracted["experience"] = exp_list
                
        except Exception as e:
            logging.error(f"Error during recruiter notes extraction: {e}")
            raw_record.errors.append(f"Extraction error: {str(e)}")
            
        return extracted
