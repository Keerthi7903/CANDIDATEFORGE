from pipeline.projector import Projector

def test_projector_fields():
    projector = Projector()
    canonical = {
        "full_name": "Aarav Sharma",
        "emails": ["aarav.sharma@example.com", "aarav.dev@gmail.com"],
        "phones": ["+919876543210"],
        "skills": [{"name": "python", "confidence": 0.90}, {"name": "spring-boot", "confidence": 0.85}],
        "overall_confidence": 0.85,
        "provenance": [{"field": "full_name", "source": "ats_json"}]
    }
    
    config = {
        "fields": [
            { "path": "full_name", "type": "string", "required": True },
            { "path": "primary_email", "from": "emails[0]", "type": "string", "required": True },
            { "path": "phone", "from": "phones[0]", "type": "string" },
            { "path": "skills", "from": "skills[].name", "type": "string[]" }
        ],
        "include_confidence": True,
        "include_provenance": False,
        "on_missing": "null"
    }
    
    projected = projector.project(canonical, config)
    assert projected["full_name"] == "Aarav Sharma"
    assert projected["primary_email"] == "aarav.sharma@example.com"
    assert projected["phone"] == "+919876543210"
    assert projected["skills"] == ["python", "spring-boot"]
    assert projected["overall_confidence"] == 0.85
    assert "provenance" not in projected
