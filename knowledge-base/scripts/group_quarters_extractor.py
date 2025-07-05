#!/usr/bin/env python3
"""
group_quarters_extractor.py
Extract structured definitions from 2023 Group Quarters Definitions PDF

Usage:
    python knowledge-base/scripts/group_quarters_extractor.py
"""

import json
import re
from pathlib import Path
import fitz  # PyMuPDF

def extract_group_quarters_definitions(pdf_path):
    """Extract all group quarters definitions from the PDF"""
    doc = fitz.open(pdf_path)
    definitions = []
    
    # Get all text from PDF
    full_text = ""
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        full_text += text + "\n"
    
    doc.close()
    
    # Define the major categories and their patterns
    categories = [
        "1. Correctional Facilities for Adults",
        "2. Juvenile Facilities", 
        "3. Nursing Facilities/Skilled Nursing Facilities",
        "4. Other Health Care Facilities",
        "5. College/University Student Housing",
        "6. Military Group Quarters",
        "7. Other Noninstitutional Facilities"
    ]
    
    # Split text into sections by category
    sections = {}
    lines = full_text.split('\n')
    current_category = None
    current_section = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line is a major category header
        is_category = False
        for cat in categories:
            if cat in line:
                # Save previous section
                if current_category and current_section:
                    sections[current_category] = '\n'.join(current_section)
                
                current_category = cat
                current_section = []
                is_category = True
                break
        
        if not is_category and current_category:
            current_section.append(line)
    
    # Don't forget the last section
    if current_category and current_section:
        sections[current_category] = '\n'.join(current_section)
    
    # Extract definitions from each section
    for category, text in sections.items():
        subcategory_definitions = extract_subcategories_from_section(text, category)
        definitions.extend(subcategory_definitions)
    
    return definitions

def extract_subcategories_from_section(text, main_category):
    """Extract subcategory definitions from a section"""
    definitions = []
    
    # Look for subcategory patterns (usually bold/capitalized headers)
    lines = text.split('\n')
    
    current_subcategory = None
    current_definition = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip page numbers and headers
        if re.match(r'^\d+$', line) or 'Group Quarters Definitions' in line:
            continue
            
        # Detect subcategory headers (usually short, capitalized lines)
        if (len(line) < 100 and 
            not line.startswith('Examples') and
            not line.startswith('Includes') and
            not line.startswith('These') and
            ('Facilities' in line or 'Centers' in line or 'Housing' in line or 
             'Quarters' in line or 'Homes' in line or 'Shelters' in line)):
            
            # Save previous definition
            if current_subcategory and current_definition:
                definition_text = ' '.join(current_definition)
                definition_text = clean_definition_text(definition_text)
                
                if len(definition_text) > 50:  # Only save substantial definitions
                    definitions.append({
                        'concept_id': create_concept_id(current_subcategory),
                        'label': current_subcategory,
                        'definition': definition_text,
                        'main_category': main_category,
                        'category': 'specialized_populations',  # All GQ are specialized populations
                        'source_page': estimate_page_number(main_category)
                    })
            
            current_subcategory = line
            current_definition = []
        
        elif current_subcategory:
            # This is part of the definition
            current_definition.append(line)
    
    # Don't forget the last definition
    if current_subcategory and current_definition:
        definition_text = ' '.join(current_definition)
        definition_text = clean_definition_text(definition_text)
        
        if len(definition_text) > 50:
            definitions.append({
                'concept_id': create_concept_id(current_subcategory),
                'label': current_subcategory,
                'definition': definition_text,
                'main_category': main_category,
                'category': 'specialized_populations',
                'source_page': estimate_page_number(main_category)
            })
    
    return definitions

def create_concept_id(label):
    """Create a concept ID from the label"""
    # Convert to lowercase, replace spaces and special chars with underscores
    concept_id = label.lower()
    concept_id = re.sub(r'[^\w\s]', '', concept_id)  # Remove punctuation
    concept_id = re.sub(r'\s+', '_', concept_id)     # Replace spaces with underscores
    concept_id = re.sub(r'_+', '_', concept_id)      # Collapse multiple underscores
    concept_id = concept_id.strip('_')               # Remove leading/trailing underscores
    return concept_id

def clean_definition_text(text):
    """Clean up definition text"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common noise patterns
    text = re.sub(r'\d+$', '', text)  # Remove trailing page numbers
    
    return text.strip()

def estimate_page_number(category):
    """Estimate page number based on category"""
    page_map = {
        "1. Correctional Facilities for Adults": 1,
        "2. Juvenile Facilities": 3,
        "3. Nursing Facilities/Skilled Nursing Facilities": 4,
        "4. Other Health Care Facilities": 4,
        "5. College/University Student Housing": 5,
        "6. Military Group Quarters": 6,
        "7. Other Noninstitutional Facilities": 6
    }
    return page_map.get(category, 1)

def main():
    # File paths
    pdf_path = Path("knowledge-base/source-docs/OtherACS/2023GQ_Definitions.pdf")
    output_path = Path("knowledge-base/concepts/group_quarters_definitions.json")
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("Extracting Group Quarters definitions...")
    definitions = extract_group_quarters_definitions(pdf_path)
    print(f"Successfully extracted {len(definitions)} definitions")
    
    # Group by main category for summary
    categories = {}
    for defn in definitions:
        cat = defn['main_category']
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1
    
    print("\nDefinitions by main category:")
    for cat, count in categories.items():
        print(f"  {cat}: {count}")
    
    # Save results
    output_data = {
        'metadata': {
            'source_file': '2023GQ_Definitions.pdf',
            'extraction_date': '2025-01-04',
            'total_definitions': len(definitions),
            'categories': categories
        },
        'definitions': definitions
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Group Quarters definitions saved to {output_path}")
    
    # Show sample definitions
    print("\nSample definitions:")
    for i, defn in enumerate(definitions[:3]):
        print(f"\n{i+1}. {defn['label']}")
        print(f"   ID: {defn['concept_id']}")
        print(f"   Definition: {defn['definition'][:100]}...")

if __name__ == "__main__":
    main()
