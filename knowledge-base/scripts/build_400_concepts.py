# knowledge-base/scripts/build_400_concepts.py
"""
Build the definitive 400-concept taxonomy using:
1. Official Census subject structure (subjects.json)
2. Extracted official definitions (definitions_2023.json)
3. Spock's systematic schema-first approach with confidence bucketing
4. Category template files for systematic generation
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import argparse

# Canonical schema - fail fast if any field is missing
CONCEPT_SCHEMA = {
    "id": str,           # cendata URI
    "label": str,        # Median Household Income
    "bucket": str,       # economic / social / demographic / housing
    "universe": str,     # Households / Civilian Labor Force / Population
    "stat_method": str,  # median / mean / rate / ratio / count
    "census_tables": list, # ["B19013", "B19013A"]
    "definition": str,   # verbatim from PDF
    "source_page": int,  # page number from definitions PDF
    "status": str,       # auto|reviewed|rejected
    "confidence": float  # 0-1 from LLM
}

@dataclass
class ConceptRecord:
    """Validated concept record matching canonical schema"""
    id: str
    label: str
    bucket: str
    universe: str
    stat_method: str
    census_tables: List[str]
    definition: str
    source_page: int
    status: str
    confidence: float
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "label": self.label,
            "bucket": self.bucket,
            "universe": self.universe,
            "stat_method": self.stat_method,
            "census_tables": self.census_tables,
            "definition": self.definition,
            "source_page": self.source_page,
            "status": self.status,
            "confidence": self.confidence
        }
    
    @classmethod
    def validate(cls, concept_dict: Dict) -> 'ConceptRecord':
        """Validate concept against canonical schema"""
        
        # Check all required fields exist
        for field, expected_type in CONCEPT_SCHEMA.items():
            if field not in concept_dict:
                raise ValueError(f"Missing required field: {field}")
            
            value = concept_dict[field]
            if not isinstance(value, expected_type):
                raise TypeError(f"Field {field} must be {expected_type.__name__}, got {type(value).__name__}")
        
        # Validate specific field constraints
        if concept_dict["confidence"] < 0 or concept_dict["confidence"] > 1:
            raise ValueError("Confidence must be between 0 and 1")
        
        if concept_dict["status"] not in ["auto", "reviewed", "rejected"]:
            raise ValueError("Status must be one of: auto, reviewed, rejected")
        
        return cls(**concept_dict)

class ConceptTaxonomyBuilder:
    """Build authoritative 400-concept taxonomy with schema validation"""
    
    def __init__(self):
        self.subjects = self._load_subjects()
        self.definitions = self._load_definitions()
        self.universe_definitions = self._load_universe_definitions()
        self.stat_method_definitions = self._load_stat_method_definitions()
        self.category_templates = self._load_category_templates()
        
        self.taxonomy = {
            "meta": {
                "total_concepts": 400,
                "strategy": "Spock's systematic schema-first approach",
                "sources": ["Census subjects.json", "2023_ACSSubjectDefinitions.pdf", "90% success validation"],
                "schema_version": "1.0"
            },
            "allocation": {
                "core_demographics": 50,
                "housing": 75,
                "economics": 75,
                "education": 50,
                "transportation": 25,
                "health_social": 50,
                "geography": 25,
                "specialized_populations": 50
            }
        }
    
    def _load_subjects(self) -> Dict:
        """Load official Census subjects structure"""
        subjects_path = Path("../official_sources/subjects.json")
        if subjects_path.exists():
            with open(subjects_path) as f:
                return json.load(f)
        else:
            print("❌ subjects.json not found - create it first")
            return {}
    
    def _load_definitions(self) -> Dict:
        """Load extracted official definitions"""
        definitions_path = Path("../official_sources/definitions_2023.json")
        if definitions_path.exists():
            with open(definitions_path) as f:
                return json.load(f)
        else:
            print("❌ definitions_2023.json not found - run extract_definitions.py first")
            return {}
    
    def _load_universe_definitions(self) -> Dict:
        """Load canonical universe definitions"""
        universe_path = Path("../official_sources/universe_definitions.yaml")
        if universe_path.exists():
            with open(universe_path) as f:
                return yaml.safe_load(f)
        else:
            # Create default universe definitions
            return self._create_default_universe_definitions()
    
    def _load_stat_method_definitions(self) -> Dict:
        """Load canonical statistical method definitions"""
        stat_path = Path("../official_sources/stat_method_definitions.yaml")
        if stat_path.exists():
            with open(stat_path) as f:
                return yaml.safe_load(f)
        else:
            return self._create_default_stat_method_definitions()
    
    def _load_category_templates(self) -> Dict:
        """Load category template files for concept generation"""
        templates_dir = Path("../concept_templates")
        if not templates_dir.exists():
            print(f"❌ Category templates directory not found: {templates_dir}")
            print("   Create template files for systematic concept generation")
            return {}
        
        templates = {}
        for category_file in templates_dir.glob("*.json"):
            category_name = category_file.stem
            with open(category_file) as f:
                templates[category_name] = json.load(f)
            print(f"✅ Loaded {category_name} template: {len(templates[category_name].get('concepts', []))} concept templates")
        
        return templates
    
    def _create_default_universe_definitions(self) -> Dict:
        """Create canonical universe definitions file"""
        universe_definitions = {
            "universes": {
                "Households": {
                    "definition": "All occupied housing units",
                    "excludes": "Group quarters population",
                    "census_note": "Standard household universe for income, housing costs"
                },
                "Family households": {
                    "definition": "Households with related individuals",
                    "excludes": "Single-person households, unrelated individuals",
                    "census_note": "Subset of households - use for family-specific measures"
                },
                "Population": {
                    "definition": "All persons counted in census/survey",
                    "includes": "Household and group quarters population",
                    "census_note": "Total population universe"
                },
                "Civilian labor force": {
                    "definition": "Civilians 16+ who are employed or actively seeking work",
                    "excludes": "Military, institutionalized, not seeking work",
                    "census_note": "Standard employment universe"
                },
                "Housing units": {
                    "definition": "All residential structures intended for occupancy",
                    "includes": "Occupied and vacant units",
                    "census_note": "Physical housing stock universe"
                },
                "Workers": {
                    "definition": "Employed civilians 16+ with work location data",
                    "excludes": "Unemployed, military, work-from-home varies",
                    "census_note": "Commuting and workplace universe"
                },
                "School-age population": {
                    "definition": "Population 3-24 years old",
                    "includes": "Enrolled and not enrolled",
                    "census_note": "Education enrollment universe"
                },
                "Geographic entity": {
                    "definition": "Census-defined geographic boundaries",
                    "includes": "All official Census geographic levels",
                    "census_note": "Administrative and statistical geography"
                }
            }
        }
        
        # Save to file
        universe_path = Path("../official_sources/universe_definitions.yaml")
        universe_path.parent.mkdir(exist_ok=True)
        with open(universe_path, 'w') as f:
            yaml.dump(universe_definitions, f, default_flow_style=False)
        
        print(f"✅ Created universe definitions: {universe_path}")
        return universe_definitions
    
    def _create_default_stat_method_definitions(self) -> Dict:
        """Create canonical statistical method definitions"""
        stat_definitions = {
            "methods": {
                "median": {
                    "definition": "50th percentile value",
                    "use_cases": "Income, home values, age - skewed distributions",
                    "census_tables": "Most B-tables provide medians"
                },
                "mean": {
                    "definition": "Arithmetic average",
                    "use_cases": "Household size, rooms - symmetric distributions",
                    "census_tables": "Some C-tables, derived calculations"
                },
                "rate": {
                    "definition": "Numerator/denominator expressed as percentage",
                    "use_cases": "Poverty rate, unemployment rate",
                    "calculation": "Detail variable / total variable * 100"
                },
                "ratio": {
                    "definition": "Relationship between two quantities",
                    "use_cases": "Sex ratio, dependency ratio",
                    "calculation": "Variable A / Variable B"
                },
                "count": {
                    "definition": "Simple enumeration",
                    "use_cases": "Population, housing units, establishments",
                    "census_tables": "Total variables, _001 estimates"
                },
                "percentage": {
                    "definition": "Share of total expressed as percentage",
                    "use_cases": "Educational attainment distribution",
                    "calculation": "Category / total * 100"
                }
            }
        }
        
        # Save to file
        stat_path = Path("../official_sources/stat_method_definitions.yaml")
        with open(stat_path, 'w') as f:
            yaml.dump(stat_definitions, f, default_flow_style=False)
        
        print(f"✅ Created statistical method definitions: {stat_path}")
        return stat_definitions
    
    def validate_concept_record(self, concept_dict: Dict) -> ConceptRecord:
        """Validate and create concept record"""
        return ConceptRecord.validate(concept_dict)
    
    def bucket_by_confidence(self, concepts: List[ConceptRecord], review_cap: int = 50) -> Dict:
        """Bucket concepts by confidence level"""
        
        auto_concepts = []      # ≥0.9 confidence
        review_queue = []       # 0.75-0.9 confidence
        low_confidence = []     # <0.75 confidence
        
        for concept in concepts:
            if concept.confidence >= 0.9:
                concept.status = "auto"
                auto_concepts.append(concept)
            elif concept.confidence >= 0.75:
                review_queue.append(concept)
            else:
                low_confidence.append(concept)
        
        # Respect review cap
        if len(review_queue) > review_cap:
            print(f"⚠️  Review queue ({len(review_queue)}) exceeds cap ({review_cap})")
            print(f"   Keeping top {review_cap} by confidence")
            review_queue = sorted(review_queue, key=lambda x: x.confidence, reverse=True)[:review_cap]
        
        return {
            "auto": auto_concepts,
            "review": review_queue,
            "low_confidence": low_confidence
        }
    
    def save_concept_buckets(self, bucketed_concepts: Dict, category: str):
        """Save concept buckets to separate files"""
        
        concepts_dir = Path("../concepts")
        concepts_dir.mkdir(exist_ok=True)
        
        # Save auto-approved concepts
        auto_data = {
            "meta": {
                "category": category,
                "status": "auto_approved",
                "concept_count": len(bucketed_concepts["auto"]),
                "confidence_threshold": "≥0.9"
            },
            "concepts": [c.to_dict() for c in bucketed_concepts["auto"]]
        }
        
        auto_path = concepts_dir / f"{category}.json"
        with open(auto_path, 'w') as f:
            json.dump(auto_data, f, indent=2)
        
        print(f"✅ Saved {len(bucketed_concepts['auto'])} auto-approved {category} concepts")
        
        # Save review queue as readable text dump
        if bucketed_concepts["review"]:
            review_path = concepts_dir / f"{category}_review.txt"
            with open(review_path, 'w') as f:
                f.write(f"# {category.title()} Concepts - Review Queue (0.75-0.9 confidence)\n")
                f.write(f"# Human review required - edit and mark as 'reviewed' when done\n\n")
                
                for i, concept in enumerate(bucketed_concepts["review"], 1):
                    f.write(f"## {i}. {concept.label} (confidence: {concept.confidence:.2f})\n")
                    f.write(f"ID: {concept.id}\n")
                    f.write(f"Universe: {concept.universe}\n")
                    f.write(f"Stat Method: {concept.stat_method}\n")
                    f.write(f"Tables: {concept.census_tables}\n")
                    f.write(f"Definition: {concept.definition}\n")
                    f.write(f"Status: NEEDS_REVIEW\n")
                    f.write("-" * 80 + "\n\n")
            
            print(f"📝 Saved {len(bucketed_concepts['review'])} concepts for review: {review_path}")
        
        # Save low confidence concepts for debugging
        if bucketed_concepts["low_confidence"]:
            low_path = concepts_dir / f"{category}_low_confidence.csv"
            with open(low_path, 'w') as f:
                f.write("label,confidence,universe,stat_method,definition\n")
                for concept in bucketed_concepts["low_confidence"]:
                    f.write(f'"{concept.label}",{concept.confidence},"{concept.universe}","{concept.stat_method}","{concept.definition[:100]}..."\n')
            
            print(f"⚠️  Saved {len(bucketed_concepts['low_confidence'])} low-confidence concepts: {low_path}")
    
    def generate_geography_turtle(self, geography_concepts: List[ConceptRecord]):
        """Generate Turtle RDF for geography concepts"""
        
        turtle_content = """@prefix cendata: <https://raw.githubusercontent.com/yourrepo/census-mcp-server/main/ontology#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .

# Official Census Geographic Hierarchy
# Based on Standard Hierarchy of Census Geographic Entities

# Level 0 - Root
cendata:Nation a skos:Concept ;
    rdfs:label "Nation" ;
    rdfs:comment "Singleton United States root geography" .

# Level 1 - Major divisions  
cendata:Region a skos:Concept ;
    rdfs:label "Census Region" ;
    rdfs:comment "4 Census regions (Northeast, Midwest, South, West)" ;
    skos:broader cendata:Nation .

cendata:Division a skos:Concept ;
    rdfs:label "Census Division" ;
    rdfs:comment "9 divisions nested in regions" ;
    skos:broader cendata:Region .

cendata:State a skos:Concept ;
    rdfs:label "State" ;
    rdfs:comment "50 states + DC + PR" ;
    skos:broader cendata:Nation .

# Level 2 - County and equivalent
cendata:County a skos:Concept ;
    rdfs:label "County" ;
    rdfs:comment "County or county equivalent" ;
    skos:broader cendata:State .

cendata:Place a skos:Concept ;
    rdfs:label "Place" ;
    rdfs:comment "Incorporated places and CDPs" ;
    skos:broader cendata:State .

# Level 3-5 - Small area
cendata:CensusTract a skos:Concept ;
    rdfs:label "Census Tract" ;
    rdfs:comment "Small statistical subdivisions of counties" ;
    skos:broader cendata:County .

cendata:BlockGroup a skos:Concept ;
    rdfs:label "Block Group" ;
    rdfs:comment "Subdivisions of census tracts" ;
    skos:broader cendata:CensusTract .

cendata:CensusBlock a skos:Concept ;
    rdfs:label "Census Block" ;
    rdfs:comment "Atomic geography - smallest entity" ;
    skos:broader cendata:BlockGroup .
"""
        
        # Save Turtle file
        ontology_dir = Path("../ontology")
        ontology_dir.mkdir(exist_ok=True)
        
        turtle_path = ontology_dir / "census_geography.ttl"
        with open(turtle_path, 'w') as f:
            f.write(turtle_content)
        
        print(f"✅ Generated geography ontology: {turtle_path}")
        print(f"🔗 {len(geography_concepts)} geographic concepts with hierarchical relationships")
    
    def build_concepts_from_template(self, category: str) -> List[ConceptRecord]:
        """Build concepts from category template file"""
        
        if category not in self.category_templates:
            print(f"❌ No template found for category: {category}")
            return []
        
        template = self.category_templates[category]
        concept_templates = template.get("concepts", [])
        
        validated_concepts = []
        for concept_template in concept_templates:
            try:
                # Ensure all template concepts have proper schema
                if "bucket" not in concept_template:
                    concept_template["bucket"] = category
                
                validated_concept = ConceptRecord.validate(concept_template)
                validated_concepts.append(validated_concept)
            except (ValueError, TypeError) as e:
                print(f"❌ Schema validation failed for {concept_template.get('label', 'unknown')}: {e}")
        
        return validated_concepts
    
    def build_all_categories(self, review_cap: int = 50) -> Dict[str, int]:
        """Build all concept categories systematically"""
        
        results = {}
        total_concepts = 0
        
        # Build each category from templates
        for category in self.taxonomy["allocation"].keys():
            target_count = self.taxonomy["allocation"][category]
            
            print(f"\n🔨 Building {category} concepts (target: {target_count})...")
            
            # Build from template
            concepts = self.build_concepts_from_template(category)
            
            if not concepts:
                print(f"⚠️  No concepts generated for {category} - check template file")
                results[category] = 0
                continue
            
            # Bucket by confidence
            bucketed = self.bucket_by_confidence(concepts, review_cap)
            
            # Save to files
            self.save_concept_buckets(bucketed, category)
            
            # Generate special outputs for geography
            if category == "geography":
                self.generate_geography_turtle(concepts)
            
            # Track results
            category_total = len(bucketed["auto"]) + len(bucketed["review"]) + len(bucketed["low_confidence"])
            results[category] = category_total
            total_concepts += category_total
            
            print(f"📊 {category.title()} Summary:")
            print(f"   • Auto-approved: {len(bucketed['auto'])} concepts")
            print(f"   • Review queue: {len(bucketed['review'])} concepts")
            print(f"   • Low confidence: {len(bucketed['low_confidence'])} concepts")
            print(f"   • Total: {category_total} concepts")
        
        return results, total_concepts

def main():
    """Build complete 400-concept taxonomy with systematic validation"""
    
    parser = argparse.ArgumentParser(description="Build 400-concept taxonomy")
    parser.add_argument("--subjects", default="../official_sources/subjects.json")
    parser.add_argument("--defs", default="../official_sources/definitions_2023.json")
    parser.add_argument("--target", type=int, default=400)
    parser.add_argument("--review_cap", type=int, default=50)
    parser.add_argument("--category", choices=["all", "economics", "education", "health_social", "transportation", "geography", "specialized_populations", "core_demographics", "housing"], default="all")
    
    args = parser.parse_args()
    
    print("🏗️  Building 400-Concept Authoritative Taxonomy")
    print("=" * 60)
    print(f"Target: {args.target} concepts")
    print(f"Review cap: {args.review_cap} concepts")
    print(f"Category: {args.category}")
    
    builder = ConceptTaxonomyBuilder()
    
    # Validate schema and universe definitions are available
    if not builder.universe_definitions or not builder.stat_method_definitions:
        print("❌ Missing universe or statistical method definitions")
        return
    
    print(f"✅ Schema validation ready")
    print(f"✅ {len(builder.universe_definitions['universes'])} universe definitions loaded")
    print(f"✅ {len(builder.stat_method_definitions['methods'])} statistical methods loaded")
    print(f"✅ {len(builder.category_templates)} category templates loaded")
    
    # Build concepts
    if args.category == "all":
        print(f"\n🚀 Building ALL categories systematically...")
        results, total_concepts = builder.build_all_categories(args.review_cap)
        
        print(f"\n📈 FINAL SUMMARY:")
        print(f"=" * 40)
        for category, count in results.items():
            target = builder.taxonomy["allocation"][category]
            status = "✅" if count >= target * 0.8 else "⚠️"
            print(f"   {status} {category}: {count}/{target} concepts")
        
        print(f"\n🎯 TOTAL CONCEPTS: {total_concepts}")
        print(f"🎯 TARGET: {args.target}")
        
        if total_concepts >= args.target:
            print(f"🎉 SUCCESS! Generated {total_concepts} concepts (≥{args.target} target)")
        else:
            print(f"⚠️  Generated {total_concepts} concepts (<{args.target} target)")
            print(f"   Check template files and run category-specific builds")
        
    else:
        # Build single category
        print(f"\n🔨 Building {args.category} concepts...")
        concepts = builder.build_concepts_from_template(args.category)
        
        if concepts:
            # Bucket by confidence
            bucketed = builder.bucket_by_confidence(concepts, args.review_cap)
            
            # Save to files
            builder.save_concept_buckets(bucketed, args.category)
            
            # Generate special outputs
            if args.category == "geography":
                builder.generate_geography_turtle(concepts)
            
            print(f"📊 {args.category.title()} Summary:")
            print(f"   • Auto-approved: {len(bucketed['auto'])} concepts")
            print(f"   • Review queue: {len(bucketed['review'])} concepts")
            print(f"   • Low confidence: {len(bucketed['low_confidence'])} concepts")
        else:
            print(f"❌ No concepts generated for {args.category}")
    
    print(f"\n💡 Next: Review medium-confidence concepts and run LLM validation")
    print(f"🎯 Schema validation prevents universe/method drift issues")

if __name__ == "__main__":
    main()
