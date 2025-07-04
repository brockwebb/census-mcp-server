#!/usr/bin/env python3
"""
Extract all Census variable IDs from COOS concept JSON files
"""

import json
import glob
from pathlib import Path
from typing import Set, Dict, List

def extract_variables_from_concept_file(file_path: str) -> Set[str]:
    """Extract all census table variables from a single concept file"""
    
    variables = set()
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        concepts = data.get('concepts', [])
        
        for concept in concepts:
            census_tables = concept.get('census_tables', [])
            
            # Add all table IDs from this concept
            for table in census_tables:
                variables.add(table)
                
        print(f"  {Path(file_path).name}: {len(variables)} unique variables")
        return variables
        
    except Exception as e:
        print(f"  ERROR reading {file_path}: {e}")
        return set()

def load_full_variable_corpus(variables_file: str) -> Dict:
    """Load the complete Census variable corpus"""
    
    try:
        import pandas as pd
        df = pd.read_csv(variables_file)
        
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
        
        return variables_data
        
    except Exception as e:
        print(f"Error loading variable corpus: {e}")
        return {}

def expand_table_to_variables(table_id: str, variable_corpus: Dict) -> List[str]:
    """Expand a table ID (like B19013) to all its specific variables (like B19013_001E)"""
    
    expanded_vars = []
    
    # Find all variables that start with this table ID
    for var_id in variable_corpus:
        if var_id.startswith(table_id):
            expanded_vars.append(var_id)
    
    return expanded_vars

def main():
    """Extract all COOS variables and expand to specific Census variables"""
    
    # Configuration
    CONCEPT_DIR = Path("../concept_templates")  # Your concepts are here
    VARIABLES_FILE = Path("../complete_2023_acs_variables/complete_variables.csv")
    OUTPUT_FILE = Path("../coos_variables_extracted.json")
    
    print("🔍 Extracting COOS variables from concept files")
    print("=" * 60)
    
    # Load full variable corpus for expansion
    print("📊 Loading complete variable corpus...")
    variable_corpus = load_full_variable_corpus(str(VARIABLES_FILE))
    print(f"  Loaded {len(variable_corpus)} total variables")
    
    # Find all concept JSON files
    concept_files = list(CONCEPT_DIR.glob("*.json"))
    
    if not concept_files:
        print(f"❌ No JSON files found in {CONCEPT_DIR}")
        print("   Check the path and make sure concept files exist")
        return
    
    print(f"\n🎯 Processing {len(concept_files)} concept files:")
    
    # Extract variables from all concept files
    all_concept_variables = set()
    concept_count = 0
    
    for file_path in concept_files:
        print(f"\n📄 Processing {file_path.name}...")
        
        file_variables = extract_variables_from_concept_file(str(file_path))
        all_concept_variables.update(file_variables)
        
        # Count concepts in this file
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            file_concept_count = len(data.get('concepts', []))
            concept_count += file_concept_count
            print(f"  Concepts in file: {file_concept_count}")
        except:
            pass
    
    print(f"\n📊 COOS Extraction Summary:")
    print(f"  Total concept files: {len(concept_files)}")
    print(f"  Total concepts: {concept_count}")
    print(f"  Unique table references: {len(all_concept_variables)}")
    
    # Expand table IDs to specific variables
    print(f"\n🔍 Expanding table IDs to specific variables...")
    
    expanded_variables = set()
    expansion_report = {}
    
    for table_id in all_concept_variables:
        specific_vars = expand_table_to_variables(table_id, variable_corpus)
        expanded_variables.update(specific_vars)
        expansion_report[table_id] = len(specific_vars)
        
        if len(specific_vars) == 0:
            print(f"  ⚠️  No variables found for table: {table_id}")
    
    print(f"\n📈 Expansion Results:")
    print(f"  Table IDs processed: {len(all_concept_variables)}")
    print(f"  Total expanded variables: {len(expanded_variables)}")
    
    # Show top table expansions
    print(f"\n🔢 Top table expansions:")
    sorted_expansions = sorted(expansion_report.items(), key=lambda x: x[1], reverse=True)
    for table_id, var_count in sorted_expansions[:10]:
        print(f"  {table_id}: {var_count} variables")
    
    # Prepare output data
    output_data = {}
    
    for var_id in expanded_variables:
        if var_id in variable_corpus:
            output_data[var_id] = variable_corpus[var_id]
        else:
            print(f"  ⚠️  Variable {var_id} not found in corpus")
    
    # Save results
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✅ COOS variable extraction complete!")
    print(f"📁 Saved {len(output_data)} variables to: {OUTPUT_FILE}")
    
    # Cost estimate
    estimated_cost = len(output_data) * 0.008  # $0.008 per variable
    print(f"\n💰 Estimated enrichment cost: ${estimated_cost:.2f}")
    
    print(f"\n🚀 Ready to enrich COOS variables:")
    print(f"   python enhanced_collaborative_enrichment.py \\")
    print(f"     --input-file {OUTPUT_FILE} \\")
    print(f"     --output-file coos_enriched_results.json \\")
    print(f"     --openai-api-key $OPENAI_API_KEY \\")
    print(f"     --claude-api-key $CLAUDE_API_KEY")

if __name__ == "__main__":
    main()
