# test_llm_mapper.py
"""
Test script to validate LLM concept mapper setup
Run this to make sure everything is working before processing larger batches
"""

import os
import sys
from pathlib import Path

# Add current directory to path so we can import llm_mapper
sys.path.append('.')

from llm_mapper import LLMConceptMapper, ConceptMapping

def test_basic_setup():
    """Test that we can load ontologies and Census variables"""
    
    print("🧪 Testing basic setup...")
    
    try:
        mapper = LLMConceptMapper()
        
        print(f"✅ COOS concepts loaded: {len(mapper.coos_concepts)}")
        print(f"✅ Census variables loaded: {len(mapper.census_variables)}")
        
        # Show a few examples
        print("\nSample COOS concepts:")
        for i, concept in enumerate(list(mapper.coos_concepts.keys())[:5]):
            print(f"  - {concept}")
        
        print("\nSample Census variables:")
        for i, (var_id, var_info) in enumerate(list(mapper.census_variables.items())[:5]):
            print(f"  - {var_id}: {var_info['label'][:60]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False

def test_candidate_finding():
    """Test finding candidate variables for a concept"""
    
    print("\n🔍 Testing candidate variable finding...")
    
    try:
        mapper = LLMConceptMapper()
        
        # Test with a clear concept
        test_concept = "income"
        test_definition = "household income statistics"
        
        candidates = mapper._find_candidate_variables(test_concept, test_definition)
        
        print(f"✅ Found {len(candidates)} candidates for '{test_concept}'")
        print("Top 5 candidates:")
        for candidate in candidates[:5]:
            print(f"  - {candidate['variable_id']}: {candidate['label'][:50]}... (score: {candidate['score']})")
        
        return len(candidates) > 0
        
    except Exception as e:
        print(f"❌ Candidate finding failed: {e}")
        return False

def test_single_mapping():
    """Test mapping a single concept (requires OpenAI API key)"""
    
    print("\n🤖 Testing single concept mapping...")
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("⚠️  No OPENAI_API_KEY found - skipping LLM test")
        print("   Set OPENAI_API_KEY environment variable to test LLM mapping")
        return True
    
    try:
        mapper = LLMConceptMapper(api_key=api_key)
        
        # Test with a simple concept
        result = mapper.map_concept_to_variables(
            concept="MedianHouseholdIncome",
            concept_definition="The median income of households"
        )
        
        print(f"✅ Mapped concept: {result.concept}")
        print(f"   Variables: {result.census_variables}")
        print(f"   Confidence: {result.confidence}")
        print(f"   Reasoning: {result.reasoning[:100]}...")
        
        return result.confidence > 0
        
    except Exception as e:
        print(f"❌ LLM mapping failed: {e}")
        return False

def main():
    """Run all tests"""
    
    print("🚀 Testing LLM Concept Mapper Setup")
    print("=" * 50)
    
    tests = [
        test_basic_setup,
        test_candidate_finding,
        test_single_mapping
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    
    if all(results):
        print("✅ All tests passed! Ready for Step 3.")
    else:
        print("❌ Some tests failed. Check setup before proceeding.")
        
    print(f"   Passed: {sum(results)}/{len(results)}")

if __name__ == "__main__":
    main()
