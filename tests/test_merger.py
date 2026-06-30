from pipeline.merger import Merger

def test_scalar_conflict_resolution():
    merger = Merger()
    records = {
        "ats_json": {
            "full_name": "Aarav Sharma",
            "emails": ["aarav.sharma@example.com"]
        },
        "recruiter_notes": {
            "full_name": "A. Sharma",
            "emails": ["aarav.dev@gmail.com"]
        }
    }
    canonical = merger.merge(records)
    assert canonical["full_name"] == "Aarav Sharma"
    
    prov = canonical["provenance"]
    winner_prov = [p for p in prov if p["field"] == "full_name" and p["source"] == "ats_json"]
    loser_prov = [p for p in prov if p["field"] == "full_name" and p["source"] == "recruiter_notes"]
    assert len(winner_prov) == 1
    assert winner_prov[0]["method"] == "direct_mapping"
    assert len(loser_prov) == 1
    assert loser_prov[0]["method"] == "conflict_discarded"

def test_skill_union_dedup():
    merger = Merger()
    records = {
        "ats_json": {
            "skills": ["Python", "Spring Boot"]
        },
        "recruiter_notes": {
            "skills": ["python", "PyTorch"]
        }
    }
    canonical = merger.merge(records)
    skills = [s["name"] for s in canonical["skills"]]
    assert "python" in skills
    assert "spring-boot" in skills
    assert "pytorch" in skills
    assert len(skills) == 3

def test_missing_source_graceful():
    merger = Merger()
    records = {
        "ats_json": {
            "full_name": "Aarav Sharma",
            "emails": ["aarav.sharma@example.com"]
        }
    }
    canonical = merger.merge(records)
    assert canonical["full_name"] == "Aarav Sharma"
    assert canonical["emails"] == ["aarav.sharma@example.com"]
