import os
import json
import logging
from flask import Flask, render_template, request
from pipeline.ingestion.ats_json_ingester import ATSJsonIngester
from pipeline.ingestion.github_ingester import GitHubIngester
from pipeline.ingestion.recruiter_notes_ingester import RecruiterNotesIngester
from pipeline.extraction.ats_extractor import ATSExtractor
from pipeline.extraction.github_extractor import GitHubExtractor
from pipeline.extraction.notes_extractor import NotesExtractor
from pipeline.merger import Merger
from pipeline.confidence import calculate_confidence
from pipeline.projector import Projector

app = Flask(__name__)

# Silence root logger warnings/errors to keep terminal output clean during Web UI runs
logging.getLogger().setLevel(logging.CRITICAL)
# Keep Flask server connection logs active
logging.getLogger("werkzeug").setLevel(logging.INFO)

os.makedirs("inputs", exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    output_json = None
    provenance = []
    overall_confidence = None
    warnings = []
    
    ats_content = ""
    github_username = ""
    notes_content = ""
    config_type = "default"
    
    if request.method == "GET":
        try:
            with open(os.path.join("inputs", "sample_ats.json"), "r", encoding="utf-8") as f:
                ats_content = f.read()
            github_username = "aarav-sharma"
            with open(os.path.join("inputs", "sample_notes.txt"), "r", encoding="utf-8") as f:
                notes_content = f.read()
        except Exception:
            pass
    
    if request.method == "POST":
        ats_content = request.form.get("ats_content", "").strip()
        github_username = request.form.get("github_username", "").strip()
        notes_content = request.form.get("notes_content", "").strip()
        config_type = request.form.get("config_type", "default")
        
        temp_ats_path = None
        temp_notes_path = None
        
        try:
            if ats_content:
                temp_ats_path = os.path.join("inputs", "temp_ats.json")
                with open(temp_ats_path, "w", encoding="utf-8") as f:
                    f.write(ats_content)
                    
            if notes_content:
                temp_notes_path = os.path.join("inputs", "temp_notes.txt")
                with open(temp_notes_path, "w", encoding="utf-8") as f:
                    f.write(notes_content)
                    
            records = {}
            if temp_ats_path:
                raw = ATSJsonIngester().ingest(temp_ats_path)
                if raw.errors:
                    warnings.extend(raw.errors)
                else:
                    records["ats_json"] = ATSExtractor().extract(raw)
                    
            if github_username:
                other_name = None
                other_emails = []
                if "ats_json" in records:
                    other_name = records["ats_json"].get("full_name")
                    other_emails.extend(records["ats_json"].get("emails") or [])
                if "recruiter_notes" in records:
                    if not other_name:
                        other_name = records["recruiter_notes"].get("full_name")
                    other_emails.extend(records["recruiter_notes"].get("emails") or [])
                
                raw = GitHubIngester().ingest(
                    username=github_username,
                    candidate_name=other_name,
                    candidate_emails=other_emails
                )
                if raw.errors:
                    warnings.extend(raw.errors)
                else:
                    records["github_api"] = GitHubExtractor().extract(raw)
                    
            if temp_notes_path:
                raw = RecruiterNotesIngester().ingest(temp_notes_path)
                if raw.errors:
                    warnings.extend(raw.errors)
                else:
                    records["recruiter_notes"] = NotesExtractor().extract(raw)
                    
            if not records:
                raise ValueError("No input data was successfully provided.")
                
            merger = Merger()
            canonical = merger.merge(records)
            canonical = calculate_confidence(canonical)
            
            provenance = canonical.get("provenance", [])
            overall_confidence = canonical.get("overall_confidence")
            
            config_dict = None
            if config_type == "custom":
                custom_path = os.path.join("config", "custom_config.json")
                if os.path.exists(custom_path):
                    with open(custom_path, "r", encoding="utf-8") as f:
                        config_dict = json.load(f)
                        
            projector = Projector()
            projected = projector.project(canonical, config_dict or {})
            
            output_json = json.dumps(projected, indent=2, ensure_ascii=False)
            
        except Exception as e:
            warnings.append(f"Pipeline error: {str(e)}")
        finally:
            if temp_ats_path and os.path.exists(temp_ats_path):
                try:
                    os.remove(temp_ats_path)
                except Exception:
                    pass
            if temp_notes_path and os.path.exists(temp_notes_path):
                try:
                    os.remove(temp_notes_path)
                except Exception:
                    pass
                
    return render_template(
        "index.html",
        ats_content=ats_content,
        github_username=github_username,
        notes_content=notes_content,
        config_type=config_type,
        output_json=output_json,
        provenance=provenance,
        overall_confidence=overall_confidence,
        warnings=warnings
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
