# extract_definitions.py
"""
Extract concept definitions from 2023 ACS Subject Definitions PDF
Based on Spock's guidance
"""

import json
import re
from pathlib import Path

try:
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer
except ImportError:
    print("Installing pdfminer.six...")
    import subprocess
    subprocess.run(["pip", "install", "pdfminer.six"])
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer

def extract_acs_definitions(pdf_path="../official_sources/2023_ACSSubjectDefinitions.pdf"):
    """Extract concept definitions from ACS Subject Definitions PDF"""
    
    if not Path(pdf_path).exists():
        print(f"❌ PDF not found: {pdf_path}")
        print("Download from: https://www2.census.gov/programs-surveys/acs/tech_docs/subject_definitions/2023_ACSSubjectDefinitions.pdf")
        return {}
    
    print(f"🔍 Extracting definitions from {pdf_path}...")
    
    concepts = {}
    
    for page_num, page in enumerate(extract_pages(pdf_path)):
        # Extract text from page
        text_elements = []
        for element in page:
            if isinstance(element, LTTextContainer):
                text_elements.append(element.get_text())
        
        page_text = "\n".join(text_elements)
        
        # Look for concept definitions
        # Pattern: Concept name (usually capitalized) followed by definition
        for match in re.finditer(r"^([A-Z][A-Za-z ,;/&()-]{3,60})\s*\n(.*?)\n{2,}", page_text, re.S | re.M):
            label, definition = match.groups()
            label = label.strip()
            definition = " ".join(definition.split())  # Clean whitespace
            
            # Filter out obvious non-concepts (page headers, etc.)
            if len(definition) > 20 and not label.startswith(("Page ", "Figure ", "Table ")):
                concepts[label] = {
                    "definition": definition,
                    "source_pdf": "2023_ACSSubjectDefinitions.pdf",
                    "page": page_num + 1
                }
    
    print(f"✅ Extracted {len(concepts)} concept definitions")
    return concepts

def save_definitions(concepts, output_path="../official_sources/definitions_2023.json"):
    """Save extracted definitions to JSON file"""
    
    Path(output_path).parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(concepts, f, indent=2)
    
    print(f"💾 Saved definitions to {output_path}")

def preview_definitions(concepts, num_examples=5):
    """Preview extracted definitions"""
    
    print(f"\n📋 Preview of extracted definitions:")
    for i, (concept, data) in enumerate(list(concepts.items())[:num_examples]):
        print(f"\n{i+1}. {concept}")
        print(f"   Definition: {data['definition'][:100]}...")
        print(f"   Page: {data['page']}")

if __name__ == "__main__":
    # Extract definitions
    concepts = extract_acs_definitions()
    
    if concepts:
        # Save to file
        save_definitions(concepts)
        
        # Preview results
        preview_definitions(concepts)
        
        print(f"\n🎯 Ready to use official definitions in concept mapping!")
    else:
        print("❌ No definitions extracted. Check PDF path and format.")
