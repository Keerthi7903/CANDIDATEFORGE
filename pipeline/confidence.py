import logging
from typing import Dict, Any, List

def calculate_confidence(canonical: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes field-level confidence and overall_confidence.
    Mutates/updates the canonical record and returns it.
    """
    provenance = canonical.get("provenance") or []
    
    # Group provenance by field path to count unique sources
    field_sources = {}
    field_methods = {}
    for entry in provenance:
        field = entry.get("field")
        source = entry.get("source")
        method = entry.get("method")
        
        if field not in field_sources:
            field_sources[field] = set()
            field_methods[field] = []
            
        field_sources[field].add(source)
        field_methods[field].append(method)
        
    def get_path_confidence(path: str, has_val: bool) -> float:
        if not has_val:
            return 0.0
            
        if path.startswith("phones"):
            methods = field_methods.get(path) or []
            if "assumed_region_normalization" in methods:
                return 0.60
                
        sources = field_sources.get(path) or set()
        sources = {s for s in sources if s != "pipeline_calculation"}
        
        if not sources:
            if path in field_sources:
                return 0.90
            return 0.0
            
        cnt = len(sources)
        if cnt >= 3:
            return 0.95
        elif cnt == 2:
            return 0.85
        else:
            src = list(sources)[0]
            if src == "github_api":
                return 0.90
            elif src == "ats_json":
                return 0.80
            elif src == "recruiter_notes":
                return 0.65
            else:
                return 0.70
                
    for idx, skill in enumerate(canonical.get("skills") or []):
        sources = skill.get("sources") or []
        cnt = len(sources)
        
        if cnt >= 3:
            conf = 0.95
        elif cnt == 2:
            conf = 0.85
        elif cnt == 1:
            src = sources[0]
            if src == "github_api":
                conf = 0.90
            elif src == "ats_json":
                conf = 0.80
            else:
                conf = 0.65
        else:
            conf = 0.0
            
        skill["confidence"] = conf

    weights = {
        "full_name": 2.0,
        "emails": 2.0,
        "phones": 1.5,
        "skills": 1.5,
        "location": 1.0,
        "links": 1.0,
        "headline": 1.0,
        "experience": 1.0,
        "education": 1.0,
        "years_experience": 1.0
    }
    
    confidences = {}
    
    confidences["full_name"] = get_path_confidence("full_name", bool(canonical.get("full_name")))
    
    emails = canonical.get("emails") or []
    if emails:
        confidences["emails"] = sum(get_path_confidence(f"emails[{i}]", True) for i in range(len(emails))) / len(emails)
    else:
        confidences["emails"] = 0.0
        
    phones = canonical.get("phones") or []
    if phones:
        confidences["phones"] = sum(get_path_confidence(f"phones[{i}]", True) for i in range(len(phones))) / len(phones)
    else:
        confidences["phones"] = 0.0
        
    skills = canonical.get("skills") or []
    if skills:
        confidences["skills"] = sum(s.get("confidence", 0.0) for s in skills) / len(skills)
    else:
        confidences["skills"] = 0.0
        
    loc = canonical.get("location") or {}
    loc_confs = []
    for sub in ["city", "region", "country"]:
        loc_confs.append(get_path_confidence(f"location.{sub}", bool(loc.get(sub))))
    confidences["location"] = sum(loc_confs) / 3.0
    
    links = canonical.get("links") or {}
    link_confs = []
    for sub in ["linkedin", "github", "portfolio"]:
        link_confs.append(get_path_confidence(f"links.{sub}", bool(links.get(sub))))
    confidences["links"] = sum(link_confs) / 3.0
    
    confidences["headline"] = get_path_confidence("headline", bool(canonical.get("headline")))
    
    exps = canonical.get("experience") or []
    if exps:
        exp_confs = []
        for i in range(len(exps)):
            exp_confs.append(get_path_confidence(f"experience[{i}].company", True))
        confidences["experience"] = sum(exp_confs) / len(exps)
    else:
        confidences["experience"] = 0.0
        
    edus = canonical.get("education") or []
    if edus:
        edu_confs = []
        for i in range(len(edus)):
            edu_confs.append(get_path_confidence(f"education[{i}].institution", True))
        confidences["education"] = sum(edu_confs) / len(edus)
    else:
        confidences["education"] = 0.0
        
    confidences["years_experience"] = get_path_confidence("years_experience", canonical.get("years_experience") is not None)
    
    weighted_sum = 0.0
    total_weight = 0.0
    for field, weight in weights.items():
        weighted_sum += confidences[field] * weight
        total_weight += weight
        
    overall = weighted_sum / total_weight if total_weight > 0 else 0.0
    canonical["overall_confidence"] = round(overall, 2)
    
    return canonical
