#!/usr/bin/env python3
"""
Create bulk variables list by excluding already processed variables
"""

import json
import pandas as pd
import argparse
from pathlib import Path

def load_variable_ids(file_path):
    """Load variable IDs from various file formats"""
    if not Path(file_path).exists():
        print(f"⚠️ File not found: {file_path}")
        return set()
    
    try:
        # Handle CSV files
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            if 'variable_id' in df.columns:
                return set(df['variable_id'].dropna())
            elif 'name' in df.columns:
                return set(df['name'].dropna())
            else:
                print(f"⚠️ CSV file {file_path} missing 'variable_id' or 'name' column")
                return set()
        
        # Handle JSON files
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            return set(data.keys())
        elif isinstance(data, list):
            # Handle results format with variable_id field
            var_ids = set()
            for item in data:
                if isinstance(item, dict) and 'variable_id' in item:
                    var_ids.add(item['variable_id'])
                elif isinstance(item, str):
                    var_ids.add(item)
            return var_ids
        else:
            print(f"⚠️ Unexpected format in {file_path}")
            return set()
            
    except Exception as e:
        print(f"⚠️ Error loading {file_path}: {e}")
        return set()

def load_complete_corpus(file_path):
    """Load complete corpus data in proper format"""
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
        corpus_data = {}
        for _, row in df.iterrows():
            var_id = row.get('variable_id')
            if var_id:
                corpus_data[var_id] = {
                    'label': row.get('label', 'Unknown'),
                    'concept': row.get('concept', 'Unknown'),
                    'predicateType': row.get('predicateType', 'Unknown'),
                    'group': row.get('group', 'Unknown'),
                    'survey': row.get('survey', 'Unknown'),
                    'complexity': row.get('complexity', 'Unknown')
                }
        return corpus_data
    else:
        # JSON format
        with open(file_path, 'r') as f:
            return json.load(f)

def main():
    parser = argparse.ArgumentParser(description='Create bulk variables by excluding processed ones')
    parser.add_argument('--complete-corpus', required=True, help='Complete variable corpus file')
    parser.add_argument('--exclude-coos', help='COOS variables file')
    parser.add_argument('--exclude-results', action='append', help='Results files to exclude (can use multiple times)')
    parser.add_argument('--output', required=True, help='Output file for bulk variables')
    
    args = parser.parse_args()
    
    print("🔍 Creating bulk variables list...")
    
    # Load complete corpus
    print(f"📊 Loading complete corpus from {args.complete_corpus}")
    corpus_data = load_complete_corpus(args.complete_corpus)
    all_variables = set(corpus_data.keys())
    print(f"   Found {len(all_variables)} total variables")
    
    # Track exclusions
    excluded = set()
    
    # Exclude COOS variables
    if args.exclude_coos:
        print(f"🎯 Excluding COOS variables from {args.exclude_coos}")
        coos_vars = load_variable_ids(args.exclude_coos)
        excluded.update(coos_vars)
        print(f"   Excluded {len(coos_vars)} COOS variables")
    
    # Exclude result files
    if args.exclude_results:
        for results_file in args.exclude_results:
            print(f"✅ Excluding processed variables from {results_file}")
            processed_vars = load_variable_ids(results_file)
            excluded.update(processed_vars)
            print(f"   Excluded {len(processed_vars)} processed variables")
    
    # Calculate bulk variables
    bulk_variables = all_variables - excluded
    
    print(f"\n📈 Summary:")
    print(f"   Total variables: {len(all_variables)}")
    print(f"   Excluded variables: {len(excluded)}")
    print(f"   Bulk variables: {len(bulk_variables)}")
    
    # Load original corpus data for bulk variables
    print(f"💾 Creating bulk variables file...")
    
    # Extract data for bulk variables only
    bulk_data = {var_id: corpus_data[var_id] for var_id in bulk_variables if var_id in corpus_data}
    
    # Save bulk variables
    with open(args.output, 'w') as f:
        json.dump(bulk_data, f, indent=2)
    
    print(f"✅ Saved {len(bulk_data)} bulk variables to {args.output}")
    
    # Estimate cost
    estimated_cost = len(bulk_data) * 0.001  # $0.001 per variable for single agent
    print(f"💰 Estimated cost: ${estimated_cost:.2f}")

if __name__ == "__main__":
    main()
