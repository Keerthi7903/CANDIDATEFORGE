import os
from unittest.mock import patch, MagicMock
from pipeline.ingestion.github_ingester import GitHubIngester
from pipeline.ingestion.recruiter_notes_ingester import RecruiterNotesIngester
from pipeline.extraction.notes_extractor import NotesExtractor
from pipeline import run_pipeline

def test_github_404_graceful():
    ingester = GitHubIngester()
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        
        raw = ingester.ingest("non-existent-user")
        assert len(raw.errors) == 1
        assert "not found" in raw.errors[0]
        assert raw.raw_fields == {}

def test_empty_notes_file(tmp_path):
    notes_file = tmp_path / "notes_empty.txt"
    notes_file.write_text("")
    
    ingester = RecruiterNotesIngester()
    raw = ingester.ingest(str(notes_file))
    assert not raw.errors
    assert raw.raw_fields == {"text": ""}
    
    extractor = NotesExtractor()
    extracted = extractor.extract(raw)
    assert extracted == {}

def test_all_sources_missing_except_one(tmp_path):
    notes_file = tmp_path / "notes.txt"
    notes_file.write_text("Spoke to Aarav on June 15. Email: aarav.sharma@example.com.")
    
    result = run_pipeline(notes_path=str(notes_file))
    
    assert result["full_name"] == "Aarav"
    assert result["emails"] == ["aarav.sharma@example.com"]
    assert result["candidate_id"] is not None

def test_github_identity_mismatch(tmp_path):
    ats_file = tmp_path / "sample_ats.json"
    ats_file.write_text('{"applicant_name": "Aarav Sharma", "contact_email": "aarav.sharma@example.com"}')
    
    notes_file = tmp_path / "sample_notes.txt"
    notes_file.write_text("Spoke to Aarav on June 15. Email: aarav.sharma@example.com.")
    
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "login": "priyanair",
            "name": "Priya Nair",
            "email": "priya.nair@example.com",
            "bio": "Developer",
            "location": "Kerala",
            "blog": "",
            "html_url": "https://github.com/priyanair"
        }
        mock_get.return_value = mock_resp
        
        result = run_pipeline(
            ats_path=str(ats_file),
            github_username="priyanair",
            notes_path=str(notes_file)
        )
        
        assert result["full_name"] == "Aarav Sharma"
        assert "aarav.sharma@example.com" in result["emails"]
        assert "priya.nair@example.com" not in result["emails"]

