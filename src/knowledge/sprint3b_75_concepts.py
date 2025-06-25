# sprint3b_75_concepts.py
"""
Sprint 3B: Scale to 75 core demographic concepts
Prove methodology works at serious scale
"""

import time
import json
import os
from datetime import datetime
from pathlib import Path
from llm_mapper import LLMConceptMapper, ConceptMapping

class Sprint3BScaleTest:
    """Test methodology at 75-concept scale"""
    
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
            "errors": [],
            "category_results": {}
        }
    
    def get_75_core_concepts(self) -> list:
        """Comprehensive list of 75 core demographic concepts"""
        
        concepts = []
        
        # Original 10 concepts that work perfectly
        proven_concepts = [
            {"name": "MedianHouseholdIncome", "definition": "The median income of all households", "category": "economics", "difficulty": "easy"},
            {"name": "PovertyRate", "definition": "Percentage of population below the federal poverty line", "category": "economics", "difficulty": "easy"},
            {"name": "EducationalAttainment", "definition": "Highest level of education completed by individuals", "category": "demographics", "difficulty": "medium"},
            {"name": "HousingTenure", "definition": "Whether housing units are owner-occupied or renter-occupied", "category": "housing", "difficulty": "easy"},
            {"name": "UnemploymentRate", "definition": "Percentage of labor force that is unemployed", "category": "economics", "difficulty": "medium"},
            {"name": "MedianAge", "definition": "The median age of the population", "category": "demographics", "difficulty": "easy"},
            {"name": "RaceEthnicity", "definition": "Racial and ethnic composition of the population", "category": "demographics", "difficulty": "medium"},
            {"name": "HouseholdSize", "definition": "Average number of people per household", "category": "demographics", "difficulty": "easy"},
            {"name": "MedianHomeValue", "definition": "Median value of owner-occupied housing units", "category": "housing", "difficulty": "easy"},
            {"name": "CommuteTime", "definition": "Time spent traveling to work for workers", "category": "transportation", "difficulty": "medium"}
        ]
        concepts.extend(proven_concepts)
        
        # Housing concepts (15 more)
        housing_concepts = [
            {"name": "RentBurden", "definition": "Percentage of income spent on rent for renter households", "category": "housing", "difficulty": "medium"},
            {"name": "HousingCostBurden", "definition": "Percentage of income spent on housing costs", "category": "housing", "difficulty": "medium"},
            {"name": "VacancyRate", "definition": "Percentage of housing units that are vacant", "category": "housing", "difficulty": "easy"},
            {"name": "HomeownershipRate", "definition": "Percentage of housing units that are owner-occupied", "category": "housing", "difficulty": "easy"},
            {"name": "MedianRent", "definition": "Median gross rent for renter-occupied housing units", "category": "housing", "difficulty": "easy"},
            {"name": "HousingUnits", "definition": "Total number of housing units in an area", "category": "housing", "difficulty": "easy"},
            {"name": "HouseholdCrowding", "definition": "Housing units with more than one person per room", "category": "housing", "difficulty": "medium"},
            {"name": "HousingAge", "definition": "Year housing units were built", "category": "housing", "difficulty": "medium"},
            {"name": "HousingBedrooms", "definition": "Number of bedrooms in housing units", "category": "housing", "difficulty": "easy"},
            {"name": "MobileHomes", "definition": "Housing units that are mobile homes or trailers", "category": "housing", "difficulty": "easy"},
            {"name": "MultifamilyHousing", "definition": "Housing units in buildings with multiple units", "category": "housing", "difficulty": "medium"},
            {"name": "SubsidizedHousing", "definition": "Housing units receiving government assistance", "category": "housing", "difficulty": "hard"},
            {"name": "HousingCondition", "definition": "Physical condition and amenities of housing units", "category": "housing", "difficulty": "medium"},
            {"name": "HousingCosts", "definition": "Monthly housing costs for homeowners and renters", "category": "housing", "difficulty": "easy"},
            {"name": "HouseholdMortgage", "definition": "Monthly mortgage payments and mortgage status", "category": "housing", "difficulty": "medium"}
        ]
        concepts.extend(housing_concepts)
        
        # Economics concepts (15 more)
        economics_concepts = [
            {"name": "MedianFamilyIncome", "definition": "Median income of family households", "category": "economics", "difficulty": "easy"},
            {"name": "PerCapitaIncome", "definition": "Average income per person in the population", "category": "economics", "difficulty": "easy"},
            {"name": "LaborForceParticipation", "definition": "Percentage of population in the labor force", "category": "economics", "difficulty": "medium"},
            {"name": "EmploymentByIndustry", "definition": "Distribution of employment across industry sectors", "category": "economics", "difficulty": "medium"},
            {"name": "EmploymentByOccupation", "definition": "Distribution of employment across occupation categories", "category": "economics", "difficulty": "medium"},
            {"name": "SelfEmployment", "definition": "Workers who are self-employed", "category": "economics", "difficulty": "medium"},
            {"name": "GovernmentWorkers", "definition": "Workers employed by government agencies", "category": "economics", "difficulty": "easy"},
            {"name": "MeanEarnings", "definition": "Average earnings by demographic characteristics", "category": "economics", "difficulty": "easy"},
            {"name": "WageAndSalaryIncome", "definition": "Income from wages and salaries", "category": "economics", "difficulty": "easy"},
            {"name": "BusinessIncome", "definition": "Income from business and self-employment", "category": "economics", "difficulty": "medium"},
            {"name": "RetirementIncome", "definition": "Income from pensions and retirement accounts", "category": "economics", "difficulty": "medium"},
            {"name": "SocialSecurityIncome", "definition": "Income from Social Security benefits", "category": "economics", "difficulty": "easy"},
            {"name": "PublicAssistanceIncome", "definition": "Income from government assistance programs", "category": "economics", "difficulty": "medium"},
            {"name": "WorkersPerHousehold", "definition": "Number of workers per household", "category": "economics", "difficulty": "easy"},
            {"name": "IncomeInequality", "definition": "Distribution of income across income brackets", "category": "economics", "difficulty": "hard"}
        ]
        concepts.extend(economics_concepts)
        
        # Demographics concepts (15 more)
        demographics_concepts = [
            {"name": "PopulationDensity", "definition": "Number of people per square mile", "category": "demographics", "difficulty": "easy"},
            {"name": "AgeDistribution", "definition": "Distribution of population across age groups", "category": "demographics", "difficulty": "easy"},
            {"name": "GenderComposition", "definition": "Distribution of population by sex", "category": "demographics", "difficulty": "easy"},
            {"name": "MaritalStatus", "definition": "Distribution of population by marital status", "category": "demographics", "difficulty": "easy"},
            {"name": "HouseholdType", "definition": "Types of households (family, non-family, etc.)", "category": "demographics", "difficulty": "easy"},
            {"name": "FamilyStructure", "definition": "Composition of family households", "category": "demographics", "difficulty": "medium"},
            {"name": "ChildrenInHouseholds", "definition": "Presence and number of children in households", "category": "demographics", "difficulty": "easy"},
            {"name": "SeniorPopulation", "definition": "Population aged 65 and older", "category": "demographics", "difficulty": "easy"},
            {"name": "VeteranStatus", "definition": "Population with military veteran status", "category": "demographics", "difficulty": "easy"},
            {"name": "DisabilityStatus", "definition": "Population with disabilities", "category": "demographics", "difficulty": "medium"},
            {"name": "LanguageSpoken", "definition": "Languages spoken at home", "category": "demographics", "difficulty": "medium"},
            {"name": "EnglishProficiency", "definition": "Ability to speak English", "category": "demographics", "difficulty": "medium"},
            {"name": "ForeignBorn", "definition": "Population born outside the United States", "category": "demographics", "difficulty": "easy"},
            {"name": "CitizenshipStatus", "definition": "Citizenship and naturalization status", "category": "demographics", "difficulty": "medium"},
            {"name": "YearOfEntry", "definition": "Year foreign-born population entered the US", "category": "demographics", "difficulty": "medium"}
        ]
        concepts.extend(demographics_concepts)
        
        # Health & Social concepts (10 more)
        health_social_concepts = [
            {"name": "HealthInsurance", "definition": "Health insurance coverage status", "category": "health", "difficulty": "medium"},
            {"name": "MedicareEnrollment", "definition": "Population enrolled in Medicare", "category": "health", "difficulty": "easy"},
            {"name": "MedicaidEnrollment", "definition": "Population enrolled in Medicaid", "category": "health", "difficulty": "easy"},
            {"name": "UninsuredRate", "definition": "Percentage of population without health insurance", "category": "health", "difficulty": "medium"},
            {"name": "ChildcareCosts", "definition": "Expenses for childcare services", "category": "social", "difficulty": "hard"},
            {"name": "SocialSecurityBenefits", "definition": "Recipients of Social Security benefits", "category": "social", "difficulty": "easy"},
            {"name": "SNAPParticipation", "definition": "Participation in food assistance programs", "category": "social", "difficulty": "medium"},
            {"name": "WICParticipation", "definition": "Participation in WIC nutrition program", "category": "social", "difficulty": "medium"},
            {"name": "HeadStartEnrollment", "definition": "Children enrolled in Head Start programs", "category": "social", "difficulty": "hard"},
            {"name": "SeniorServices", "definition": "Services and support for elderly population", "category": "social", "difficulty": "hard"}
        ]
        concepts.extend(health_social_concepts)
        
        # Transportation & Misc concepts (10 more)
        transport_misc_concepts = [
            {"name": "VehicleAvailability", "definition": "Number of vehicles available to households", "category": "transportation", "difficulty": "easy"},
            {"name": "PublicTransitUse", "definition": "Use of public transportation for commuting", "category": "transportation", "difficulty": "medium"},
            {"name": "WalkingToWork", "definition": "Workers who walk to work", "category": "transportation", "difficulty": "easy"},
            {"name": "WorkFromHome", "definition": "Workers who work from home", "category": "transportation", "difficulty": "easy"},
            {"name": "LongCommute", "definition": "Workers with commutes over 60 minutes", "category": "transportation", "difficulty": "medium"},
            {"name": "UrbanRuralClassification", "definition": "Classification of areas as urban or rural", "category": "geography", "difficulty": "medium"},
            {"name": "PopulationGrowth", "definition": "Change in population over time", "category": "geography", "difficulty": "hard"},
            {"name": "MigrationPatterns", "definition": "Population movement between areas", "category": "geography", "difficulty": "hard"},
            {"name": "SchoolEnrollment", "definition": "Enrollment in educational institutions", "category": "education", "difficulty": "medium"},
            {"name": "InternetAccess", "definition": "Household access to internet services", "category": "technology", "difficulty": "medium"}
        ]
        concepts.extend(transport_misc_concepts)
        
        print(f"Generated {len(concepts)} total concepts:")
        print(f"  • Proven working: {len(proven_concepts)}")
        print(f"  • Housing: {len(housing_concepts)}")
        print(f"  • Economics: {len(economics_concepts)}")
        print(f"  • Demographics: {len(demographics_concepts)}")
        print(f"  • Health/Social: {len(health_social_concepts)}")
        print(f"  • Transport/Misc: {len(transport_misc_concepts)}")
        
        return concepts
    
    def run_75_concept_test(self, delay_seconds: float = 0.8) -> dict:
        """Run the massive 75-concept proof of scale"""
        
        print("🚀 Starting 75-Concept PROOF OF SCALE")
        print("=" * 70)
        
        self.results["start_time"] = datetime.now().isoformat()
        start_time = time.time()
        
        # Get all 75 concepts
        all_concepts = self.get_75_core_concepts()
        
        print(f"\n⚡ Processing {len(all_concepts)} concepts with {delay_seconds}s delay...")
        print(f"📊 Estimated total time: {len(all_concepts) * (delay_seconds + 7):.0f} seconds (~{len(all_concepts) * (delay_seconds + 7)/60:.1f} minutes)")
        print(f"💰 Estimated cost: ${len(all_concepts) * 0.068:.2f}")
        
        # Process each concept
        successful_mappings = []
        failed_mappings = []
        category_stats = {}
        
        for i, concept_info in enumerate(all_concepts, 1):
            concept_name = concept_info["name"]
            concept_definition = concept_info["definition"]
            category = concept_info["category"]
            difficulty = concept_info["difficulty"]
            
            print(f"\n📊 [{i:2d}/{len(all_concepts)}] {concept_name} ({category}, {difficulty})")
            
            # Track category stats
            if category not in category_stats:
                category_stats[category] = {"total": 0, "successful": 0, "failed": 0}
            category_stats[category]["total"] += 1
            
            try:
                # Time individual mapping
                mapping_start = time.time()
                
                result = self.mapper.map_concept_to_variables(
                    concept=concept_name,
                    concept_definition=concept_definition
                )
                
                mapping_duration = time.time() - mapping_start
                
                # Add metadata
                result.category = category
                result.difficulty = difficulty
                result.mapping_duration = mapping_duration
                
                if result.confidence > 0:
                    successful_mappings.append(result)
                    category_stats[category]["successful"] += 1
                    print(f"   ✅ SUCCESS! Confidence: {result.confidence:.2f}")
                    print(f"   📋 Variables: {result.census_variables}")
                    if len(result.reasoning) > 80:
                        print(f"   💭 Reasoning: {result.reasoning[:80]}...")
                    else:
                        print(f"   💭 Reasoning: {result.reasoning}")
                else:
                    failed_mappings.append(result)
                    category_stats[category]["failed"] += 1
                    print(f"   ❌ Failed: {result.reasoning[:80]}...")
                
                # Store result
                self.results["mappings"].append({
                    "concept": concept_name,
                    "definition": concept_definition,
                    "category": category,
                    "difficulty": difficulty,
                    "census_variables": result.census_variables,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "statistical_method": getattr(result, 'statistical_method', None),
                    "universe": getattr(result, 'universe', None),
                    "mapping_duration": mapping_duration,
                    "success": result.confidence > 0
                })
                
                # Rate limiting
                if delay_seconds > 0 and i < len(all_concepts):
                    time.sleep(delay_seconds)
                    
            except Exception as e:
                error_msg = f"Error processing {concept_name}: {str(e)}"
                print(f"   ❌ Error: {error_msg}")
                category_stats[category]["failed"] += 1
                
                self.results["errors"].append({
                    "concept": concept_name,
                    "category": category,
                    "error": error_msg
                })
        
        # Calculate final metrics
        end_time = time.time()
        total_duration = end_time - start_time
        
        self.results["end_time"] = datetime.now().isoformat()
        self.results["total_duration_seconds"] = total_duration
        self.results["concepts_processed"] = len(all_concepts)
        self.results["successful_mappings"] = len(successful_mappings)
        self.results["category_results"] = category_stats
        
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
        
        self._print_comprehensive_summary()
        return self.results
    
    def _print_comprehensive_summary(self):
        """Print detailed summary of 75-concept results"""
        
        print("\n" + "=" * 70)
        print("📊 75-CONCEPT PROOF OF SCALE SUMMARY")
        print("=" * 70)
        
        # Overall stats
        total_concepts = self.results["concepts_processed"]
        successful = self.results["successful_mappings"]
        success_rate = (successful / total_concepts) * 100 if total_concepts > 0 else 0
        
        print(f"📈 Overall Results:")
        print(f"   • Total concepts processed: {total_concepts}")
        print(f"   • Successful mappings: {successful}")
        print(f"   • Success rate: {success_rate:.1f}%")
        print(f"   • Average confidence: {self.results['average_confidence']:.2f}")
        print(f"   • Total duration: {self.results['total_duration_seconds']:.1f}s ({self.results['total_duration_seconds']/60:.1f} minutes)")
        
        # Performance metrics
        if self.results["performance_metrics"]:
            metrics = self.results["performance_metrics"]
            print(f"\n⏱️  Performance Metrics:")
            print(f"   • Average mapping time: {metrics['average_mapping_time']:.2f}s")
            print(f"   • Fastest mapping: {metrics['min_mapping_time']:.2f}s")
            print(f"   • Slowest mapping: {metrics['max_mapping_time']:.2f}s")
            print(f"   • Total LLM time: {metrics['total_llm_time']:.1f}s")
        
        # Success by category
        print(f"\n🎯 Success by Category:")
        for category, stats in self.results["category_results"].items():
            total = stats["total"]
            success = stats["successful"]
            rate = (success / total) * 100 if total > 0 else 0
            print(f"   • {category.capitalize()}: {success}/{total} ({rate:.1f}%)")
        
        # Success by difficulty
        difficulty_stats = {}
        for mapping in self.results["mappings"]:
            diff = mapping["difficulty"]
            if diff not in difficulty_stats:
                difficulty_stats[diff] = {"total": 0, "successful": 0}
            difficulty_stats[diff]["total"] += 1
            if mapping["success"]:
                difficulty_stats[diff]["successful"] += 1
        
        print(f"\n🎯 Success by Difficulty:")
        for difficulty in ["easy", "medium", "hard"]:
            if difficulty in difficulty_stats:
                stats = difficulty_stats[difficulty]
                total = stats["total"]
                success = stats["successful"]
                rate = (success / total) * 100 if total > 0 else 0
                print(f"   • {difficulty.capitalize()}: {success}/{total} ({rate:.1f}%)")
        
        # High confidence mappings
        high_confidence = sum(1 for m in self.results["mappings"] if m["confidence"] >= 0.85)
        print(f"\n🔥 High Confidence Mappings (≥0.85): {high_confidence}/{total_concepts} ({high_confidence/total_concepts*100:.1f}%)")
        
        # Show some examples of high confidence successes
        high_conf_examples = [m for m in self.results["mappings"] if m["confidence"] >= 0.90][:10]
        if high_conf_examples:
            print(f"\n✨ Top High-Confidence Examples:")
            for mapping in high_conf_examples:
                print(f"   • {mapping['concept']}: {mapping['confidence']:.2f} → {mapping['census_variables']}")
        
        # Show failures for analysis
        failures = [m for m in self.results["mappings"] if not m["success"]]
        if failures:
            print(f"\n❌ Failed Mappings ({len(failures)}):")
            for mapping in failures[:5]:  # Show first 5 failures
                print(f"   • {mapping['concept']} ({mapping['category']}): {mapping['reasoning'][:60]}...")
            if len(failures) > 5:
                print(f"   ... and {len(failures) - 5} more")
        
        # Errors
        if self.results["errors"]:
            print(f"\n💥 Errors ({len(self.results['errors'])}):")
            for error in self.results["errors"]:
                print(f"   • {error['concept']}: {error['error']}")
        
        # Final assessment
        print(f"\n🎯 SCALE TEST ASSESSMENT:")
        if success_rate >= 85:
            print("✅ EXCELLENT! Methodology scales beautifully")
            print("   Ready for production deployment at 100+ concept scale")
        elif success_rate >= 70:
            print("⚡ GOOD! Methodology mostly scales well")
            print("   Some refinement needed but foundation is solid")
        else:
            print("🔧 NEEDS WORK before large-scale deployment")
            print("   Systematic issues need addressing")
        
        print(f"   Success rate: {success_rate:.1f}%")
        print(f"   Average confidence: {self.results['average_confidence']:.2f}")
        print(f"   High confidence rate: {high_confidence/total_concepts*100:.1f}%")
    
    def save_results(self, output_file: str = None):
        """Save comprehensive results to JSON file"""
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"sprint3b_75_concepts_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        return output_file

def main():
    """Run the 75-concept proof of scale"""
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        print("   Set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        return False
    
    try:
        print("🤘 SPRINT 3B: 75-CONCEPT PROOF OF SCALE")
        print("Time to prove this methodology REALLY scales!")
        print()
        
        # Confirm with user
        response = input("Ready to process 75 concepts? This will take ~10-15 minutes and cost ~$5. (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Cancelled. Run again when ready!")
            return False
        
        # Run the scale test
        runner = Sprint3BScaleTest(api_key=api_key)
        results = runner.run_75_concept_test(delay_seconds=0.8)
        
        # Save results
        output_file = runner.save_results()
        
        # Final assessment
        success_rate = (results["successful_mappings"] / results["concepts_processed"]) * 100
        
        print(f"\n🎯 FINAL VERDICT:")
        if success_rate >= 85:
            print("🎉 METHODOLOGY PROVEN AT SCALE!")
            print("   Ready for Thread 2 to push to 100+ concepts")
        elif success_rate >= 70:
            print("⚡ STRONG FOUNDATION CONFIRMED")
            print("   Some refinement needed but ready to proceed")
        else:
            print("🔧 SCALE ISSUES IDENTIFIED")
            print("   Need systematic improvements before scaling further")
        
        print(f"\nSuccess rate: {success_rate:.1f}%")
        print(f"This thread's work: COMPLETE! 🚀")
        
        return success_rate >= 70
        
    except Exception as e:
        print(f"❌ Scale test failed: {e}")
        return False

if __name__ == "__main__":
    main()
