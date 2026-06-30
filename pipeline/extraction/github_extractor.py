import logging
from typing import Dict, Any
from pipeline.ingestion import RawRecord

class GitHubExtractor:
    def extract(self, raw_record: RawRecord) -> Dict[str, Any]:
        extracted = {}
        raw = raw_record.raw_fields
        if not raw:
            return extracted
            
        try:
            # Full Name (fallback to login if name is missing/null)
            name = raw.get("name") or raw.get("login")
            if name:
                extracted["full_name"] = name
                
            # Emails
            email = raw.get("email")
            if email:
                extracted["emails"] = [email]
                
            # Headline
            bio = raw.get("bio")
            if bio:
                extracted["headline"] = bio
                
            # Location
            location = raw.get("location")
            if location:
                extracted["location"] = location
                
            # Links
            github_url = raw.get("html_url")
            blog_url = raw.get("blog")
            links = {}
            if github_url:
                links["github"] = github_url
            if blog_url:
                links["portfolio"] = blog_url
            if links:
                extracted["links"] = links
                
            # Skills (derived from repo languages)
            repos = raw.get("repos") or []
            skills = set()
            for repo in repos:
                lang = repo.get("language")
                if lang:
                    skills.add(lang.lower())
            if skills:
                extracted["skills"] = list(skills)
                
        except Exception as e:
            logging.error(f"Error during GitHub extraction: {e}")
            raw_record.errors.append(f"Extraction error: {str(e)}")
            
        return extracted
