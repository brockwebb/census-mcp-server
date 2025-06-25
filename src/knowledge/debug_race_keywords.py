# debug_race_keywords.py
"""
Debug why race/ethnicity keywords aren't working
"""

from llm_mapper import LLMConceptMapper

def debug_race_keywords():
    """Debug the keyword matching for race/ethnicity"""
    
    mapper = LLMConceptMapper()
    
    concept = "RaceEthnicity"
    definition = "Racial and ethnic composition of the population"
    
    print("🔍 Debugging Race/Ethnicity Keyword Matching")
    print("=" * 50)
    
    # Check what keyword lookup is happening
    concept_key = concept.lower().replace(" ", "")
    print(f"Concept key: '{concept_key}'")
    
    # Look for specific race variables in the full dataset
    print(f"\nSearching for B02001 and B03002 variables...")
    
    race_vars = []
    for var_id, var_info in mapper.census_variables.items():
        if var_id.startswith('B02001') or var_id.startswith('B03002'):
            race_vars.append((var_id, var_info.get('label', ''), var_info.get('concept', '')))
    
    print(f"Found {len(race_vars)} race/ethnicity variables:")
    for var_id, label, concept in race_vars[:10]:
        print(f"  {var_id}: {label[:50]}...")
        print(f"    Concept: {concept}")
    
    if not race_vars:
        print("❌ No B02001/B03002 variables found in dataset!")
    else:
        print("\n✅ Race variables exist, keyword matching must be the issue")

if __name__ == "__main__":
    debug_race_keywords()
