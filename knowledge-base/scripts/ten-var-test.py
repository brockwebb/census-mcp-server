#!/usr/bin/env python3
"""
Extract 10 test variables for config validation
"""

import json
from pathlib import Path

def extract_10_test_variables():
    """Extract 10 diverse variables for testing"""
    
    # Try different possible paths for the complete variables file
    possible_paths = [
        "../complete_2023_acs_variables/complete_variables.csv",
        "../coos_variables_extracted.json",
        "complete_variables.csv",
        "coos_variables_extracted.json"
    ]
    
    variables_data = None
    source_file = None
    
    # Try to find an existing variables file
    for path in possible_paths:
        if Path(path).exists():
            source_file = path
            break
    
    if not source_file:
        print("❌ No variables file found. Please check paths:")
        for path in possible_paths:
            print(f"   {path}")
        return
    
    print(f"📁 Loading variables from: {source_file}")
    
    # Load data based on file type
    if source_file.endswith('.json'):
        with open(source_file, 'r') as f:
            variables_data = json.load(f)
    elif source_file.endswith('.csv'):
        import pandas as pd
        df = pd.read_csv(source_file)
        # Convert to JSON format expected by enrichment script
        variables_data = {}
        for _, row in df.iterrows():
            var_id = row.get('name', row.get('variable_id', 'unknown'))
            variables_data[var_id] = {
                'label': row.get('label', 'Unknown'),
                'concept': row.get('concept', 'Unknown'),
                'universe': row.get('universe', 'Unknown')
            }
    
    if not variables_data:
        print("❌ Could not load variables data")
        return
    
    print(f"📊 Found {len(variables_data)} total variables")
    
    # Select 10 diverse test variables
    # Try to get different table families
    selected_vars = {}
    target_tables = ['B19', 'B25', 'B08', 'B17', 'B01', 'B15', 'B23', 'B02', 'B11', 'B20']
    
    for table_prefix in target_tables:
        for var_id, var_data in variables_data.items():
            if var_id.startswith(table_prefix) and var_id not in selected_vars:
                selected_vars[var_id] = var_data
                break
        if len(selected_vars) >= 10:
            break
    
    # If we don't have 10 yet, just take first available
    if len(selected_vars) < 10:
        remaining_needed = 10 - len(selected_vars)
        for var_id, var_data in variables_data.items():
            if var_id not in selected_vars:
                selected_vars[var_id] = var_data
                remaining_needed -= 1
                if remaining_needed == 0:
                    break
    
    # Save test file
    output_file = "test_10_variables.json"
    with open(output_file, 'w') as f:
        json.dump(selected_vars, f, indent=2)
    
    print(f"\n✅ Test file created: {output_file}")
    print(f"📋 Selected {len(selected_vars)} test variables:")
    
    for var_id, var_data in selected_vars.items():
        table_family = var_id[:3] if len(var_id) >= 3 else var_id
        label = var_data.get('label', 'Unknown')[:50] + "..." if len(var_data.get('label', '')) > 50 else var_data.get('label', 'Unknown')
        print(f"   {var_id} ({table_family}): {label}")
    
    print(f"\n🧪 Ready to test with:")
    print(f"   python enhanced_collaborative_enrichment.py \\")
    print(f"     --input-file {output_file} \\")
    print(f"     --output-file test_results.json \\")
    print(f"     --config-file agent_config.yaml \\")
    print(f"     --openai-api-key $OPENAI_API_KEY \\")
    print(f"     --claude-api-key $CLAUDE_API_KEY \\")
    print(f"     --max-variables 10")

if __name__ == "__main__":
    extract_10_test_variables()
