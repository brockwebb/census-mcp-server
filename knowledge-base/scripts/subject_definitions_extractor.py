#!/usr/bin/env python3
"""
subject_definitions_extractor.py
Extract structured definitions from 2023 ACS Subject Definitions PDF

Usage:
    python knowledge-base/scripts/subject_definitions_extractor.py
"""

import json
import re
from pathlib import Path
import fitz  # PyMuPDF

def extract_toc_structure(pdf_path):
    """Extract table of contents structure from PDF"""
    doc = fitz.open(pdf_path)
    toc_entries = []
    
    # Look for TOC in first few pages
    for page_num in range(min(10, len(doc))):
        page = doc[page_num]
        text = page.get_text()
        
        # Look for TOC pattern: ITEM_NAME followed by page numbers
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Match pattern: "CONCEPT NAME" followed by page numbers
            # Handle underscores used as spacing in TOC
            cleaned_line = re.sub(r'_+', ' ', line)
            
            # Look for lines ending with page numbers
            page_match = re.search(r'(.+?)\s+(\d+)$', cleaned_line)
            if page_match:
                concept_name = page_match.group(1).strip()
                page_number = int(page_match.group(2))
                
                # Filter out obvious non-concepts
                if (len(concept_name) > 3 and 
                    not concept_name.startswith('TABLE OF') and
                    not concept_name.startswith('AMERICAN COMMUNITY') and
                    concept_name.upper() == concept_name):  # All caps = likely a concept
                    
                    toc_entries.append({
                        'concept_name': concept_name,
                        'page_number': page_number,
                        'source_line': line
                    })
    
    doc.close()
    return toc_entries

def extract_definitions_from_content(pdf_path, toc_entries):
    """Extract actual definitions for each concept from PDF content"""
    doc = fitz.open(pdf_path)
    definitions = []
    
    for i, entry in enumerate(toc_entries):
        concept_name = entry['concept_name']
        start_page = entry['page_number'] - 1  # Convert to 0-based indexing
        
        # Determine end page (next concept's page or end of doc)
        if i + 1 < len(toc_entries):
            end_page = toc_entries[i + 1]['page_number'] - 1
        else:
            end_page = len(doc)
        
        # Extract text from relevant pages
        definition_text = ""
        for page_num in range(start_page, min(end_page + 2, len(doc))):
            if page_num < len(doc):
                page = doc[page_num]
                text = page.get_text()
                definition_text += text + "\n"
        
        # Clean and extract the actual definition
        definition = extract_definition_for_concept(definition_text, concept_name)
        
        if definition:
            definitions.append({
                'concept_id': concept_name.lower().replace(' ', '_').replace('/', '_'),
                'label': concept_name,
                'definition': definition,
                'source_page': entry['page_number'],
                'category': determine_category(concept_name, start_page)
            })
    
    doc.close()
    return definitions

def extract_definition_for_concept(text, concept_name):
    """Extract the definition text for a specific concept"""
    lines = text.split('\n')
    definition_lines = []
    found_concept = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for the concept name as a header
        if concept_name.upper() in line.upper() and len(line) < 100:
            found_concept = True
            continue
            
        # If we found the concept, collect definition text
        if found_concept:
            # Stop at next major heading (all caps, short line)
            if (line.isupper() and len(line) < 80 and 
                line != concept_name.upper() and
                not line.startswith('AMERICAN COMMUNITY')):
                break
                
            # Skip obvious headers/footers
            if (line.startswith('AMERICAN COMMUNITY') or
                line.startswith('2023 SUBJECT') or
                re.match(r'^\d+$', line)):
                continue
                
            definition_lines.append(line)
    
    # Clean up the definition
    definition = ' '.join(definition_lines)
    definition = re.sub(r'\s+', ' ', definition)  # Normalize whitespace
    definition = definition.strip()
    
    # Only return if we have substantial content
    if len(definition) > 50:
        return definition
    
    return None

def determine_category(concept_name, page_number):
    """Temporarily assign all concepts to 'other' category for PASS 1"""
    return 'other'

def main():
    # File paths
    pdf_path = Path("knowledge-base/source-docs/OtherACS/2023_ACSSubjectDefinitions.pdf")
    output_path = Path("knowledge-base/concepts/subject_definitions.json")
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("Extracting table of contents structure...")
    toc_entries = extract_toc_structure(pdf_path)
    print(f"Found {len(toc_entries)} TOC entries")
    
    # Debug: Print first few entries
    print("\nFirst 10 TOC entries:")
    for entry in toc_entries[:10]:
        print(f"  {entry['concept_name']} (page {entry['page_number']})")
    
    print("\nExtracting definitions from content...")
    definitions = extract_definitions_from_content(pdf_path, toc_entries)
    print(f"Successfully extracted {len(definitions)} definitions")
    
    # Group by category for summary
    categories = {'other': len(definitions)}  # All concepts in 'other' for PASS 1
    
    print("\nDefinitions by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    # Save results
    output_data = {
        'metadata': {
            'source_file': '2023_ACSSubjectDefinitions.pdf',
            'extraction_date': '2025-01-04',
            'total_definitions': len(definitions),
            'categories': categories
        },
        'definitions': definitions
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Subject definitions saved to {output_path}")
    
    # Also save a summary for quick reference
    summary_path = output_path.with_suffix('.summary.txt')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("ACS Subject Definitions Extraction Summary\n")
        f.write("=" * 45 + "\n\n")
        
        for cat in sorted(categories.keys()):
            f.write(f"{cat.upper()} ({categories[cat]} definitions)\n")
            f.write("-" * (len(cat) + 20) + "\n")
            
            cat_definitions = [d for d in definitions if d['category'] == cat]
            for defn in cat_definitions:
                f.write(f"• {defn['label']} (page {defn['source_page']})\n")
            f.write("\n")
    
    print(f"✅ Summary saved to {summary_path}")

if __name__ == "__main__":
    main()
