# mcp/geoadvisor.py
from pathlib import Path
import json
from typing import Dict, List, Optional, Union

class GeoAdvisor:
    """
    Three-layer geographic suitability engine for Census data.
    
    Layer 1: Table availability (deterministic - can we?)
    Layer 2: Semantic heterogeneity hints (should we? - based on spatial variance)
    Layer 3: Statistical validation (MOE checks - is it reliable?)
    """

    def __init__(self,
                 table_geo_file: str = "data/table_geos.json",
                 geo_weight_file: Optional[str] = None,
                 moe_resolver=None):
        """
        Initialize GeoAdvisor with data files.
        
        Args:
            table_geo_file: Path to table→geography mapping JSON
            geo_weight_file: Path to variable→geography weight mapping JSON (optional)
            moe_resolver: Function for real-time MOE checking (optional)
        """
        self.table_geo_file = table_geo_file
        self.geo_weight_file = geo_weight_file
        self.moe_resolver = moe_resolver
        
        # Load table availability data (Layer 1)
        try:
            with open(table_geo_file, 'r') as f:
                self.table_geo = json.load(f)
            print(f"✅ Loaded {len(self.table_geo)} table geography mappings")
        except FileNotFoundError:
            raise FileNotFoundError(f"Table geography file not found: {table_geo_file}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in table geography file: {table_geo_file}")
        
        # Load semantic geography weights (Layer 2) - optional
        self.geo_weights = {}
        if geo_weight_file:
            try:
                with open(geo_weight_file, 'r') as f:
                    self.geo_weights = json.load(f)
                print(f"✅ Loaded {len(self.geo_weights)} variable geography weights")
            except FileNotFoundError:
                print(f"⚠️  Geography weight file not found: {geo_weight_file}")
            except json.JSONDecodeError:
                print(f"⚠️  Invalid JSON in geography weight file: {geo_weight_file}")
        
        # Geographic hierarchy for suggestions (ordered by specificity)
        self.geo_hierarchy = [
            'us', 'state', 'county', 'place', 'tract', 'block_group'
        ]
        
        # Geography display names
        self.geo_display_names = {
            'us': 'National',
            'state': 'State', 
            'county': 'County',
            'place': 'Place',
            'tract': 'Census Tract',
            'block_group': 'Block Group',
            'msa': 'Metropolitan Statistical Area',
            'cd': 'Congressional District',
            'zcta': 'ZIP Code Tabulation Area',
            'puma': 'Public Use Microdata Area'
        }

    def extract_table_id(self, variable_id: str) -> str:
        """Extract table ID from variable ID (e.g., B01001_001E → B01001)."""
        if '_' in variable_id:
            return variable_id.split('_')[0]
        return variable_id[:6] if len(variable_id) >= 6 else variable_id

    def is_available(self, variable_id: str, geo_level: str) -> bool:
        """
        Layer 1: Check if variable is available at geographic level.
        
        Args:
            variable_id: Census variable ID (e.g., B01001_001E)
            geo_level: Geographic level (e.g., 'tract', 'county')
            
        Returns:
            True if variable is published at this geographic level
        """
        table_id = self.extract_table_id(variable_id)
        available_levels = self.table_geo.get(table_id, [])
        return geo_level in available_levels

    def get_available_levels(self, variable_id: str) -> List[str]:
        """Get all geographic levels where variable is available."""
        table_id = self.extract_table_id(variable_id)
        return self.table_geo.get(table_id, [])

    def suggest_coarser_levels(self, variable_id: str, current_level: str) -> List[str]:
        """
        Suggest coarser geographic levels that are available.
        
        Args:
            variable_id: Census variable ID
            current_level: Current geographic level that failed
            
        Returns:
            List of coarser levels available for this variable
        """
        available = self.get_available_levels(variable_id)
        
        # Find coarser levels (earlier in hierarchy)
        try:
            current_idx = self.geo_hierarchy.index(current_level)
            coarser_available = [
                level for level in self.geo_hierarchy[:current_idx] 
                if level in available
            ]
            return coarser_available
        except ValueError:
            # Current level not in standard hierarchy, return all available
            return available

    def get_geographic_hint(self, variable_id: str) -> Optional[Dict]:
        """
        Layer 2: Get semantic geographic hint for variable.
        
        Returns semantic analysis of how spatially variable this phenomenon is.
        High weights suggest more local variation, low weights suggest more uniformity.
        """
        if not self.geo_weights:
            return None
            
        weight = self.geo_weights.get(variable_id)
        if weight is None:
            return None
            
        # Interpret weight levels (based on your sample analysis)
        if weight < 0.30:
            category = "nationally_stable"
            guidance = "Low spatial variation - county or state level may be sufficient"
        elif weight < 0.38:
            category = "regionally_variable" 
            guidance = "Moderate spatial variation - county level recommended"
        else:
            category = "locally_clustered"
            guidance = "High spatial variation - tract or block group recommended"
            
        return {
            "geography_weight": weight,
            "spatial_category": category,
            "guidance": guidance
        }

    def check_moe_reliability(self, variable_id: str, geo_level: str, geoid: str) -> Optional[Dict]:
        """
        Layer 3: Check margin of error for statistical reliability.
        
        Args:
            variable_id: Census variable ID
            geo_level: Geographic level 
            geoid: Specific geographic identifier
            
        Returns:
            MOE analysis or None if MOE resolver not available
        """
        if not self.moe_resolver:
            return None
            
        try:
            moe_ratio = self.moe_resolver(variable_id, geo_level, geoid)
            if moe_ratio is None:
                return None
                
            # Classify reliability
            if moe_ratio < 0.10:
                reliability = "high"
                guidance = "Reliable estimate"
            elif moe_ratio < 0.30:
                reliability = "medium" 
                guidance = "Use with caution"
            else:
                reliability = "low"
                guidance = "Consider aggregating to larger geography"
                
            return {
                "moe_ratio": moe_ratio,
                "reliability": reliability,
                "guidance": guidance
            }
        except Exception as e:
            return {"error": f"MOE check failed: {str(e)}"}

    def recommend(self, variable_id: str, geo_level: str, geoid: Optional[str] = None) -> Dict:
        """
        Main recommendation engine - combines all three layers.
        
        Args:
            variable_id: Census variable ID (e.g., B01001_001E)
            geo_level: Requested geographic level (e.g., 'tract')
            geoid: Specific geographic ID for MOE checking (optional)
            
        Returns:
            Recommendation dictionary with status, message, and suggestions
        """
        result = {
            "variable_id": variable_id,
            "requested_level": geo_level,
            "table_id": self.extract_table_id(variable_id)
        }
        
        # Layer 1: Availability check
        if not self.is_available(variable_id, geo_level):
            coarser_levels = self.suggest_coarser_levels(variable_id, geo_level)
            result.update({
                "status": "blocked",
                "reason": "not_published",
                "message": f"Variable {variable_id} not published at {self.geo_display_names.get(geo_level, geo_level)} level",
                "available_levels": coarser_levels,
                "suggestion": f"Try {', '.join(coarser_levels)} instead" if coarser_levels else "No alternative levels available"
            })
            return result
        
        # Layer 3: MOE reliability check (if geoid provided)
        moe_analysis = None
        if geoid:
            moe_analysis = self.check_moe_reliability(variable_id, geo_level, geoid)
            if moe_analysis and moe_analysis.get("reliability") == "low":
                coarser_levels = self.suggest_coarser_levels(variable_id, geo_level)
                result.update({
                    "status": "warning",
                    "reason": "high_moe",
                    "message": f"High sampling error (MOE/estimate = {moe_analysis['moe_ratio']:.1%})",
                    "moe_analysis": moe_analysis,
                    "available_levels": coarser_levels,
                    "suggestion": f"Consider using {coarser_levels[0] if coarser_levels else 'coarser geography'} for more reliable estimates"
                })
                return result
        
        # Layer 2: Semantic geographic hint
        geo_hint = self.get_geographic_hint(variable_id)
        
        # Success case
        result.update({
            "status": "ok",
            "message": f"Variable available at {self.geo_display_names.get(geo_level, geo_level)} level",
            "geographic_hint": geo_hint,
            "moe_analysis": moe_analysis
        })
        
        # Add contextual guidance
        if geo_hint:
            if geo_hint["spatial_category"] == "locally_clustered" and geo_level in ['county', 'state']:
                result["message"] += f" | Note: {geo_hint['guidance']}"
            elif geo_hint["spatial_category"] == "nationally_stable" and geo_level in ['tract', 'block_group']:
                result["message"] += f" | Note: {geo_hint['guidance']}"
        
        return result

    def batch_recommend(self, requests: List[Dict]) -> List[Dict]:
        """
        Process multiple recommendation requests efficiently.
        
        Args:
            requests: List of dicts with 'variable_id', 'geo_level', 'geoid' (optional)
            
        Returns:
            List of recommendation results
        """
        results = []
        for req in requests:
            variable_id = req.get('variable_id')
            geo_level = req.get('geo_level') 
            geoid = req.get('geoid')
            
            if not variable_id or not geo_level:
                results.append({
                    "error": "Missing required fields: variable_id, geo_level",
                    "request": req
                })
                continue
                
            recommendation = self.recommend(variable_id, geo_level, geoid)
            results.append(recommendation)
            
        return results

    def get_stats(self) -> Dict:
        """Get statistics about loaded data."""
        stats = {
            "tables_loaded": len(self.table_geo),
            "variables_with_weights": len(self.geo_weights),
            "moe_resolver_available": self.moe_resolver is not None,
            "supported_geographies": list(self.geo_display_names.keys())
        }
        
        # Geography distribution
        geo_counts = {}
        for table_id, levels in self.table_geo.items():
            for level in levels:
                geo_counts[level] = geo_counts.get(level, 0) + 1
        
        stats["geography_distribution"] = geo_counts
        return stats
