import logging
from typing import Dict, Any, List

class ProjectionError(Exception):
    pass

class Projector:
    def project(self, canonical: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Projects canonical record based on config.
        """
        output = {}
        on_missing = config.get("on_missing", "null")
        fields = config.get("fields")
        
        if fields is None:
            output = {k: v for k, v in canonical.items() if k not in ("provenance", "overall_confidence")}
        else:
            for f_cfg in fields:
                out_path = f_cfg.get("path")
                from_expr = f_cfg.get("from") or out_path
                is_required = f_cfg.get("required", False)
                
                try:
                    val = self._evaluate_path(canonical, from_expr)
                except Exception:
                    val = None
                    
                if val is None or (isinstance(val, list) and not val):
                    if is_required:
                        if on_missing == "error":
                            raise ProjectionError(f"Required field '{out_path}' (from '{from_expr}') is missing.")
                        elif on_missing == "omit":
                            continue
                        else:
                            output[out_path] = None
                    else:
                        if on_missing == "omit":
                            continue
                        else:
                            output[out_path] = None
                else:
                    output[out_path] = val
                    
        if config.get("include_confidence", True):
            if "overall_confidence" in canonical:
                output["overall_confidence"] = canonical["overall_confidence"]
        else:
            if "overall_confidence" in output:
                del output["overall_confidence"]
                
        if config.get("include_provenance", True):
            if "provenance" in canonical:
                output["provenance"] = canonical["provenance"]
        else:
            if "provenance" in output:
                del output["provenance"]
                
        return output
        
    def _evaluate_path(self, canonical: Dict[str, Any], expr: str) -> Any:
        if not expr:
            return None
            
        if "[]. " in expr or "[]." in expr:
            parts = expr.split("[].")
            array_field = parts[0].strip()
            sub_field = parts[1].strip() if len(parts) > 1 else None
            arr = canonical.get(array_field) or []
            if sub_field:
                return [item.get(sub_field) for item in arr if isinstance(item, dict) and sub_field in item]
            return arr
            
        if "[" in expr and "]" in expr:
            parts = expr.split("[")
            field = parts[0].strip()
            index_str = parts[1].split("]")[0].strip()
            try:
                idx = int(index_str)
            except ValueError:
                idx = 0
            arr = canonical.get(field) or []
            if idx < len(arr):
                return arr[idx]
            return None
            
        if "." in expr:
            parts = expr.split(".")
            val = canonical
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p.strip())
                else:
                    return None
            return val
            
        return canonical.get(expr)
