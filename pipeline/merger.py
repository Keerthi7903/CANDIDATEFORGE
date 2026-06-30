import hashlib
import logging
from typing import Dict, Any, List
from rapidfuzz import fuzz
from pipeline.normalization.phone import normalize_phone
from pipeline.normalization.date import normalize_date
from pipeline.normalization.country import normalize_country
from pipeline.normalization.skill import SkillNormalizer
from pipeline.normalization.location import parse_location

class Merger:
    def __init__(self):
        self.skill_normalizer = SkillNormalizer()
        self.sources_priority = ["github_api", "ats_json", "recruiter_notes"]
        self.source_methods = {
            "github_api": "api_extraction",
            "ats_json": "direct_mapping",
            "recruiter_notes": "regex_parse"
        }

    def merge(self, records: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merges normalized extracted data from multiple sources.
        records: dict mapping source_name -> extracted dict
        """
        normalized_sources = self._normalize_all_sources(records)
        
        canonical = {
            "candidate_id": None,
            "full_name": None,
            "emails": [],
            "phones": [],
            "location": {"city": None, "region": None, "country": None},
            "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
            "headline": None,
            "years_experience": None,
            "skills": [],
            "experience": [],
            "education": [],
            "provenance": [],
            "overall_confidence": 0.0
        }
        
        provenance_list = []
        
        # 1. Merge Scalar Fields (full_name, headline)
        for field in ["full_name", "headline"]:
            winner_val = None
            winner_src = None
            
            # Find the winning value
            for src in self.sources_priority:
                val = normalized_sources.get(src, {}).get(field)
                if val:
                    winner_val = val
                    winner_src = src
                    break
            
            canonical[field] = winner_val
            
            # Record provenance
            if winner_src:
                provenance_list.append({
                    "field": field,
                    "source": winner_src,
                    "method": self.source_methods[winner_src]
                })
                # Record conflict_discarded for other sources that had values
                for src in self.sources_priority:
                    if src != winner_src:
                        val = normalized_sources.get(src, {}).get(field)
                        if val:
                            provenance_list.append({
                                "field": field,
                                "source": src,
                                "method": "conflict_discarded"
                            })

        # 2. Merge Arrays (emails, phones)
        # Emails
        seen_emails = set()
        email_sources = {}
        for src in self.sources_priority:
            emails = normalized_sources.get(src, {}).get("emails") or []
            for email in emails:
                email_lower = email.strip().lower()
                if email_lower and email_lower not in seen_emails:
                    seen_emails.add(email_lower)
                    canonical["emails"].append(email)
                    email_sources[email_lower] = src
                    
        for idx, email in enumerate(canonical["emails"]):
            src = email_sources[email.lower()]
            provenance_list.append({
                "field": f"emails[{idx}]",
                "source": src,
                "method": self.source_methods[src]
            })

        # Phones
        seen_phones = set()
        phone_sources = {}
        phone_metadata = {} # keeps track of is_assumed flag
        for src in self.sources_priority:
            phones = normalized_sources.get(src, {}).get("phones") or []
            for p_tuple in phones:
                phone_val, is_assumed = p_tuple
                if phone_val and phone_val not in seen_phones:
                    seen_phones.add(phone_val)
                    canonical["phones"].append(phone_val)
                    phone_sources[phone_val] = src
                    phone_metadata[phone_val] = is_assumed
                    
        for idx, phone in enumerate(canonical["phones"]):
            src = phone_sources[phone]
            method = "assumed_region_normalization" if phone_metadata[phone] else self.source_methods[src]
            provenance_list.append({
                "field": f"phones[{idx}]",
                "source": src,
                "method": method
            })

        # 3. Merge Location
        loc_winner_src = None
        for src in self.sources_priority:
            loc = normalized_sources.get(src, {}).get("location")
            if loc and (loc.get("city") or loc.get("region") or loc.get("country")):
                canonical["location"] = loc
                loc_winner_src = src
                break
                
        if loc_winner_src:
            for subfield in ["city", "region", "country"]:
                provenance_list.append({
                    "field": f"location.{subfield}",
                    "source": loc_winner_src,
                    "method": self.source_methods[loc_winner_src]
                })
            # conflict discarded locations
            for src in self.sources_priority:
                if src != loc_winner_src:
                    loc = normalized_sources.get(src, {}).get("location")
                    if loc and (loc.get("city") or loc.get("region") or loc.get("country")):
                        provenance_list.append({
                            "field": "location",
                            "source": src,
                            "method": "conflict_discarded"
                        })

        # 4. Merge Links
        link_fields = ["linkedin", "github", "portfolio"]
        for field in link_fields:
            winner_val = None
            winner_src = None
            for src in self.sources_priority:
                val = normalized_sources.get(src, {}).get("links", {}).get(field)
                if val:
                    winner_val = val
                    winner_src = src
                    break
            canonical["links"][field] = winner_val
            if winner_src:
                provenance_list.append({
                    "field": f"links.{field}",
                    "source": winner_src,
                    "method": self.source_methods[winner_src]
                })
                # conflict discarded links
                for src in self.sources_priority:
                    if src != winner_src:
                        val = normalized_sources.get(src, {}).get("links", {}).get(field)
                        if val:
                            provenance_list.append({
                                "field": f"links.{field}",
                                "source": src,
                                "method": "conflict_discarded"
                            })
                            
        # other links (union)
        seen_other_links = set()
        other_sources = {}
        for src in self.sources_priority:
            other = normalized_sources.get(src, {}).get("links", {}).get("other") or []
            for link in other:
                link_clean = link.strip().lower()
                if link_clean and link_clean not in seen_other_links:
                    seen_other_links.add(link_clean)
                    canonical["links"]["other"].append(link)
                    other_sources[link_clean] = src
        for idx, link in enumerate(canonical["links"]["other"]):
            src = other_sources[link.lower()]
            provenance_list.append({
                "field": f"links.other[{idx}]",
                "source": src,
                "method": self.source_methods[src]
            })

        # 5. Merge Skills (union, boost confidences)
        merged_skills = {} # canonical name -> {sources: set}
        for src in self.sources_priority:
            skills = normalized_sources.get(src, {}).get("skills") or []
            for skill_tuple in skills:
                name, is_known = skill_tuple
                if name:
                    if name not in merged_skills:
                        merged_skills[name] = {"sources": set()}
                    merged_skills[name]["sources"].add(src)
                    
        for skill_name, info in merged_skills.items():
            canonical["skills"].append({
                "name": skill_name,
                "sources": sorted(list(info["sources"]))
            })
            
        for idx, skill in enumerate(canonical["skills"]):
            # Provenance for each skill
            for src in skill["sources"]:
                provenance_list.append({
                    "field": f"skills[{idx}]",
                    "source": src,
                    "method": self.source_methods[src]
                })

        # 6. Merge Experience
        raw_experiences = []
        for src in self.sources_priority:
            exps = normalized_sources.get(src, {}).get("experience") or []
            for exp in exps:
                raw_experiences.append((exp, src))
                
        merged_exps = []
        for exp, src in raw_experiences:
            company = exp.get("company")
            if not company:
                continue
                
            # Find fuzzy match in merged_exps
            match_idx = -1
            for idx, merged in enumerate(merged_exps):
                # Calculate ratio
                ratio = fuzz.token_set_ratio(company.lower(), merged["company"].lower())
                if ratio >= 80.0:
                    match_idx = idx
                    break
                    
            if match_idx == -1:
                # Add as new
                merged_exps.append({
                    "company": company,
                    "title": exp.get("title"),
                    "start": exp.get("start"),
                    "end": exp.get("end"),
                    "summary": exp.get("summary"),
                    "sources": [src],
                    "all_titles": {src: exp.get("title")},
                    "all_summaries": {src: exp.get("summary")},
                    "all_dates": {src: (exp.get("start"), exp.get("end"))}
                })
            else:
                # Merge existing
                merged = merged_exps[match_idx]
                merged["sources"].append(src)
                if exp.get("title"):
                    merged["all_titles"][src] = exp.get("title")
                if exp.get("summary"):
                    merged["all_summaries"][src] = exp.get("summary")
                merged["all_dates"][src] = (exp.get("start"), exp.get("end"))
                
        # Resolve merged experiences according to priority
        final_exps = []
        for idx, merged in enumerate(merged_exps):
            # Select title: highest priority source that has a title
            selected_title = None
            title_src = None
            for src in self.sources_priority:
                if src in merged["all_titles"] and merged["all_titles"][src]:
                    selected_title = merged["all_titles"][src]
                    title_src = src
                    break
            
            # Select dates: prefer more complete range (both start and end)
            selected_start = None
            selected_end = None
            date_src = None
            for src in self.sources_priority:
                if src in merged["all_dates"]:
                    start, end = merged["all_dates"][src]
                    if start:
                        selected_start = start
                        selected_end = end
                        date_src = src
                        # If it has both, it's a great match. Let's break
                        if end:
                            break
                            
            # Select summary: highest priority or longest summary
            selected_summary = None
            summary_src = None
            for src in self.sources_priority:
                if src in merged["all_summaries"] and merged["all_summaries"][src]:
                    selected_summary = merged["all_summaries"][src]
                    summary_src = src
                    break
                    
            final_exps.append({
                "company": merged["company"],
                "title": selected_title or "Unknown Role",
                "start": selected_start,
                "end": selected_end,
                "summary": selected_summary
            })
            
            # Provenance for experience
            # Company
            comp_src = merged["sources"][0]
            provenance_list.append({
                "field": f"experience[{idx}].company",
                "source": comp_src,
                "method": self.source_methods[comp_src]
            })
            # Title
            if title_src:
                provenance_list.append({
                    "field": f"experience[{idx}].title",
                    "source": title_src,
                    "method": self.source_methods[title_src]
                })
                # conflict discarded title
                for src in merged["sources"]:
                    if src != title_src and src in merged["all_titles"]:
                        provenance_list.append({
                            "field": f"experience[{idx}].title",
                            "source": src,
                            "method": "conflict_discarded"
                        })
            # Start/End dates
            if date_src:
                provenance_list.append({
                    "field": f"experience[{idx}].dates",
                    "source": date_src,
                    "method": self.source_methods[date_src]
                })
                
        canonical["experience"] = final_exps

        # 7. Merge Education
        raw_educations = []
        for src in self.sources_priority:
            edus = normalized_sources.get(src, {}).get("education") or []
            for edu in edus:
                raw_educations.append((edu, src))
                
        merged_edus = []
        for edu, src in raw_educations:
            inst = edu.get("institution")
            if not inst:
                continue
                
            match_idx = -1
            for idx, merged in enumerate(merged_edus):
                ratio = fuzz.token_set_ratio(inst.lower(), merged["institution"].lower())
                if ratio >= 80.0:
                    match_idx = idx
                    break
                    
            if match_idx == -1:
                merged_edus.append({
                    "institution": inst,
                    "degree": edu.get("degree"),
                    "field": edu.get("field"),
                    "end_year": edu.get("end_year"),
                    "sources": [src],
                    "all_degrees": {src: edu.get("degree")},
                    "all_fields": {src: edu.get("field")},
                    "all_years": {src: edu.get("end_year")}
                })
            else:
                merged = merged_edus[match_idx]
                merged["sources"].append(src)
                if edu.get("degree"):
                    merged["all_degrees"][src] = edu.get("degree")
                if edu.get("field"):
                    merged["all_fields"][src] = edu.get("field")
                if edu.get("end_year") is not None:
                    merged["all_years"][src] = edu.get("end_year")
                    
        final_edus = []
        for idx, merged in enumerate(merged_edus):
            # Select degree, field, year
            sel_degree = None
            deg_src = None
            for src in self.sources_priority:
                if src in merged["all_degrees"] and merged["all_degrees"][src]:
                    sel_degree = merged["all_degrees"][src]
                    deg_src = src
                    break
            sel_field = None
            for src in self.sources_priority:
                if src in merged["all_fields"] and merged["all_fields"][src]:
                    sel_field = merged["all_fields"][src]
                    break
            sel_year = None
            for src in self.sources_priority:
                if src in merged["all_years"] and merged["all_years"][src] is not None:
                    sel_year = merged["all_years"][src]
                    break
                    
            final_edus.append({
                "institution": merged["institution"],
                "degree": sel_degree,
                "field": sel_field,
                "end_year": sel_year
            })
            
            # Provenance
            inst_src = merged["sources"][0]
            provenance_list.append({
                "field": f"education[{idx}].institution",
                "source": inst_src,
                "method": self.source_methods[inst_src]
            })
            
        canonical["education"] = final_edus

        # 8. Calculate Years Experience
        canonical["years_experience"] = self._calculate_years_experience(canonical["experience"])
        if canonical["years_experience"] is not None:
            # Provenance for years experience is derived from the experiences
            provenance_list.append({
                "field": "years_experience",
                "source": "pipeline_calculation",
                "method": "date_duration_aggregation"
            })

        # 9. Generate Deterministic candidate_id
        # Hash of primary email, or full_name+github if no email
        candidate_id = None
        primary_email = canonical["emails"][0] if canonical["emails"] else None
        if primary_email:
            candidate_id = hashlib.sha256(primary_email.lower().encode("utf-8")).hexdigest()
            provenance_list.append({
                "field": "candidate_id",
                "source": "pipeline_calculation",
                "method": "email_sha256"
            })
        else:
            github_link = canonical["links"].get("github")
            name = canonical["full_name"] or "unknown"
            hash_str = f"{name.lower()}+{github_link.lower() if github_link else 'no_github'}"
            candidate_id = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()
            provenance_list.append({
                "field": "candidate_id",
                "source": "pipeline_calculation",
                "method": "name_github_sha256"
            })
            
        canonical["candidate_id"] = candidate_id
        canonical["provenance"] = provenance_list

        return canonical

    def _normalize_all_sources(self, records: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        normalized = {}
        for src, raw in records.items():
            normalized[src] = {}
            if not raw:
                continue
                
            # Scalars
            normalized[src]["full_name"] = raw.get("full_name")
            normalized[src]["headline"] = raw.get("headline")
            
            # Emails
            normalized[src]["emails"] = []
            for email in raw.get("emails") or []:
                if "@" in email:
                    normalized[src]["emails"].append(email.strip())
                    
            # Phones (normalized with is_assumed)
            normalized[src]["phones"] = []
            for phone in raw.get("phones") or []:
                p_norm, is_assumed = normalize_phone(phone)
                if p_norm:
                    normalized[src]["phones"].append((p_norm, is_assumed))
                    
            # Location
            loc_val = raw.get("location")
            if isinstance(loc_val, str):
                normalized[src]["location"] = parse_location(loc_val)
            elif isinstance(loc_val, dict):
                normalized[src]["location"] = {
                    "city": loc_val.get("city"),
                    "region": loc_val.get("region"),
                    "country": normalize_country(loc_val.get("country"))
                }
            else:
                normalized[src]["location"] = {"city": None, "region": None, "country": None}
                
            # Links
            raw_links = raw.get("links") or {}
            normalized[src]["links"] = {
                "linkedin": raw_links.get("linkedin"),
                "github": raw_links.get("github"),
                "portfolio": raw_links.get("portfolio"),
                "other": raw_links.get("other") or []
            }
            
            # Skills (normalize each skill name using skill aliases)
            normalized[src]["skills"] = []
            for skill in raw.get("skills") or []:
                s_norm, is_known = self.skill_normalizer.normalize(skill)
                if s_norm:
                    normalized[src]["skills"].append((s_norm, is_known))
                    
            # Experience (normalize dates)
            normalized[src]["experience"] = []
            for exp in raw.get("experience") or []:
                normalized[src]["experience"].append({
                    "company": exp.get("company"),
                    "title": exp.get("title"),
                    "start": normalize_date(exp.get("start")),
                    "end": normalize_date(exp.get("end")),
                    "summary": exp.get("summary")
                })
                
            # Education
            normalized[src]["education"] = []
            for edu in raw.get("education") or []:
                normalized[src]["education"].append({
                    "institution": edu.get("institution"),
                    "degree": edu.get("degree"),
                    "field": edu.get("field"),
                    "end_year": self._parse_int(edu.get("end_year"))
                })
                
        return normalized

    def _parse_int(self, val: Any) -> int | None:
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def _calculate_years_experience(self, experiences: List[Dict[str, Any]]) -> float | None:
        """
        Sum normalized dates durations (start, end).
        If end is Present/None, default to '2026-06'.
        Returns years rounded to 1 decimal place.
        """
        if not experiences:
            return None
            
        total_months = 0
        valid_ranges = 0
        
        for exp in experiences:
            start_str = exp.get("start")
            end_str = exp.get("end")
            
            if not start_str:
                continue
                
            # Parse start
            try:
                start_year, start_month = map(int, start_str.split("-"))
            except ValueError:
                continue
                
            # Parse end (defaulting to 2026-06 if Present/null)
            if not end_str:
                end_year, end_month = 2026, 6
            else:
                try:
                    end_year, end_month = map(int, end_str.split("-"))
                except ValueError:
                    end_year, end_month = 2026, 6
                    
            months = (end_year - start_year) * 12 + (end_month - start_month)
            # Add 1 month to make it inclusive of start & end month
            months = max(1, months + 1)
            
            total_months += months
            valid_ranges += 1
            
        if valid_ranges == 0:
            return None
            
        return round(total_months / 12.0, 1)
