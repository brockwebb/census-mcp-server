# test_improved_candidates.py
"""
Quick test to see if improved candidate selection works better
"""

from llm_mapper import LLMConceptMapper

def test_candidate_improvements():
    """Test improved candidate selection for problematic concepts"""
    
    mapper = LLMConceptMapper()
    
    test_cases = [
        {
            "concept": "MedianHouseholdIncome",
            "definition": "The median income of all households in a geographic area",
            "expected_vars": ["B19013"]
        },
        {
            "concept": "PovertyRate",
            "definition": "Percentage of population below the federal poverty line", 
            "expected_vars": ["B17001"]
        },
        {
            "concept": "EducationalAttainment",
            "definition": "Highest level of education completed by individuals",
            "expected_vars": ["B15003", "B15002"]
        }
    ]
    
    print("🔍 Testing Improved Candidate Selection")
    print("=" * 50)
    
    for test in test_cases:
        print(f"\n📊 Testing: {test['concept']}")
        
        candidates = mapper._find_candidate_variables(
            test["concept"], 
            test["definition"]
        )
        
        print(f"   Found {len(candidates)} candidates:")
        
        # Show top 5 candidates
        for i, candidate in enumerate(candidates[:5]):
            var_id = candidate['variable_id']
            score = candidate['score']
            label = candidate['label'][:60] + "..."
            
            # Check if any expected variable patterns are found
            found_expected = any(exp in var_id for exp in test["expected_vars"])
            marker = "✅" if found_expected else "  "
            
            print(f"   {marker} {i+1}. {var_id}: {label} (score: {score})")
        
        # Summary
        found_any = any(
            any(exp in c['variable_id'] for exp in test["expected_vars"]) 
            for c in candidates[:10]
        )
        
        if found_any:
            print(f"   ✅ SUCCESS: Found expected variable patterns in top 10")
        else:
            print(f"   ❌ ISSUE: No expected patterns found in top 10")

if __name__ == "__main__":
    test_candidate_improvements()
