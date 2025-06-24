# step3_proof_of_concept.py
"""
Step 3: Process 10 concepts through automated pipeline
Measure performance and generate validated mappings
"""

import time
import json
import os
from datetime import datetime
from pathlib import Path
from llm_mapper import LLMConceptMapper, ConceptMapping

class ProofOfConceptRunner:
    """Run and measure the 10-concept proof of concept"""
    
    def __init__(self, api_key: str = None):
        self.mapper = LLMConceptMapper(api_key=api_key)
        self.results = {
            "start_time": None,
            "end_time": None,
            "total_duration_seconds": 0,
            "concepts_processed": 0,
            "successful_mappings": 0,
            "average_confidence": 0,
            "mappings": [],
            "performance_metrics": {},
            "errors": []
        }
    
    def select_test_concepts(self) -> list:
        """Select 10 diverse test concepts for proof of concept"""
        
        # Mix of core demographic concepts that should map well to Census
        test_concepts = [
            {
                "name": "MedianHouseholdIncome",
                "definition": "The median income of all households in a geographic area",
                "expected_difficulty": "easy"
            },
            {
                "name": "PovertyRate", 
                "definition": "Percentage of population below the federal poverty line",
                "expected_difficulty": "easy"
            },
            {
                "name": "EducationalAttainment",
                "definition": "Highest level of education completed by individuals",
                "expected_difficulty": "medium"
            },
            {
                "name": "HousingTenure",
                "definition": "Whether housing units are owner-occupied or renter-occupied",
                "expected_difficulty": "easy"
            },
            {
                "name": "UnemploymentRate",
                "definition": "Percentage of labor force that is unemployed",
                "expected_difficulty": "medium"
            },
            {
                "name": "MedianAge",
                "definition": "The median age of the population in a geographic area",
                "expected_difficulty": "easy"
            },
            {
                "name": "RaceEthnicity",
                "definition": "Racial and ethnic composition of the population",
                "expected_difficulty": "medium"
            },
            {
                "name": "HouseholdSize",
                "definition": "Average number of people per household",
                "expected_difficulty": "easy"
            },
            {
                "name": "MedianHomeValue",
                "definition": "Median value of owner-occupied housing units",
                "expected_difficulty": "easy"
            },
            {
                "name": "CommuteTime",
                "definition": "Time spent traveling to work for workers",
                "expected_difficulty": "medium"
            }
        ]
        
        print(f"Selected {len(test_concepts)} test concepts:")
        for i, concept in enumerate(test_concepts, 1):
            print(f"  {i}. {concept['name']} ({concept['expected_difficulty']})")
        
        return test_concepts
    
    def run_proof_of_concept(self, delay_seconds: float = 1.0) -> dict:
        """Run the full 10-concept proof of concept"""
        
        print("🚀 Starting 10-Concept Proof of Concept")
        print("=" * 60)
        
        self.results["start_time"] = datetime.now().isoformat()
        start_time = time.time()
        
        # Select test concepts
        test_concepts = self.select_test_concepts()
        
        print(f"\n⏱️  Processing {len(test_concepts)} concepts with {delay_seconds}s delay...")
        
        # Process each concept
        successful_mappings = []
        failed_mappings = []
        
        for i, concept_info in enumerate(test_concepts, 1):
            concept_name = concept_info["name"]
            concept_definition = concept_info["definition"]
            
            print(f"\n📊 [{i}/{len(test_concepts)}] Processing: {concept_name}")
            
            try:
                # Time individual mapping
                mapping_start = time.time()
                
                result = self.mapper.map_concept_to_variables(
                    concept=concept_name,
                    concept_definition=concept_definition
                )
                
                mapping_duration = time.time() - mapping_start
                
                # Add metadata
                result.expected_difficulty = concept_info["expected_difficulty"]
                result.mapping_duration = mapping_duration
                
                if result.confidence > 0:
                    successful_mappings.append(result)
                    print(f"   ✅ Success! Confidence: {result.confidence:.2f}")
                    print(f"   📋 Variables: {result.census_variables}")
                    print(f"   ⏱️  Duration: {mapping_duration:.2f}s")
                else:
                    failed_mappings.append(result)
                    print(f"   ❌ Failed: {result.reasoning}")
                
                # Store result
                self.results["mappings"].append({
                    "concept": concept_name,
                    "definition": concept_definition,
                    "expected_difficulty": concept_info["expected_difficulty"],
                    "census_variables": result.census_variables,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "statistical_method": result.statistical_method,
                    "universe": result.universe,
                    "mapping_duration": mapping_duration,
                    "success": result.confidence > 0
                })
                
                # Rate limiting
                if delay_seconds > 0 and i < len(test_concepts):
                    time.sleep(delay_seconds)
                    
            except Exception as e:
                error_msg = f"Error processing {concept_name}: {str(e)}"
                print(f"   ❌ Error: {error_msg}")
                
                self.results["errors"].append({
                    "concept": concept_name,
                    "error": error_msg
                })
        
        # Calculate final metrics
        end_time = time.time()
        total_duration = end_time - start_time
        
        self.results["end_time"] = datetime.now().isoformat()
        self.results["total_duration_seconds"] = total_duration
        self.results["concepts_processed"] = len(test_concepts)
        self.results["successful_mappings"] = len(successful_mappings)
        
        if successful_mappings:
            avg_confidence = sum(m.confidence for m in successful_mappings) / len(successful_mappings)
            self.results["average_confidence"] = avg_confidence
        
        # Performance metrics
        mapping_durations = [m["mapping_duration"] for m in self.results["mappings"] if m["success"]]
        if mapping_durations:
            self.results["performance_metrics"] = {
                "average_mapping_time": sum(mapping_durations) / len(mapping_durations),
                "min_mapping_time": min(mapping_durations),
                "max_mapping_time": max(mapping_durations),
                "total_llm_time": sum(mapping_durations)
            }
        
        self._print_summary()
        return self.results
    
    def _print_summary(self):
        """Print detailed summary of results"""
        
        print("\n" + "=" * 60)
        print("📊 PROOF OF CONCEPT SUMMARY")
        print("=" * 60)
        
        # Overall stats
        total_concepts = self.results["concepts_processed"]
        successful = self.results["successful_mappings"]
        success_rate = (successful / total_concepts) * 100 if total_concepts > 0 else 0
        
        print(f"📈 Overall Results:")
        print(f"   • Total concepts processed: {total_concepts}")
        print(f"   • Successful mappings: {successful}")
        print(f"   • Success rate: {success_rate:.1f}%")
        print(f"   • Average confidence: {self.results['average_confidence']:.2f}")
        print(f"   • Total duration: {self.results['total_duration_seconds']:.1f}s")
        
        # Performance metrics
        if self.results["performance_metrics"]:
            metrics = self.results["performance_metrics"]
            print(f"\n⏱️  Performance Metrics:")
            print(f"   • Average mapping time: {metrics['average_mapping_time']:.2f}s")
            print(f"   • Fastest mapping: {metrics['min_mapping_time']:.2f}s")
            print(f"   • Slowest mapping: {metrics['max_mapping_time']:.2f}s")
            print(f"   • Total LLM time: {metrics['total_llm_time']:.1f}s")
        
        # Success by difficulty
        easy_success = sum(1 for m in self.results["mappings"] if m["expected_difficulty"] == "easy" and m["success"])
        medium_success = sum(1 for m in self.results["mappings"] if m["expected_difficulty"] == "medium" and m["success"])
        easy_total = sum(1 for m in self.results["mappings"] if m["expected_difficulty"] == "easy")
        medium_total = sum(1 for m in self.results["mappings"] if m["expected_difficulty"] == "medium")
        
        print(f"\n🎯 Success by Difficulty:")
        if easy_total > 0:
            print(f"   • Easy concepts: {easy_success}/{easy_total} ({easy_success/easy_total*100:.1f}%)")
        if medium_total > 0:
            print(f"   • Medium concepts: {medium_success}/{medium_total} ({medium_success/medium_total*100:.1f}%)")
        
        # High confidence mappings
        high_confidence = sum(1 for m in self.results["mappings"] if m["confidence"] >= 0.85)
        print(f"\n🔥 High Confidence Mappings (≥0.85): {high_confidence}/{total_concepts}")
        
        for mapping in self.results["mappings"]:
            if mapping["confidence"] >= 0.85:
                print(f"   • {mapping['concept']}: {mapping['confidence']:.2f} → {mapping['census_variables']}")
        
        # Errors
        if self.results["errors"]:
            print(f"\n❌ Errors ({len(self.results['errors'])}):")
            for error in self.results["errors"]:
                print(f"   • {error['concept']}: {error['error']}")
    
    def save_results(self, output_file: str = None):
        """Save results to JSON file"""
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"step3_proof_of_concept_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        return output_file

def main():
    """Run the Step 3 proof of concept"""
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        print("   Set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        return False
    
    try:
        # Run proof of concept
        runner = ProofOfConceptRunner(api_key=api_key)
        results = runner.run_proof_of_concept(delay_seconds=1.0)
        
        # Save results
        output_file = runner.save_results()
        
        # Determine if we're ready for next step
        success_rate = (results["successful_mappings"] / results["concepts_processed"]) * 100
        avg_confidence = results["average_confidence"]
        
        print(f"\n🎯 STEP 3 ASSESSMENT:")
        if success_rate >= 70 and avg_confidence >= 0.75:
            print("✅ EXCELLENT! Ready for Step 4 (50 concepts)")
            print(f"   Success rate: {success_rate:.1f}% (target: ≥70%)")
            print(f"   Avg confidence: {avg_confidence:.2f} (target: ≥0.75)")
        elif success_rate >= 50:
            print("⚠️  GOOD but needs refinement before scaling")
            print(f"   Success rate: {success_rate:.1f}% (target: ≥70%)")
            print(f"   Avg confidence: {avg_confidence:.2f} (target: ≥0.75)")
            print("   Consider improving prompts or candidate selection")
        else:
            print("❌ NEEDS WORK before proceeding")
            print(f"   Success rate: {success_rate:.1f}% (too low)")
            print("   Review failed mappings and improve pipeline")
        
        return success_rate >= 70
        
    except Exception as e:
        print(f"❌ Proof of concept failed: {e}")
        return False

if __name__ == "__main__":
    main()
