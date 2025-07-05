#!/usr/bin/env python3
"""
combined_definitions_merger.py
Merge Group Quarters and Subject Definitions into single backbone

Usage:
    python knowledge-base/scripts/combined_definitions_merger.py
"""

import json
from pathlib import Path

def main():
    # Input files
    subject_defs_path = Path("knowledge-base/concepts/subject_definitions.json")
    gq_defs_path = Path("knowledge-base/concepts/group_quarters_definitions.json")
    output_path = Path("knowledge-base/concepts/census_backbone_definitions.json")
    
    # Load both files
    print("Loading Subject Definitions...")
    with open(subject_defs_path, 'r', encoding='utf-8') as f:
        subject_data = json.load(f)
    
    print("Loading Group Quarters Definitions...")
    with open(gq_defs_path, 'r', encoding='utf-8') as f:
        gq_data = json.load(f)
    
    # Combine definitions
    all_definitions = []
    
    # Add subject definitions (with prefix to avoid ID conflicts)
    for defn in subject_data['definitions']:
        defn['source'] = 'subject_definitions'
        all_definitions.append(defn)
    
    # Add group quarters definitions (with prefix to avoid ID conflicts)
    for defn in gq_data['definitions']:
        defn['concept_id'] = f"gq_{defn['concept_id']}"  # Prefix to avoid conflicts
        defn['source'] = 'group_quarters'
        all_definitions.append(defn)
    
    # Create combined metadata
    combined_metadata = {
        'source_files': [
            '2023_ACSSubjectDefinitions.pdf',
            '2023GQ_Definitions.pdf'
        ],
        'extraction_date': '2025-01-04',
        'total_definitions': len(all_definitions),
        'subject_definitions_count': len(subject_data['definitions']),
        'group_quarters_count': len(gq_data['definitions']),
        'categories': {}
    }
    
    # Count by category
    for defn in all_definitions:
        cat = defn.get('category', 'other')
        if cat not in combined_metadata['categories']:
            combined_metadata['categories'][cat] = 0
        combined_metadata['categories'][cat] += 1
    
    # Create final structure
    combined_data = {
        'metadata': combined_metadata,
        'definitions': all_definitions
    }
    
    # Save combined file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Combined definitions saved to {output_path}")
    print(f"📊 Total definitions: {len(all_definitions)}")
    print(f"   Subject Definitions: {len(subject_data['definitions'])}")
    print(f"   Group Quarters: {len(gq_data['definitions'])}")
    
    print("\n📋 Categories breakdown:")
    for cat, count in sorted(combined_metadata['categories'].items()):
        print(f"   {cat}: {count}")
    
    # Show some sample combined results
    print("\n🔍 Sample combined definitions:")
    
    # Show one from each source
    subject_sample = next((d for d in all_definitions if d['source'] == 'subject_definitions'), None)
    gq_sample = next((d for d in all_definitions if d['source'] == 'group_quarters'), None)
    
    if subject_sample:
        print(f"\nSubject Definition Example:")
        print(f"   ID: {subject_sample['concept_id']}")
        print(f"   Label: {subject_sample['label']}")
        print(f"   Definition: {subject_sample['definition'][:100]}...")
    
    if gq_sample:
        print(f"\nGroup Quarters Example:")
        print(f"   ID: {gq_sample['concept_id']}")
        print(f"   Label: {gq_sample['label']}")
        print(f"   Definition: {gq_sample['definition'][:100]}...")

if __name__ == "__main__":
    main()
