# debug_poverty_candidates.py
"""
Debug what candidates are being found for poverty rate
"""

from llm_mapper import LLMConceptMapper

def debug_poverty_candidates():
    """See what candidates are actually being found"""
    
    mapper = LLMConceptMapper()
    
    print("🔍 Debugging Poverty Rate Candidate Selection")
    print("=" * 50)
    
    candidates = mapper._find_candidate_variables(
        concept="PovertyRate",
        definition="Percentage of population below the federal poverty line"
    )
    
    print(f"Found {len(candidates)} candidates:")
    print()
    
    for i, candidate in enumerate(candidates):
        var_id = candidate['variable_id']
        score = candidate['score']
        label = candidate['label']
        concept = candidate.get('concept', '')
        
        print(f"{i+1:2d}. {var_id} (score: {score})")
        print(f"    Label: {label}")
        print(f"    Concept: {concept}")
        print()
        
        if i >= 14:  # Show top 15
            break
    
    # Look specifically for B17001 variables
    b17001_vars = [c for c in candidates if 'B17001' in c['variable_id']]
    print(f"\nB17001 variables found: {len(b17001_vars)}")
    
    for var in b17001_vars[:5]:
        print(f"  - {var['variable_id']}: {var['label']}")

if __name__ == "__main__":
    debug_poverty_candidates()
