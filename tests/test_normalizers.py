from pipeline.normalization.phone import normalize_phone
from pipeline.normalization.date import normalize_date
from pipeline.normalization.skill import SkillNormalizer

def test_phone_e164_with_country_code():
    res, assumed = normalize_phone("+919876543210")
    assert res == "+919876543210"
    assert assumed is False

def test_phone_e164_no_country_code():
    res, assumed = normalize_phone("9876543210")
    assert res == "+919876543210"
    assert assumed is True

def test_phone_invalid():
    res, assumed = normalize_phone("abc123")
    assert res is None

def test_skill_canonical():
    norm = SkillNormalizer()
    res, known = norm.normalize("JS")
    assert res == "javascript"
    assert known is True
    
    res, known = norm.normalize("PyTorch")
    assert res == "pytorch"
    assert known is True

def test_date_formats():
    assert normalize_date("June 2026") == "2026-06"
    assert normalize_date("06/2026") == "2026-06"
    assert normalize_date("2026-06") == "2026-06"
    assert normalize_date("Present") is None
