# quick_retest.py
"""
Quick retest of the 3 failed concepts with improved candidate selection
"""

import os
from llm_mapper import LLMConceptMapper

def quick_retest():
    """Test the 3 concepts that failed in Step 3"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Need OPENAI_API_KEY to test LLM mapping")
        return
    
    mapper = LLMConceptMapper(api_key=api_key)
    
    failed_concepts = [
        {
            "name": "MedianHouseholdIncome",
            "definition": "The median income of all households in a geographic area"
        },
        {
            "name": "PovertyRate", 
            "definition": "Percentage of population below the federal poverty line"
        },
        {
            "name": "EducationalAttainment",
            "definition": "Highest level of education completed by individuals"
        }
    ]
    
    print("🔄 Quick Retest of Failed Concepts")
    print("=" * 50)
    
    successful = 0
    
    for i, concept_info in enumerate(failed_concepts, 1):
        concept = concept_info["name"]
        definition = concept_info["definition"]
        
        print(f"\n📊 [{i}/3] Testing: {concept}")
        
        try:
            result = mapper.map_concept_to_variables(concept, definition)
            
            if result.confidence > 0:
                successful += 1
                print(f"   ✅ SUCCESS! Confidence: {result.confidence:.2f}")
                print(f"   📋 Variables: {result.census_variables}")
                print(f"   💭 Reasoning: {result.reasoning[:80]}...")
            else:
                print(f"   ❌ Still failing: {result.reasoning[:80]}...")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n" + "=" * 50)
    print(f"📊 RETEST SUMMARY: {successful}/3 concepts now working")
    
    if successful == 3:
        print("🎉 EXCELLENT! All problem concepts fixed")
        print("   Ready to rerun full Step 3 proof of concept")
    elif successful >= 2:
        print("⚡ GOOD progress! Most concepts working")
        print("   Consider rerunning Step 3 or proceeding")
    else:
        print("🔧 Still needs work on LLM prompting")

if __name__ == "__main__":
    quick_retest()
