# test_race_ethnicity_fix.py
"""
Quick test of the RaceEthnicity fix
"""

import os
from llm_mapper import LLMConceptMapper

def test_race_ethnicity_fix():
    """Test if RaceEthnicity now maps correctly"""
    
    # First check candidates
    mapper = LLMConceptMapper()
    
    print("🔍 Testing RaceEthnicity Candidate Selection")
    print("=" * 50)
    
    candidates = mapper._find_candidate_variables(
        concept="RaceEthnicity",
        definition="Racial and ethnic composition of the population"
    )
    
    print(f"Found {len(candidates)} candidates:")
    for i, candidate in enumerate(candidates[:5]):
        var_id = candidate['variable_id']
        score = candidate['score']
        label = candidate['label'][:60] + "..."
        
        # Check for B02001 or B03002
        found_expected = any(table in var_id for table in ['B02001', 'B03002'])
        marker = "✅" if found_expected else "  "
        
        print(f"   {marker} {i+1}. {var_id}: {label} (score: {score})")
    
    # Test LLM mapping if API key available
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        print(f"\n🤖 Testing LLM Mapping")
        print("-" * 30)
        
        mapper_with_api = LLMConceptMapper(api_key=api_key)
        result = mapper_with_api.map_concept_to_variables(
            concept="RaceEthnicity",
            concept_definition="Racial and ethnic composition of the population"
        )
        
        print(f"Confidence: {result.confidence}")
        print(f"Variables: {result.census_variables}")
        print(f"Reasoning: {result.reasoning[:100]}...")
        
        if result.confidence >= 0.8:
            print("\n🎉 SUCCESS! RaceEthnicity fixed!")
            return True
        else:
            print("\n⚠️  Still needs work")
            return False
    else:
        print("\n⚠️  No OPENAI_API_KEY - can't test LLM mapping")
        # Check if we at least got good candidates
        b02001_found = any('B02001' in c['variable_id'] for c in candidates[:10])
        b03002_found = any('B03002' in c['variable_id'] for c in candidates[:10])
        
        if b02001_found and b03002_found:
            print("✅ Good candidates found - likely will work!")
            return True
        else:
            print("❌ Still not finding right race/ethnicity tables")
            return False

if __name__ == "__main__":
    success = test_race_ethnicity_fix()
    if success:
        print("\n🎯 Ready to rerun full proof of concept for 10/10 success!")
    else:
        print("\n🔧 Need more keyword refinement")
