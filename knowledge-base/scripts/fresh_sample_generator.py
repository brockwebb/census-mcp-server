#!/usr/bin/env python3
"""
Generate a fresh 100-variable sample for domain specialist testing
Excludes variables already processed in the 999-variable Claude/GPT run
"""

import json
import pandas as pd
import random
from typing import Dict, List, Set
from pathlib import Path

def load_existing_processed_variables(enrichment_file: str) -> Set[str]:
    """Load variables that were already processed in previous runs"""
    
    try:
        with open(enrichment_file, 'r') as f:
            enrichment_data = json.load(f)
        
        # Extract variable IDs from enrichment data
        if 'enriched_variables' in enrichment_data:
            processed_vars = set(enrichment_data['enriched_variables'].keys())
        else:
            # Alternative structure - check for variable_id fields
            processed_vars = set()
            for var_id, data in enrichment_data.items():
                if isinstance(data, dict) and 'variable_id' in data:
                    processed_vars.add(data['variable_id'])
                else:
                    processed_vars.add(var_id)
        
        print(f"📊 Found {len(processed_vars)} already processed variables")
        return processed_vars
        
    except Exception as e:
        print(f"⚠️ Could not load existing variables: {e}")
        return set()

def load_full_variable_corpus(variables_file: str) -> Dict:
    """Load the complete 28K+ variable corpus from CSV"""
    
    try:
        df = pd.read_csv(variables_file)
        
        # Convert to dict keyed by variable_id
        variables_data = {}
        for _, row in df.iterrows():
            var_id = row['variable_id']
            variables_data[var_id] = {
                'label': row['label'],
                'concept': row['concept'],
                'predicateType': row['predicateType'],
                'group': row['group'],
                'survey': row['survey'],
                'complexity': row['complexity'],
                'table_family': row.get('table_family', var_id[:3] if len(var_id) >= 3 else 'OTHER')
            }
        
        print(f"📊 Loaded {len(variables_data)} total variables from corpus")
        return variables_data
        
    except Exception as e:
        print(f"❌ Error loading variable corpus: {e}")
        return {}

def categorize_variables_by_table_family(variables: Dict) -> Dict[str, List[str]]:
    """Group variables by table family for balanced sampling"""
    
    table_families = {}
    
    for var_id in variables.keys():
        # Extract table family (e.g., "B19" from "B19013_001E") - Fixed truncated line
        table_family = var_id[:3] if len(var_id) >= 3 else "OTHER"
        
        if table_family not in table_families:
            table_families[table_family] = []
        
        table_families[table_family].append(var_id)
    
    # Sort by family size for sampling strategy
    sorted_families = dict(sorted(table_families.items(), key=lambda x: len(x[1]), reverse=True))
    
    print(f"📊 Found {len(sorted_families)} table families")
    for family, vars_list in list(sorted_families.items())[:10]:  # Show top 10
        print(f"  {family}: {len(vars_list)} variables")
    
    return sorted_families

def intelligent_sampling_strategy(table_families: Dict[str, List[str]],
                                excluded_vars: Set[str],
                                target_size: int = 100) -> List[str]:
    """Generate intelligent sample across table families and complexity levels"""
    
    # Define priority table families for testing domain specialist routing
    priority_families = {
        "B19": 15,  # Income - test labor economist routing
        "B25": 15,  # Housing - test housing economist routing
        "B08": 10,  # Commuting - test transportation analyst routing
        "B17": 10,  # Poverty - test demographics + labor economist routing
        "B01": 8,   # Age/Sex - test demographics specialist routing
        "B15": 8,   # Education - test general routing
        "B23": 8,   # Employment - test labor economist routing
        "B09": 6,   # Children - test demographics specialist routing
        "B11": 6,   # Household composition - test general routing
        "B02": 6,   # Race - test demographics specialist routing
        "B03": 6,   # Hispanic origin - test demographics specialist routing
        "B26": 5,   # Group quarters - test housing economist routing
        "B20": 5,   # Earnings - test labor economist routing
    }
    
    selected_variables = []
    remaining_slots = target_size
    
    # Sample from priority families first
    for family, target_count in priority_families.items():
        if family in table_families and remaining_slots > 0:
            # Get variables from this family that weren't already processed
            available_vars = [v for v in table_families[family] if v not in excluded_vars]
            
            if available_vars:
                # Sample up to target_count variables from this family
                sample_size = min(target_count, len(available_vars), remaining_slots)
                family_sample = random.sample(available_vars, sample_size)
                selected_variables.extend(family_sample)
                remaining_slots -= sample_size
                
                print(f"  Selected {sample_size} variables from {family} family")
    
    # Fill remaining slots with random sampling from other families
    if remaining_slots > 0:
        other_families = {f: vars_list for f, vars_list in table_families.items()
                         if f not in priority_families}
        
        all_other_vars = []
        for vars_list in other_families.values():
            all_other_vars.extend([v for v in vars_list if v not in excluded_vars and v not in selected_variables])
        
        if all_other_vars and remaining_slots > 0:
            additional_sample = random.sample(all_other_vars, min(remaining_slots, len(all_other_vars)))
            selected_variables.extend(additional_sample)
            print(f"  Selected {len(additional_sample)} additional variables from other families")
    
    print(f"📊 Final sample: {len(selected_variables)} variables")
    return selected_variables

def validate_sample_diversity(selected_vars: List[str], variables_data: Dict) -> Dict:
    """Validate that the sample has good diversity across domains"""
    
    # Count by table family
    family_counts = {}
    for var_id in selected_vars:
        family = var_id[:3] if len(var_id) >= 3 else "OTHER"
        family_counts[family] = family_counts.get(family, 0) + 1
    
    # Count unique concepts if available
    concepts = []
    for var_id in selected_vars:
        if var_id in variables_data:
            concept = variables_data[var_id].get('concept', 'Unknown')
            concepts.append(concept)
    
    unique_concepts = len(set(concepts))
    
    diversity_report = {
        "total_variables": len(selected_vars),
        "table_families": len(family_counts),
        "family_distribution": dict(sorted(family_counts.items(), key=lambda x: x[1], reverse=True)),
        "unique_concepts": unique_concepts,
        "concept_diversity_ratio": unique_concepts / len(selected_vars) if selected_vars else 0
    }
    
    return diversity_report

def save_fresh_sample(selected_vars: List[str], variables_data: Dict, output_file: str):
    """Save the fresh sample in the format expected by enrichment pipeline"""
    
    sample_data = {}
    for var_id in selected_vars:
        if var_id in variables_data:
            sample_data[var_id] = variables_data[var_id]
        else:
            print(f"⚠️ Warning: {var_id} not found in variables data")
    
    with open(output_file, 'w') as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"💾 Fresh sample saved to: {output_file}")
    print(f"📊 Sample contains {len(sample_data)} variables")

def main():
    """Generate fresh sample for domain specialist testing"""
    
    # Configuration
    BASE_DIR = Path("../")
    ENRICHMENT_FILE = BASE_DIR / "spatial_topology_discovery/enrichment_checkpoint.json"
    VARIABLES_FILE = BASE_DIR / "complete_2023_acs_variables/complete_variables.csv"
    OUTPUT_FILE = BASE_DIR / "fresh_sample_100_domain_specialist_test.json"
    
    print("🚀 Generating fresh 100-variable sample for domain specialist testing")
    print("=" * 70)
    
    # Load existing processed variables to exclude
    excluded_vars = load_existing_processed_variables(str(ENRICHMENT_FILE))
    
    # Load full variable corpus
    variables_data = load_full_variable_corpus(str(VARIABLES_FILE))
    
    if not variables_data:
        print("❌ Could not load variable corpus. Check file path.")
        return
    
    # Categorize by table family
    table_families = categorize_variables_by_table_family(variables_data)
    
    # Generate intelligent sample
    print(f"\n🎯 Generating sample (excluding {len(excluded_vars)} already processed variables)")
    selected_vars = intelligent_sampling_strategy(table_families, excluded_vars, target_size=100)
    
    # Validate diversity
    print(f"\n📊 Sample diversity analysis:")
    diversity_report = validate_sample_diversity(selected_vars, variables_data)
    print(f"  Table families: {diversity_report['table_families']}")
    print(f"  Unique concepts: {diversity_report['unique_concepts']}")
    print(f"  Concept diversity: {diversity_report['concept_diversity_ratio']:.2f}")
    
    print(f"\n  Top table families in sample:")
    for family, count in list(diversity_report['family_distribution'].items())[:8]:
        print(f"    {family}: {count} variables")
    
    # Save sample
    save_fresh_sample(selected_vars, variables_data, str(OUTPUT_FILE))
    
    print(f"\n✅ Fresh sample generation complete!")
    print(f"📝 Ready to test domain specialist ensemble with:")
    print(f"   python enhanced_collaborative_enrichment.py \\")
    print(f"     --ensemble-mode domain_specialist \\")
    print(f"     --input-file {OUTPUT_FILE} \\")
    print(f"     --output-file domain_specialist_test_results.json \\")
    print(f"     --openai-api-key $OPENAI_API_KEY")

if __name__ == "__main__":
    # Set random seed for reproducible sampling
    random.seed(42)
    main()
