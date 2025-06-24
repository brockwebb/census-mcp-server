# src/knowledge/llm_mapper.py

import json
import requests
import rdflib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import openai
import time

@dataclass
class ConceptMapping:
    """Result of mapping a concept to Census variables"""
    concept: str
    census_variables: List[str]
    confidence: float
    reasoning: str
    coos_uri: Optional[str] = None
    statistical_method: Optional[str] = None
    universe: Optional[str] = None
    calculation_note: Optional[str] = None

class LLMConceptMapper:
    """Maps COOS concepts to Census variables using LLM reasoning"""
    
    def __init__(self, api_key: str = None):
        self.client = openai.OpenAI(api_key=api_key)
        self.coos_concepts = self._load_coos_concepts()
        self.census_variables = self._load_census_variables()
        
    def _load_coos_concepts(self) -> Dict[str, dict]:
        """Load COOS concepts from downloaded TTL file"""
        # Try to find the coos.ttl file by searching up the directory tree
        current_dir = Path.cwd()
        
        # Search current and parent directories
        search_dirs = [current_dir] + list(current_dir.parents)
        
        coos_path = None
        for search_dir in search_dirs:
            potential_path = search_dir / "knowledge-base" / "third_party" / "ontologies" / "coos.ttl"
            if potential_path.exists():
                coos_path = potential_path
                break
        
        if coos_path is None:
            # Show current directory and what we're looking for
            print(f"Current directory: {Path.cwd()}")
            print("Looking for: knowledge-base/third_party/ontologies/coos.ttl")
            raise FileNotFoundError(f"COOS ontology not found. Current dir: {Path.cwd()}")
        
        # Parse RDF/TTL file
        graph = rdflib.Graph()
        graph.parse(coos_path, format="turtle")
        
        concepts = {}
        
        # Extract concepts from RDF graph
        # This is a simplified extraction - we'll refine based on actual COOS structure
        for subject, predicate, obj in graph:
            if "Concept" in str(predicate) or "concept" in str(subject).lower():
                concept_id = str(subject).split("#")[-1] if "#" in str(subject) else str(subject)
                if concept_id not in concepts:
                    concepts[concept_id] = {
                        "uri": str(subject),
                        "label": concept_id,
                        "definition": ""
                    }
        
        print(f"Loaded {len(concepts)} COOS concepts")
        return concepts
    
    def _load_census_variables(self) -> Dict[str, dict]:
        """Load Census ACS variables from API"""
        try:
            # Fetch 2022 ACS 5-year variables
            url = "https://api.census.gov/data/2022/acs/acs5/variables.json"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            variables_data = response.json()
            variables = variables_data.get("variables", {})
            
            # Filter to meaningful variables (exclude technical/metadata variables)
            filtered_variables = {}
            for var_id, var_info in variables.items():
                if (var_id.startswith("B") or var_id.startswith("C")) and "_" in var_id:
                    filtered_variables[var_id] = {
                        "label": var_info.get("label", ""),
                        "concept": var_info.get("concept", ""),
                        "group": var_info.get("group", "")
                    }
            
            print(f"Loaded {len(filtered_variables)} Census variables")
            return filtered_variables
            
        except Exception as e:
            print(f"Error loading Census variables: {e}")
            return {}
    
    def map_concept_to_variables(self, concept: str, concept_definition: str = "") -> ConceptMapping:
        """Map a single COOS concept to Census variables using LLM"""
        
        # Find relevant Census variables by concept similarity
        candidate_variables = self._find_candidate_variables(concept, concept_definition)
        
        # Use LLM to select best mappings
        mapping_result = self._llm_map_concept(concept, concept_definition, candidate_variables)
        
        return mapping_result
    
    def _find_candidate_variables(self, concept: str, definition: str, max_candidates: int = 15) -> List[dict]:
        """Find Census variables that might match the concept"""
        
        # Enhanced concept-specific keyword mapping
        concept_keywords = {
            "medianhouseholdincome": ["B19013", "median household income"],
            "householdincome": ["B19013", "household income"],
            "income": ["B19013", "B19001", "income"],
            "povertyrate": ["B17001", "poverty status"],
            "poverty": ["B17001", "B17017", "poverty"],
            "educationalattainment": ["B15003", "B15002", "educational attainment"],
            "education": ["B15003", "B15002", "education", "school"],
            "housingtenure": ["B25003", "tenure"],
            "housing": ["B25003", "B25001", "housing", "owner", "renter"],
            "unemploymentrate": ["B23025", "employment status"],
            "unemployment": ["B23025", "B08007", "unemployed", "labor"],
            "medianage": ["B01002", "median age"],
            "age": ["B01002", "age"],
            "raceethnicity": ["B02001", "B03002", "race", "ethnicity"],
            "race": ["B02001", "B03002", "race", "hispanic"],
            "householdsize": ["B25010", "B11001", "household size"],
            "household": ["B11001", "household", "family"],
            "medianhomevalue": ["B25077", "home value"],
            "homevalue": ["B25077", "B25097", "value"],
            "commutetime": ["B08013", "travel time"],
            "commute": ["B08013", "B08301", "commute", "travel"]
        }
        
        # Get relevant keywords for this concept
        concept_key = concept.lower().replace(" ", "")
        definition_lower = definition.lower()
        
        relevant_keywords = []
        
        # First try exact concept match
        if concept_key in concept_keywords:
            relevant_keywords.extend(concept_keywords[concept_key])
        else:
            # Try partial matches
            for key, keywords in concept_keywords.items():
                if key in concept_key or any(word in concept_key for word in key.split()):
                    relevant_keywords.extend(keywords)
        
        # Add definition keywords as backup
        relevant_keywords.extend(definition_lower.split())
        
        candidates = []
        for var_id, var_info in self.census_variables.items():
            label = var_info.get("label", "").lower()
            concept_text = var_info.get("concept", "").lower()
            
            # Score based on keyword relevance
            score = 0
            for keyword in relevant_keywords:
                if len(keyword) > 2:  # Skip very short terms
                    if keyword.lower() in label:
                        score += 3  # Higher weight for label matches
                    if keyword.lower() in concept_text:
                        score += 2
                    if keyword.lower() in var_id.lower():
                        score += 4  # Highest weight for variable ID matches
            
            # PRIORITY BOOST for base tables (no race/ethnicity suffix)
            # Base tables like B17001_001E are more general than B17001A_001E (race-specific)
            if score > 0:
                # Check if this is a base table (no letter suffix like A, B, C, etc.)
                var_parts = var_id.split('_')
                if len(var_parts) == 2:  # Format: B17001_001E
                    table_id = var_parts[0]
                    var_num = var_parts[1].replace('E', '')  # Remove 'E' suffix
                    
                    # If table ID has no letter suffix, it's a base table
                    if table_id[-1].isdigit():  # Ends with digit, not letter
                        score += 10  # Big boost for base tables
                        
                        # EXTRA boost for summary variables (001, 002 are usually totals)
                        if var_num in ['001', '002']:
                            score += 20  # Huge boost for total/summary variables
                            
                        # Special boost for poverty rate calculation variables
                        if table_id == 'B17001' and var_num in ['001', '002']:
                            score += 30  # B17001_001E (total) and B17001_002E (below poverty)
            
            if score > 0:
                candidates.append({
                    "variable_id": var_id,
                    "score": score,
                    **var_info
                })
        
        # Sort by score and return top candidates
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:max_candidates]
    
    def _llm_map_concept(self, concept: str, definition: str, candidates: List[dict]) -> ConceptMapping:
        """Use LLM to map concept to best Census variables"""
        
        # Prepare candidates for LLM
        candidate_text = ""
        for i, candidate in enumerate(candidates[:10]):  # Limit to top 10 for token efficiency
            candidate_text += f"{i+1}. {candidate['variable_id']}: {candidate['label']}\n"
            candidate_text += f"   Concept: {candidate['concept']}\n\n"
        
        prompt = f"""You are a statistical expert mapping demographic concepts to U.S. Census variables.

CONCEPT TO MAP:
Name: {concept}
Definition: {definition or 'No definition provided'}

CANDIDATE CENSUS VARIABLES:
{candidate_text}

TASK: Select the best Census variable(s) that match this concept. Consider:
1. Conceptual alignment (does the variable measure what the concept describes?)
2. Universe appropriateness (households vs individuals vs families)
3. Statistical method (median vs mean, rate vs count)

SPECIAL GUIDANCE FOR RATES:
- For rate concepts (unemployment rate, poverty rate), you need BOTH:
  * Numerator variable (people with condition) 
  * Denominator variable (total population for universe)
- Example: Poverty rate = B17001_002 (below poverty) / B17001_001 (total)
- Look for paired variables like "Total" and specific condition counts

SPECIAL GUIDANCE FOR MEDIAN/MEAN:
- "Median" concepts should map to variables containing "Median" in the label
- Avoid aggregate or total income variables for median concepts

Respond with JSON only:
{{
    "selected_variables": ["variable_id1", "variable_id2"],
    "confidence": 0.85,
    "reasoning": "Explanation of why these variables were chosen",
    "statistical_method": "median|mean|rate|count|other",
    "universe": "households|individuals|families|other",
    "calculation_note": "For rates: explain numerator/denominator if applicable"
}}

Be conservative with confidence scores. Only use >0.9 if you're very certain."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean up markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]  # Remove ```json
            if result_text.startswith("```"):
                result_text = result_text[3:]   # Remove ```
            if result_text.endswith("```"):
                result_text = result_text[:-3]  # Remove trailing ```
            
            result_text = result_text.strip()
            
            # Parse JSON response
            try:
                result = json.loads(result_text)
                
                return ConceptMapping(
                    concept=concept,
                    census_variables=result.get("selected_variables", []),
                    confidence=result.get("confidence", 0.0),
                    reasoning=result.get("reasoning", ""),
                    statistical_method=result.get("statistical_method"),
                    universe=result.get("universe"),
                    calculation_note=result.get("calculation_note")
                )
                
            except json.JSONDecodeError:
                print(f"Failed to parse LLM response: {result_text}")
                return ConceptMapping(
                    concept=concept,
                    census_variables=[],
                    confidence=0.0,
                    reasoning="Failed to parse LLM response"
                )
                
        except Exception as e:
            print(f"LLM API error: {e}")
            return ConceptMapping(
                concept=concept,
                census_variables=[],
                confidence=0.0,
                reasoning=f"API error: {str(e)}"
            )
    
    def batch_map_concepts(self, concepts: List[str], delay: float = 1.0) -> List[ConceptMapping]:
        """Process multiple concepts with rate limiting"""
        
        results = []
        for i, concept in enumerate(concepts):
            print(f"Processing concept {i+1}/{len(concepts)}: {concept}")
            
            # Get concept definition from COOS if available
            concept_info = self.coos_concepts.get(concept, {})
            definition = concept_info.get("definition", "")
            
            # Map concept
            mapping = self.map_concept_to_variables(concept, definition)
            results.append(mapping)
            
            # Rate limiting
            if delay > 0 and i < len(concepts) - 1:
                time.sleep(delay)
        
        return results
    
    def save_mappings(self, mappings: List[ConceptMapping], output_path: str):
        """Save mapping results to JSON file"""
        
        mappings_data = []
        for mapping in mappings:
            mappings_data.append({
                "concept": mapping.concept,
                "census_variables": mapping.census_variables,
                "confidence": mapping.confidence,
                "reasoning": mapping.reasoning,
                "statistical_method": mapping.statistical_method,
                "universe": mapping.universe,
                "coos_uri": mapping.coos_uri
            })
        
        with open(output_path, 'w') as f:
            json.dump(mappings_data, f, indent=2)
        
        print(f"Saved {len(mappings)} mappings to {output_path}")


# Example usage and testing
if __name__ == "__main__":
    
    # Test with a few sample concepts
    mapper = LLMConceptMapper()
    
    # Test concepts - we'll start with these and see how well it works
    test_concepts = [
        "MedianHouseholdIncome",
        "PovertyRate",
        "EducationalAttainment",
        "HousingTenure",
        "UnemploymentRate"
    ]
    
    print("Testing LLM concept mapping...")
    results = mapper.batch_map_concepts(test_concepts[:3])  # Start with 3 concepts
    
    # Display results
    for result in results:
        print(f"\nConcept: {result.concept}")
        print(f"Variables: {result.census_variables}")
        print(f"Confidence: {result.confidence}")
        print(f"Reasoning: {result.reasoning}")
    
    # Save results
    mapper.save_mappings(results, "test_mappings.json")
