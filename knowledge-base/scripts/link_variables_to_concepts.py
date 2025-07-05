#!/usr/bin/env python3
"""
link_variables_to_concepts.py - Step 3-B: Link 36K variables to 160 backbone concepts

Uses sentence transformers to compute semantic similarity between variable descriptions
and backbone concept definitions, then generates weighted links based on cosine similarity.

Usage:
    python knowledge-base/scripts/link_variables_to_concepts.py
    
Inputs:
    - knowledge-base/concepts/concept_backbone.ttl (160 backbone concepts)
    - 2023_ACS_Enriched_Universe.json (36,918 enriched variables)
    
Output:
    - knowledge-base/concepts/variable_links.ttl
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Tuple, Set
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - VAR_LINKER - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SIMILARITY_THRESHOLD = 0.20  # Minimum cosine similarity to create a link
MAX_CONCEPTS_PER_VARIABLE = 5  # Maximum backbone concepts per variable
EMBEDDING_MODEL = "sentence-transformers/all-roberta-large-v1"  # Match your existing setup
BATCH_SIZE = 50  # Process variables in batches (match your concept_weight_extractor)
EMBED_BATCH_SIZE = 32  # Embedding batch size

class VariableConceptLinker:
    """Link variables to backbone concepts using semantic similarity"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.backbone_path = self.base_dir / "concepts" / "concept_backbone.ttl"
        
        # Try multiple possible locations for the variables file
        possible_paths = [
            self.base_dir / "scripts" / "2023_ACS_Enriched_Universe.json",  # Found location
            Path("2023_ACS_Enriched_Universe.json"),
            Path("../2023_ACS_Enriched_Universe.json"),
            Path("data/2023_ACS_Enriched_Universe.json"),
            self.base_dir / "data" / "2023_ACS_Enriched_Universe.json",
            self.base_dir.parent / "2023_ACS_Enriched_Universe.json"
        ]
        
        self.variables_path = None
        for path in possible_paths:
            if path.exists():
                self.variables_path = path
                break
        
        if self.variables_path is None:
            # If not found, use the first option as default for error message
            self.variables_path = possible_paths[0]
            
        self.output_path = self.base_dir / "concepts" / "variable_links.ttl"
        self.cache_path = self.base_dir / "concepts" / "embedding_cache.pkl"
        self.checkpoint_path = self.base_dir / "concepts" / "linking_checkpoint.json"
        
        # Load sentence transformer model
        logger.info(f"Loading sentence transformer model: {EMBEDDING_MODEL}")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        
        # Storage for concepts and variables
        self.backbone_concepts = []  # List of concept dicts
        self.concept_embeddings = None  # Numpy array of embeddings
        self.variables = []  # List of variable dicts
        
        # Statistics tracking
        self.stats = {
            'total_variables': 0,
            'variables_linked': 0,
            'variables_unlinked': 0,
            'total_links': 0,
            'avg_concepts_per_variable': 0.0,
            'similarity_distribution': []
        }
    
    def extract_backbone_concepts(self) -> List[Dict]:
        """Extract concept definitions from TTL backbone file"""
        logger.info(f"Extracting backbone concepts from {self.backbone_path}")
        
        if not self.backbone_path.exists():
            raise FileNotFoundError(f"Backbone file not found: {self.backbone_path}")
        
        concepts = []
        
        with open(self.backbone_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split content into blocks starting with "cendata:"
        blocks = re.split(r'\ncendata:', content)
        
        for i, block in enumerate(blocks):
            if i == 0:  # Skip header block
                continue
                
            # Add back the cendata: prefix
            block = 'cendata:' + block
            lines = block.strip().split('\n')
            
            if not lines:
                continue
            
            # Extract concept ID from first line
            first_line = lines[0].strip()
            if not first_line.startswith('cendata:'):
                continue
                
            concept_id = first_line.replace('cendata:', '').strip()
            
            # Initialize concept
            concept = {'id': concept_id, 'label': '', 'definition': ''}
            
            # Parse lines for prefLabel and definition
            in_definition = False
            definition_parts = []
            
            for line in lines[1:]:
                line = line.strip()
                
                if 'skos:prefLabel' in line:
                    # Extract label - it's enclosed in quotes
                    if '"' in line:
                        parts = line.split('"')
                        if len(parts) >= 2:
                            concept['label'] = parts[1].strip()
                
                elif 'skos:definition' in line:
                    # Start of definition
                    in_definition = True
                    if '"' in line:
                        # Definition starts on same line
                        after_def = line.split('skos:definition', 1)[1].strip()
                        if after_def.startswith('"'):
                            definition_text = after_def[1:]  # Remove opening quote
                            if definition_text.endswith('";'):
                                # Single line definition
                                concept['definition'] = definition_text[:-2].strip()
                                in_definition = False
                            elif definition_text.endswith('"'):
                                # Single line definition
                                concept['definition'] = definition_text[:-1].strip()
                                in_definition = False
                            else:
                                # Multi-line definition starts
                                definition_parts = [definition_text]
                
                elif in_definition:
                    # Continue collecting definition lines
                    if line.endswith('";') or line.endswith('" ;'):
                        # End of definition
                        if line.endswith('";'):
                            definition_parts.append(line[:-2])
                        else:
                            definition_parts.append(line[:-3])
                        concept['definition'] = ' '.join(definition_parts).strip()
                        in_definition = False
                        definition_parts = []
                    elif line.endswith('"'):
                        # End of definition without semicolon
                        definition_parts.append(line[:-1])
                        concept['definition'] = ' '.join(definition_parts).strip()
                        in_definition = False
                        definition_parts = []
                    elif not line.startswith(('skos:', 'cendata:', 'dct:')):
                        # Continuation of definition
                        definition_parts.append(line)
                    else:
                        # Hit another property, end definition
                        concept['definition'] = ' '.join(definition_parts).strip()
                        in_definition = False
                        definition_parts = []
            
            # Finalize any remaining definition
            if in_definition and definition_parts:
                concept['definition'] = ' '.join(definition_parts).strip()
            
            # Clean up and add concept if we have useful data
            if concept['label'] or concept['definition']:
                # Clean up text
                concept['label'] = concept['label'].replace('\\"', '"').strip()
                concept['definition'] = concept['definition'].replace('\\"', '"').strip()
                concept['text_for_embedding'] = f"{concept['label']}. {concept['definition']}".strip()
                concepts.append(concept)
        
        logger.info(f"Extracted {len(concepts)} backbone concepts")
        
        if len(concepts) == 0:
            logger.warning("No concepts extracted - showing first few concept blocks:")
            for i, block in enumerate(blocks[1:6]):  # Show first 5 concept blocks
                logger.warning(f"Block {i+1}: {block[:200]}...")
        else:
            logger.info(f"Sample concept: {concepts[0]['id']} - {concepts[0]['label'][:50]}...")
                        
        return concepts
    
    def load_variables(self) -> List[Dict]:
        """Load enriched variables from consolidated JSON"""
        logger.info(f"Loading variables from {self.variables_path}")
        
        if not self.variables_path.exists():
            raise FileNotFoundError(f"Variables file not found: {self.variables_path}")
        
        with open(self.variables_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both direct format and nested "variables" key
        if 'variables' in data:
            variables_dict = data['variables']
        else:
            variables_dict = data
        
        variables = []
        
        for var_id, var_data in variables_dict.items():
            # Extract the best available description for embedding
            description = self._get_best_description(var_data)
            
            if description and len(description.strip()) > 10:  # Minimum description length
                variables.append({
                    'id': var_id,
                    'label': var_data.get('label', ''),
                    'description': description,
                    'quality_tier': var_data.get('quality_tier', 'unknown'),
                    'source_type': var_data.get('source_type', 'unknown'),
                    'text_for_embedding': f"{var_data.get('label', '')}. {description}".strip()
                })
        
        logger.info(f"Loaded {len(variables)} variables with valid descriptions")
        
        if len(variables) == 0:
            logger.warning("No variables loaded - checking data structure:")
            logger.warning(f"Top-level keys: {list(data.keys())}")
            if 'variables' in data:
                sample_vars = list(data['variables'].items())[:3]
                for var_id, var_data in sample_vars:
                    logger.warning(f"Sample variable {var_id}: {list(var_data.keys())}")
        
        return variables
    
    def _get_best_description(self, var_data: Dict) -> str:
        """Extract the best available description from variable data"""
        # Based on concept_weight_extractor.py - check for enrichment_text field first
        
        # Direct enrichment_text field (from consolidated universe)
        if var_data.get('enrichment_text'):
            return var_data.get('enrichment_text')
        
        # Concept field
        if var_data.get('concept'):
            return var_data.get('concept')
        
        # Label field
        if var_data.get('label'):
            return var_data.get('label')
        
        # Nested enrichment structure (fallback)
        enrichment = var_data.get('enrichment', {})
        if enrichment.get('analysis'):
            return enrichment.get('analysis')
        
        if enrichment.get('enhanced_description'):
            return enrichment.get('enhanced_description')
        
        # Legacy nested analysis structures
        for analysis_key in ['coos_analysis', 'bulk_analysis', 'early_analysis']:
            if analysis_key in var_data:
                analysis = var_data[analysis_key]
                if isinstance(analysis, dict) and 'enhanced_description' in analysis:
                    return analysis['enhanced_description']
        
        # Fallback to original description
        return var_data.get('description', '')
    
    def _progress_update(self, current: int, total: int, batch_stats: Dict = None):
        """Update progress on same line (from concept_weight_extractor)"""
        percentage = (current / total) * 100
        progress_bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
        
        stats_str = ""
        if batch_stats:
            avg_links = batch_stats.get('avg_links', 0)
            max_links = batch_stats.get('max_links', 0)
            zero_links = batch_stats.get('zero_links', 0)
            stats_str = f" | Avg: {avg_links:.1f} | Max: {max_links} | Zero: {zero_links}"
        
        # Use \r to overwrite the same line
        print(f"\r🔄 [{progress_bar}] {current:,}/{total:,} ({percentage:.1f}%){stats_str}", end='', flush=True)
    
    def _save_checkpoint(self, processed_index: int, processed_links: List[Dict]):
        """Save checkpoint data"""
        checkpoint = {
            'processed_index': processed_index,
            'processed_links': processed_links,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def _load_checkpoint(self) -> Tuple[int, List[Dict]]:
        """Load checkpoint data if exists"""
        if self.checkpoint_path.exists():
            logger.info("Loading checkpoint...")
            with open(self.checkpoint_path, 'r') as f:
                checkpoint = json.load(f)
            
            return checkpoint.get('processed_index', -1), checkpoint.get('processed_links', [])
        
        return -1, []
    
    def compute_embeddings(self) -> None:
        """Compute embeddings for concepts and variables with caching"""
        
        # Check for cached embeddings
        if self.cache_path.exists():
            logger.info("Loading cached embeddings...")
            with open(self.cache_path, 'rb') as f:
                cache = pickle.load(f)
                
            # Verify cache validity
            if (len(cache.get('concept_embeddings', [])) == len(self.backbone_concepts) and
                len(cache.get('variable_embeddings', [])) == len(self.variables)):
                
                self.concept_embeddings = np.array(cache['concept_embeddings'])
                self.variable_embeddings = np.array(cache['variable_embeddings'])
                logger.info("Using cached embeddings")
                return
        
        logger.info("Computing fresh embeddings...")
        
        # Compute concept embeddings
        concept_texts = [c['text_for_embedding'] for c in self.backbone_concepts]
        logger.info(f"Computing embeddings for {len(concept_texts)} concepts...")
        self.concept_embeddings = self.model.encode(concept_texts, batch_size=32, show_progress_bar=True)
        
        # Compute variable embeddings in batches
        variable_texts = [v['text_for_embedding'] for v in self.variables]
        logger.info(f"Computing embeddings for {len(variable_texts)} variables...")
        self.variable_embeddings = self.model.encode(variable_texts, batch_size=EMBED_BATCH_SIZE, show_progress_bar=True)
        
        # Cache embeddings
        logger.info("Caching embeddings for future use...")
        cache = {
            'concept_embeddings': self.concept_embeddings.tolist(),
            'variable_embeddings': self.variable_embeddings.tolist(),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.cache_path, 'wb') as f:
            pickle.dump(cache, f)
        
        logger.info("Embeddings computed and cached")
    
    def compute_similarities_and_links(self) -> List[Dict]:
        """Compute similarities and generate variable-concept links with checkpointing"""
        logger.info("Computing similarities and generating links...")
        
        # Load checkpoint if exists
        last_processed_index, existing_links = self._load_checkpoint()
        start_index = last_processed_index + 1
        
        if start_index > 0:
            logger.info(f"Resuming from variable {start_index:,} (checkpoint found)")
        
        # Compute cosine similarities: variables x concepts (batched processing)
        all_links = existing_links.copy()
        variables_with_links = len(set(link['variable_id'] for link in existing_links))
        
        total_variables = len(self.variables)
        
        # Process in batches for memory efficiency
        for batch_start in range(start_index, total_variables, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_variables)
            batch_variables = self.variables[batch_start:batch_end]
            
            # Get embeddings for this batch
            batch_var_embeddings = self.variable_embeddings[batch_start:batch_end]
            
            # Compute similarities for this batch
            similarities_batch = cosine_similarity(batch_var_embeddings, self.concept_embeddings)
            
            # Process each variable in the batch
            batch_links = []
            batch_stats = {'avg_links': 0, 'max_links': 0, 'zero_links': 0}
            links_count = []
            
            for i, variable in enumerate(batch_variables):
                var_similarities = similarities_batch[i]
                
                # Find concepts above threshold
                above_threshold = np.where(var_similarities >= SIMILARITY_THRESHOLD)[0]
                
                if len(above_threshold) == 0:
                    batch_stats['zero_links'] += 1
                    links_count.append(0)
                    continue
                
                # Sort by similarity and take top N
                sorted_indices = above_threshold[np.argsort(-var_similarities[above_threshold])]
                top_concepts = sorted_indices[:MAX_CONCEPTS_PER_VARIABLE]
                
                # Create links for this variable
                variable_links = []
                for concept_idx in top_concepts:
                    similarity = var_similarities[concept_idx]
                    concept = self.backbone_concepts[concept_idx]
                    
                    link = {
                        'variable_id': variable['id'],
                        'concept_id': concept['id'],
                        'concept_label': concept['label'],
                        'similarity': float(similarity),
                        'weight': float(similarity)  # Use similarity as weight
                    }
                    
                    variable_links.append(link)
                    self.stats['similarity_distribution'].append(float(similarity))
                
                # Normalize weights to sum to 1.0
                total_weight = sum(link['weight'] for link in variable_links)
                if total_weight > 0:
                    for link in variable_links:
                        link['normalized_weight'] = link['weight'] / total_weight
                
                batch_links.extend(variable_links)
                links_count.append(len(variable_links))
                variables_with_links += 1
            
            # Update batch statistics
            if links_count:
                batch_stats['avg_links'] = np.mean(links_count)
                batch_stats['max_links'] = np.max(links_count)
            
            # Add to all links
            all_links.extend(batch_links)
            
            # Save checkpoint every batch
            self._save_checkpoint(batch_end - 1, all_links)
            
            # Progress update
            self._progress_update(batch_end, total_variables, batch_stats)
        
        print()  # New line after progress bar
        
        # Update final statistics
        self.stats['total_variables'] = len(self.variables)
        self.stats['variables_linked'] = variables_with_links
        self.stats['variables_unlinked'] = len(self.variables) - variables_with_links
        self.stats['total_links'] = len(all_links)
        self.stats['avg_concepts_per_variable'] = len(all_links) / max(variables_with_links, 1)
        
        logger.info(f"Generated {len(all_links)} links for {variables_with_links} variables")
        
        return all_links
    
    def generate_ttl_output(self, links: List[Dict]) -> None:
        """Generate TTL file with variable-concept links"""
        logger.info(f"Generating TTL output: {self.output_path}")
        
        # TTL header
        ttl_content = f"""# Variable-Concept Links - Generated {datetime.now().isoformat()}
# Links 36K ACS variables to 160 backbone concepts via semantic similarity

@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix cendata: <https://example.org/cendata/> .

# Link predicates
cendata:hasConcept a owl:ObjectProperty ;
    rdfs:label "has concept" ;
    rdfs:comment "Links a variable to a backbone concept" .

cendata:conceptWeight a owl:DatatypeProperty ;
    rdfs:label "concept weight" ;
    rdfs:comment "Semantic similarity weight between variable and concept" ;
    rdfs:range xsd:decimal .

cendata:conceptWeightNormalized a owl:DatatypeProperty ;
    rdfs:label "normalized concept weight" ;
    rdfs:comment "Concept weight normalized so all weights for a variable sum to 1.0" ;
    rdfs:range xsd:decimal .

# Variable-concept links

"""
        
        # Group links by variable for cleaner output
        links_by_variable = {}
        for link in links:
            var_id = link['variable_id']
            if var_id not in links_by_variable:
                links_by_variable[var_id] = []
            links_by_variable[var_id].append(link)
        
        # Generate TTL for each variable
        for var_id, var_links in links_by_variable.items():
            ttl_content += f"cendata:{var_id}\n"
            
            # Add concept links
            for i, link in enumerate(var_links):
                ttl_content += f"    cendata:hasConcept cendata:{link['concept_id']} ;\n"
                ttl_content += f"    cendata:conceptWeight \"{link['weight']:.4f}\"^^xsd:decimal ;\n"
                ttl_content += f"    cendata:conceptWeightNormalized \"{link['normalized_weight']:.4f}\"^^xsd:decimal"
                
                if i < len(var_links) - 1:
                    ttl_content += " ;\n"
                else:
                    ttl_content += " .\n\n"
        
        # Write output file
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(ttl_content)
        
        logger.info(f"TTL output written: {self.output_path.stat().st_size:,} bytes")
    
    def generate_summary_report(self) -> None:
        """Generate summary statistics and report"""
        logger.info("\n📊 Variable-Concept Linking Summary:")
        logger.info(f"   Total variables processed: {self.stats['total_variables']:,}")
        logger.info(f"   Variables with links: {self.stats['variables_linked']:,}")
        logger.info(f"   Variables without links: {self.stats['variables_unlinked']:,}")
        logger.info(f"   Link coverage: {self.stats['variables_linked']/self.stats['total_variables']*100:.1f}%")
        logger.info(f"   Total concept links: {self.stats['total_links']:,}")
        logger.info(f"   Average concepts per variable: {self.stats['avg_concepts_per_variable']:.2f}")
        
        if self.stats['similarity_distribution']:
            similarities = np.array(self.stats['similarity_distribution'])
            logger.info(f"   Similarity distribution:")
            logger.info(f"     Min: {similarities.min():.3f}")
            logger.info(f"     Mean: {similarities.mean():.3f}")
            logger.info(f"     Max: {similarities.max():.3f}")
            logger.info(f"     Median: {np.median(similarities):.3f}")
    
    def run_linking_pipeline(self) -> None:
        """Execute the complete variable-concept linking pipeline"""
        logger.info("🚀 Starting Variable-Concept Linking Pipeline (Step 3-B)")
        
        try:
            # Load data
            self.backbone_concepts = self.extract_backbone_concepts()
            self.variables = self.load_variables()
            
            if len(self.backbone_concepts) == 0:
                raise ValueError("No backbone concepts loaded")
            
            if len(self.variables) == 0:
                raise ValueError("No variables loaded")
            
            # Compute embeddings
            self.compute_embeddings()
            
            # Generate links
            links = self.compute_similarities_and_links()
            
            # Generate output
            self.generate_ttl_output(links)
            
            # Generate summary report
            self.generate_summary_report()
            
            # Clean up checkpoint
            if self.checkpoint_path.exists():
                self.checkpoint_path.unlink()
                logger.info("Checkpoint file cleaned up")
            
            logger.info("\n🎯 Next steps:")
            logger.info("   1. Load variable_links.ttl into your graph store")
            logger.info("   2. Test concept-based variable retrieval queries")
            logger.info("   3. Integrate with existing cendata-extension-complete.ttl")
            logger.info("   4. Implement probabilistic concept weighting in search")
            
            logger.info(f"\n✅ Variable-Concept Linking Complete!")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise

def main():
    """Main execution function"""
    linker = VariableConceptLinker()
    linker.run_linking_pipeline()

if __name__ == "__main__":
    main()
