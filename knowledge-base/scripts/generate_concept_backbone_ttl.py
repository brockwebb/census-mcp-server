#!/usr/bin/env python3
"""
generate_concept_backbone_ttl.py - Convert 160 weighted Census concepts to RDF/TTL

Converts subject_definitions_weighted.json to RDF Turtle format for knowledge graph integration.
Generates clean concept IDs, weight predicates, and skos:broader relationships.

Usage:
    python knowledge-base/scripts/generate_concept_backbone_ttl.py
    
Output:
    knowledge-base/concepts/concept_backbone.ttl
"""

import json
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - TTL_GENERATOR - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Domain mapping to existing category concepts
DOMAIN_TO_CATEGORY = {
    'housing': 'Housing',
    'core_demographics': 'CoreDemographics',
    'economics': 'Economics',
    'specialized_populations': 'SpecializedPopulations',
    'education': 'Education',
    'geography': 'Geography',
    'transportation': 'Transportation',
    'health_social': 'HealthSocial'
}

# Valid domains for validation
VALID_DOMAINS = set(DOMAIN_TO_CATEGORY.keys())

class ConceptBackboneTTLGenerator:
    """Generate RDF/TTL from weighted Census concept definitions"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.input_path = self.base_dir / "concepts" / "subject_definitions_weighted.json"
        self.output_path = self.base_dir / "concepts" / "concept_backbone.ttl"
        
        self.used_ids = set()  # Track used concept IDs to prevent duplicates
        self.id_transforms = []  # Log ID transformations for audit
        
    def generate_concept_id(self, label: str, original_id: str = None) -> str:
        """
        Generate clean concept ID from label.
        
        Transforms labels like "GROSS RENT AS A PERCENTAGE OF HOUSEHOLD INCOME"
        to "GrossRentPctIncome" while ensuring uniqueness.
        """
        # Try original ID first if provided and valid
        if original_id and re.match(r'^[A-Za-z][A-Za-z0-9_]*$', original_id):
            if original_id not in self.used_ids:
                self.used_ids.add(original_id)
                return original_id
        
        # Generate from label
        # Remove common noise words and replace with shorter forms
        replacements = {
            r'\b(PERCENTAGE|PERCENT|PCT)\b': 'Pct',
            r'\b(NUMBER|NUM)\b': 'Num',
            r'\b(TOTAL|TOT)\b': 'Total',
            r'\b(POPULATION|POP)\b': 'Pop',
            r'\b(HOUSEHOLD|HH)\b': 'Household',
            r'\b(INCOME|INC)\b': 'Income',
            r'\b(EDUCATION|EDU)\b': 'Education',
            r'\b(EMPLOYMENT|EMP)\b': 'Employment',
            r'\b(TRANSPORTATION|TRANS)\b': 'Transportation'
        }
        
        clean_label = label.upper()
        for pattern, replacement in replacements.items():
            clean_label = re.sub(pattern, replacement, clean_label)
        
        # Split into words and create CamelCase
        words = re.findall(r'[A-Za-z]+', clean_label)
        concept_id = ''.join(word.capitalize() for word in words if len(word) > 1)
        
        # Truncate if too long
        if len(concept_id) > 50:
            concept_id = concept_id[:50]
        
        # Ensure uniqueness
        base_id = concept_id
        counter = 1
        while concept_id in self.used_ids:
            concept_id = f"{base_id}{counter}"
            counter += 1
        
        self.used_ids.add(concept_id)
        
        # Log transformation
        self.id_transforms.append({
            'original_label': label,
            'generated_id': concept_id,
            'original_id': original_id
        })
        
        return concept_id
    
    def validate_weights(self, weights: Dict[str, float], concept_label: str) -> List[str]:
        """Validate domain weights for a concept"""
        issues = []
        
        # Check for invalid domains
        invalid_domains = set(weights.keys()) - VALID_DOMAINS
        if invalid_domains:
            issues.append(f"Invalid domains: {invalid_domains}")
        
        # Check weight sum (should be close to 1.0)
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.01:
            issues.append(f"Weight sum {total_weight:.3f} != 1.0")
        
        # Check for negative weights
        negative_weights = {k: v for k, v in weights.items() if v < 0}
        if negative_weights:
            issues.append(f"Negative weights: {negative_weights}")
        
        return issues
    
    def escape_ttl_string(self, text: str) -> str:
        """Escape string for TTL format"""
        # Use triple quotes for multi-line strings to preserve formatting
        if '\n' in text or '"' in text:
            # Escape triple quotes if they exist
            text = text.replace('"""', r'\"\"\"')
            return f'"""{text}"""'
        else:
            # Escape quotes and backslashes
            text = text.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{text}"'
    
    def generate_ttl_header(self) -> str:
        """Generate TTL file header with prefixes and declarations"""
        header = f"""# Census Concept Backbone - Generated {datetime.now().isoformat()}
# 160 weighted Census subject definitions as SKOS concepts

@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix cendata: <https://example.org/cendata/> .

# Weight predicates for multi-domain concept weighting
cendata:weightHousing a owl:DatatypeProperty ;
    rdfs:label "Housing domain weight" ;
    rdfs:range xsd:decimal .

cendata:weightCoreDemographics a owl:DatatypeProperty ;
    rdfs:label "Core Demographics domain weight" ;
    rdfs:range xsd:decimal .

cendata:weightEconomics a owl:DatatypeProperty ;
    rdfs:label "Economics domain weight" ;
    rdfs:range xsd:decimal .

cendata:weightSpecializedPopulations a owl:DatatypeProperty ;
    rdfs:label "Specialized Populations domain weight" ;
    rdfs:range xsd:decimal .

cendata:weightEducation a owl:DatatypeProperty ;
    rdfs:label "Education domain weight" ;
    rdfs:range xsd:decimal .

cendata:weightGeography a owl:DatatypeProperty ;
    rdfs:label "Geography domain weight" ;
    rdfs:range xsd:decimal .

cendata:weightTransportation a owl:DatatypeProperty ;
    rdfs:label "Transportation domain weight" ;
    rdfs:range xsd:decimal .

cendata:weightHealthSocial a owl:DatatypeProperty ;
    rdfs:label "Health & Social domain weight" ;
    rdfs:range xsd:decimal .

# Concept definitions begin here

"""
        return header
    
    def generate_concept_ttl(self, concept: Dict) -> str:
        """Generate TTL for a single concept"""
        # Extract data
        label = concept.get('label', 'Unknown')
        definition = concept.get('definition', '')
        weights = concept.get('domain_weights', {})
        source_page = concept.get('source_page')
        
        # Validate weights
        validation_issues = self.validate_weights(weights, label)
        if validation_issues:
            logger.warning(f"Validation issues for '{label}': {validation_issues}")
        
        # Generate concept ID
        original_id = concept.get('concept_id')
        concept_id = self.generate_concept_id(label, original_id)
        
        # Find primary domain (highest weight)
        if weights:
            primary_domain = max(weights.keys(), key=lambda k: weights[k])
            primary_category = DOMAIN_TO_CATEGORY[primary_domain]
        else:
            primary_category = 'CoreDemographics'  # Default fallback
        
        # Start TTL generation
        ttl = f'cendata:{concept_id}\n'
        ttl += '    a skos:Concept ;\n'
        ttl += f'    skos:prefLabel {self.escape_ttl_string(label)} ;\n'
        
        if definition:
            ttl += f'    skos:definition {self.escape_ttl_string(definition)} ;\n'
        
        # Add broader relationship
        ttl += f'    skos:broader cendata:{primary_category} ;\n'
        
        # Add weight predicates with proper datatype
        for domain, weight in sorted(weights.items()):
            if weight >= 0.05:  # Only include significant weights
                predicate = f"weight{DOMAIN_TO_CATEGORY[domain]}"
                ttl += f'    cendata:{predicate} "{weight:.4f}"^^xsd:decimal ;\n'
        
        # Add source information
        if source_page:
            ttl += f'    dct:source "ACS 2023 Subject Definitions, p. {source_page}" ;\n'
        else:
            ttl += f'    dct:source "ACS 2023 Subject Definitions" ;\n'
        
        # Remove trailing semicolon and add period
        ttl = ttl.rstrip(' ;\n') + ' .\n\n'
        
        return ttl
    
    def load_and_validate_input(self) -> Dict:
        """Load and validate input JSON file"""
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_path}")
        
        logger.info(f"Loading concepts from {self.input_path}")
        
        with open(self.input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate structure
        if 'definitions' not in data:
            raise ValueError("Input file missing 'definitions' key")
        
        definitions = data['definitions']
        logger.info(f"Loaded {len(definitions)} concept definitions")
        
        # Quick validation of required fields
        missing_fields = []
        for i, defn in enumerate(definitions):
            required = ['concept_id', 'label', 'definition', 'domain_weights']
            missing = [field for field in required if field not in defn]
            if missing:
                missing_fields.append(f"Definition {i}: missing {missing}")
        
        if missing_fields:
            logger.error("Input validation errors:")
            for error in missing_fields[:5]:  # Show first 5 errors
                logger.error(f"  {error}")
            if len(missing_fields) > 5:
                logger.error(f"  ... and {len(missing_fields) - 5} more")
            raise ValueError("Input file has validation errors")
        
        return data
    
    def generate_ttl(self) -> None:
        """Main TTL generation workflow"""
        logger.info("🚀 Starting TTL generation for concept backbone")
        
        # Load input data
        data = self.load_and_validate_input()
        definitions = data['definitions']
        
        # Generate TTL content
        ttl_content = self.generate_ttl_header()
        
        # Process each concept
        valid_concepts = 0
        error_concepts = 0
        
        for concept in definitions:
            try:
                concept_ttl = self.generate_concept_ttl(concept)
                ttl_content += concept_ttl
                valid_concepts += 1
            except Exception as e:
                error_concepts += 1
                concept_id = concept.get('concept_id', 'unknown')
                logger.error(f"Error generating TTL for {concept_id}: {e}")
        
        # Write output file
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(ttl_content)
        
        logger.info(f"✅ TTL generation complete!")
        logger.info(f"   Output: {self.output_path}")
        logger.info(f"   Valid concepts: {valid_concepts}")
        logger.info(f"   Error concepts: {error_concepts}")
        
        # Log ID transformations if any
        if self.id_transforms:
            logger.info(f"\n📝 Concept ID transformations ({len(self.id_transforms)}):")
            for transform in self.id_transforms[:10]:  # Show first 10
                logger.info(f"   '{transform['original_label']}' → {transform['generated_id']}")
            if len(self.id_transforms) > 10:
                logger.info(f"   ... and {len(self.id_transforms) - 10} more")
        
        # Validate output file
        self.validate_output()
    
    def validate_output(self) -> None:
        """Validate generated TTL file"""
        try:
            # Basic syntax check - try to load with rdflib if available
            try:
                from rdflib import Graph
                g = Graph()
                g.parse(str(self.output_path), format='turtle')
                triple_count = len(g)
                logger.info(f"✅ TTL syntax validation passed ({triple_count} triples)")
            except ImportError:
                logger.info("📝 rdflib not available - skipping syntax validation")
            except Exception as e:
                logger.error(f"❌ TTL syntax validation failed: {e}")
        
        except Exception as e:
            logger.error(f"Validation error: {e}")
    
    def generate_summary_report(self) -> None:
        """Generate summary statistics for the TTL file"""
        if not self.output_path.exists():
            logger.error("Cannot generate report - TTL file not found")
            return
        
        # Count concepts and relationships using regex to avoid false positives
        with open(self.output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use regex patterns to count accurately
        concept_pattern = re.compile(r'^\s*cendata:[A-Za-z0-9_]+\s+a\s+skos:Concept', re.MULTILINE)
        broader_pattern = re.compile(r'\s+skos:broader\s+cendata:', re.MULTILINE)
        weight_pattern = re.compile(r'\s+cendata:weight\w+\s+', re.MULTILINE)
        
        concept_count = len(concept_pattern.findall(content))
        broader_count = len(broader_pattern.findall(content))
        weight_count = len(weight_pattern.findall(content))
        
        logger.info(f"\n📊 TTL Generation Summary:")
        logger.info(f"   File size: {self.output_path.stat().st_size:,} bytes")
        logger.info(f"   Concepts: {concept_count}")
        logger.info(f"   skos:broader links: {broader_count}")
        logger.info(f"   Weight assignments: {weight_count}")
        logger.info(f"   ID transformations: {len(self.id_transforms)}")

def main():
    """Main execution function"""
    try:
        generator = ConceptBackboneTTLGenerator()
        generator.generate_ttl()
        generator.generate_summary_report()
        
        logger.info("\n🎯 Next steps:")
        logger.info("   1. Load TTL into your graph store")
        logger.info("   2. Verify skos:broader relationships")
        logger.info("   3. Test SPARQL queries")
        logger.info("   4. Proceed to variable linking (Step 3-B)")
        
    except Exception as e:
        logger.error(f"TTL generation failed: {e}")
        raise

if __name__ == "__main__":
    main()
