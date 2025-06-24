# test_poverty_fix.py
"""
Test the poverty rate fix specifically
"""

import os
from llm_mapper import LLMConceptMapper

def test_poverty_fix():
    """Test if poverty rate now maps correctly"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Need OPENAI_API_KEY")
        return
    
    mapper = LLMConceptMapper(api_key=api_key)
    
    print("🧪 Testing Poverty Rate Fix")
    print("=" * 40)
    
    # Test poverty rate with enhanced prompting
    print("\n📊 Testing: PovertyRate")
    
    result = mapper.map_concept_to_variables(
        concept="PovertyRate",
        concept_definition="Percentage of population below the federal poverty line"
    )
    
    print(f"Confidence: {result.confidence}")
    print(f"Variables: {result.census_variables}")
    print(f"Statistical Method: {result.statistical_method}")
    print(f"Universe: {result.universe}")
    print(f"Calculation Note: {result.calculation_note}")
    print(f"Reasoning: {result.reasoning}")
    
    # Check if we got rate-appropriate variables
    if result.confidence > 0:
        if len(result.census_variables) >= 2:
            print("\n✅ SUCCESS: Got multiple variables (likely numerator/denominator)")
        elif "rate" in str(result.statistical_method).lower():
            print("\n✅ SUCCESS: Recognized as rate calculation")
        else:
            print("\n⚠️  PARTIAL: Mapped but may not understand rate calculation")
    else:
        print("\n❌ STILL FAILING")
    
    return result.confidence > 0.7

if __name__ == "__main__":
    success = test_poverty_fix()
    if success:
        print("\n🎉 Poverty rate issue fixed! Ready to proceed.")
    else:
        print("\n🔧 Still needs more work.")
