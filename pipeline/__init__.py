import logging
from typing import Dict, Any, Optional

from pipeline.ingestion.ats_json_ingester import ATSJsonIngester
from pipeline.ingestion.github_ingester import GitHubIngester
from pipeline.ingestion.recruiter_notes_ingester import RecruiterNotesIngester

from pipeline.extraction.ats_extractor import ATSExtractor
from pipeline.extraction.github_extractor import GitHubExtractor
from pipeline.extraction.notes_extractor import NotesExtractor

from pipeline.merger import Merger
from pipeline.confidence import calculate_confidence
from pipeline.projector import Projector
from pipeline.validator import Validator

def run_pipeline(
    ats_path: Optional[str] = None,
    github_username: Optional[str] = None,
    notes_path: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    schema_path: Optional[str] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Orchestrates the entire Multi-Source Candidate Data Transformer pipeline.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    records = {}
    
    # 1. Ingestion & Extraction
    if ats_path:
        logging.info(f"Ingesting ATS JSON from {ats_path}...")
        raw_ats = ATSJsonIngester().ingest(ats_path)
        if not raw_ats.errors:
            logging.info("Extracting ATS JSON...")
            records["ats_json"] = ATSExtractor().extract(raw_ats)
        else:
            logging.warning(f"Skipping ATS JSON due to ingestion errors: {raw_ats.errors}")
            
    if github_username:
        logging.info(f"Ingesting GitHub profile for {github_username}...")
        
        other_name = None
        other_emails = []
        if "ats_json" in records:
            other_name = records["ats_json"].get("full_name")
            other_emails.extend(records["ats_json"].get("emails") or [])
        if "recruiter_notes" in records:
            if not other_name:
                other_name = records["recruiter_notes"].get("full_name")
            other_emails.extend(records["recruiter_notes"].get("emails") or [])
            
        raw_github = GitHubIngester().ingest(
            username=github_username,
            candidate_name=other_name,
            candidate_emails=other_emails
        )
        if not raw_github.errors:
            logging.info("Extracting GitHub profile...")
            records["github_api"] = GitHubExtractor().extract(raw_github)
        else:
            logging.warning(f"Skipping GitHub API due to ingestion errors: {raw_github.errors}")
            
    if notes_path:
        logging.info(f"Ingesting recruiter notes from {notes_path}...")
        raw_notes = RecruiterNotesIngester().ingest(notes_path)
        if not raw_notes.errors:
            logging.info("Extracting recruiter notes...")
            records["recruiter_notes"] = NotesExtractor().extract(raw_notes)
        else:
            logging.warning(f"Skipping Recruiter Notes due to ingestion errors: {raw_notes.errors}")
            
    if not records:
        raise ValueError("No input sources were successfully ingested. Pipeline cannot proceed.")
        
    # 2. Merge & Normalize
    logging.info("Merging and normalizing profiles...")
    merger = Merger()
    canonical = merger.merge(records)
    
    # 3. Confidence Scoring
    logging.info("Calculating confidence scores...")
    canonical = calculate_confidence(canonical)
    
    # 4. Project
    if config:
        logging.info("Projecting canonical profile according to configuration...")
        projector = Projector()
        output = projector.project(canonical, config)
    else:
        output = canonical
        
    # 5. Validate Canonical Record
    logging.info("Validating profile against JSON schema...")
    validator = Validator(schema_path)
    validator.validate(canonical)
    
    return output
