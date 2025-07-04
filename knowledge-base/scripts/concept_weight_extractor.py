#!/usr/bin/env python3

import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
import time
import sys
from datetime import datetime

# Set up logging with minimal noise
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CategoryWeightExtractor:
    def __init__(self, ontology_file: str, universe_file: str, output_file: str = None, batch_size: int = 100, embed_batch_size: int = 50):
        self.ontology_file = ontology_file
        self.universe_file = universe_file
        self.output_file = output_file or "2023_ACS_Enriched_Universe_With_Category_Weights.json"
        self.batch_size = batch_size  # Checkpoint batch size
        self.embed_batch_size = embed_batch_size  # Embedding batch size
        self.checkpoint_file = f"{Path(self.output_file).stem}_checkpoint.json"
        self.weight_threshold = 0.05  # 5% minimum threshold
        
        # Define the 8 categories
        self.categories = [
            'core_demographics',
            'economics',
            'education',
            'geography',
            'health_social',
            'housing',
            'specialized_populations',
            'transportation'
        ]
        
        # Load model
        logger.info("Loading sentence transformer model...")
        self.model = SentenceTransformer('sentence-transformers/all-roberta-large-v1')
        logger.info("✅ Model loaded successfully")
        
        # Load and prepare category concepts
        self.category_concepts = self._load_and_group_concepts()
        self.category_embeddings = self._get_category_embeddings()
        
        # Load universe data
        self.universe_data = self._load_universe_data()
        
        logger.info(f"Loaded {len(self.categories)} categories and {len(self.universe_data)} variables")
    
    def _load_and_group_concepts(self) -> Dict[str, List[Dict]]:
        """Load concepts and group by category"""
        with open(self.ontology_file, 'r') as f:
            ontology = json.load(f)
        
        # Group concepts by category
        category_concepts = {cat: [] for cat in self.categories}
        
        # Get approved concepts
        for concept in ontology.get('approved_concepts', []):
            category = concept.get('category', '').lower()
            if category in category_concepts:
                category_concepts[category].append(concept)
        
        # Get modified concepts
        for concept in ontology.get('modified_concepts', []):
            category = concept.get('category', '').lower()
            if category in category_concepts:
                category_concepts[category].append(concept)
        
        # Log category sizes
        for cat, concepts in category_concepts.items():
            logger.info(f"  {cat}: {len(concepts)} concepts")
        
        return category_concepts
    
    def _get_category_embeddings(self) -> Dict[str, np.ndarray]:
        """Generate embeddings for each category by combining concept texts"""
        category_embeddings = {}
        
        for category, concepts in self.category_concepts.items():
            if not concepts:
                logger.warning(f"No concepts found for category: {category}")
                continue
            
            # Combine all concept texts for this category
            category_texts = []
            for concept in concepts:
                text_parts = [
                    concept.get('label', ''),
                    concept.get('definition', ''),
                    concept.get('universe', '')
                ]
                concept_text = ' | '.join([part for part in text_parts if part])
                category_texts.append(concept_text)
            
            # Create comprehensive category text by combining all concepts
            combined_category_text = ' || '.join(category_texts)
            
            # Generate embedding for this category
            category_embedding = self.model.encode([combined_category_text])
            category_embeddings[category] = category_embedding[0]
            
            logger.info(f"Generated embedding for {category} ({len(concepts)} concepts)")
        
        return category_embeddings
    
    def _load_universe_data(self) -> List[Dict]:
        """Load and normalize universe data structure"""
        with open(self.universe_file, 'r') as f:
            universe_data = json.load(f)
        
        # Handle both formats: direct array or metadata wrapper
        if isinstance(universe_data, list):
            return universe_data
        elif isinstance(universe_data, dict):
            # Check for 'variables' key (consolidated format)
            if 'variables' in universe_data:
                variables_data = universe_data['variables']
                if isinstance(variables_data, list):
                    return variables_data
                elif isinstance(variables_data, dict):
                    # Convert dict of variables to list, preserving variable names
                    result = []
                    for var_name, var_data in variables_data.items():
                        var_record = var_data.copy()
                        # Ensure the variable has a name field
                        if 'name' not in var_record:
                            var_record['name'] = var_name
                        if 'variable_id' not in var_record:
                            var_record['variable_id'] = var_name
                        result.append(var_record)
                    return result
                else:
                    raise ValueError(f"'variables' key contains unexpected type: {type(variables_data)}")
            else:
                raise ValueError(f"Unknown universe file format. Keys: {list(universe_data.keys())[:10]}")
        else:
            raise ValueError(f"Unexpected universe file format: {type(universe_data)}")
    
    def _extract_analysis_text_batch(self, variables: List[Dict]) -> List[str]:
        """Extract analysis text from batch of variables"""
        analysis_texts = []
        
        for variable in variables:
            text_parts = []
            
            # Get enrichment analysis
            enrichment = variable.get('enrichment', {})
            if enrichment.get('analysis'):
                text_parts.append(enrichment.get('analysis'))
            
            if enrichment.get('methodology_notes'):
                text_parts.append(enrichment.get('methodology_notes'))
            
            if enrichment.get('statistical_notes'):
                text_parts.append(enrichment.get('statistical_notes'))
            
            # Get enrichment_text field (from your data structure)
            if variable.get('enrichment_text'):
                text_parts.append(variable.get('enrichment_text'))
            
            # Get basic variable info
            if variable.get('label'):
                text_parts.append(variable.get('label'))
            
            if variable.get('concept'):
                text_parts.append(variable.get('concept'))
            
            # Convert all parts to strings and filter out None/empty values
            clean_text_parts = [str(part) for part in text_parts if part is not None and str(part).strip()]
            analysis_text = ' | '.join(clean_text_parts) if clean_text_parts else ""
            analysis_texts.append(analysis_text)
        
        return analysis_texts
    

    def _compute_category_weights_batch(
            self,
            analysis_texts: List[str]
    ) -> Tuple[List[Dict[str, float]], List[Dict[str, float]]]:
        """
        For a batch of variable-level texts:
        • produce two parallel lists:
            1. linear-normalised category weights
            2. log-normalised ("winner-takes-most") weights
        Each element i of both lists corresponds to analysis_texts[i].
        Empty / whitespace texts yield empty dicts in both lists.
        """
        # ---- 1. collect only non-empty texts ----
        valid_texts, valid_idx = [], []
        for idx, txt in enumerate(analysis_texts):
            if txt.strip():
                valid_texts.append(txt)
                valid_idx.append(idx)

        # Pre-fill results with empty dicts (for the blanks we skipped)
        linear_out = [{} for _ in analysis_texts]
        log_out    = [{} for _ in analysis_texts]

        if not valid_texts:          # nothing to do
            return linear_out, log_out

        # ---- 2. embeddings  ----
        text_embs = self.model.encode(
            valid_texts,
            show_progress_bar=False,
            batch_size=self.embed_batch_size
        )

        cat_emb_mat = np.stack([self.category_embeddings[c] for c in self.categories])
        sims_batch  = cosine_similarity(text_embs, cat_emb_mat)   # shape: (batch, 8)

        # ---- 3. turn similarities into weights ----
        eps = 1e-8
        for row_idx, sims in enumerate(sims_batch):
            # a) clip negatives (cosine can be −1…1)
            sims = np.clip(sims, 0, None)

            # b) linear weights --------------------------------------------------
            lin = sims / (sims.sum() + eps)                  # normalise to 1
            lin = {cat: float(w) for cat, w in zip(self.categories, lin)}
            lin = {k: v for k, v in lin.items() if v >= self.weight_threshold}
            if not lin:                                      # make sure ≥1 cat
                best = int(np.argmax(sims))
                lin = {self.categories[best]: 1.0}
            else:
                tot = sum(lin.values())
                lin = {k: v / tot for k, v in lin.items()}

            # c) log-weights -----------------------------------------------------
            logw = np.log1p(sims)                            # log(1+v)
            logw = logw / (logw.sum() + eps)
            logw = {cat: float(w) for cat, w in zip(self.categories, logw)}
            logw = {k: v for k, v in logw.items() if v >= self.weight_threshold}
            if not logw:
                best = int(np.argmax(sims))
                logw = {self.categories[best]: 1.0}
            else:
                tot = sum(logw.values())
                logw = {k: v / tot for k, v in logw.items()}

            # d) write back in the right slot
            original_idx = valid_idx[row_idx]
            linear_out[original_idx] = lin
            log_out[original_idx]    = logw

        return linear_out, log_out

    
    def _load_checkpoint(self) -> Tuple[int, List[Dict]]:
        """Load checkpoint if exists"""
        if Path(self.checkpoint_file).exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                
                last_processed = checkpoint.get('last_processed_index', -1)
                processed_variables = checkpoint.get('processed_variables', [])
                
                logger.info(f"📂 Resuming from checkpoint: {last_processed + 1:,}/{len(self.universe_data):,} variables")
                return last_processed, processed_variables
                
            except Exception as e:
                logger.warning(f"Error loading checkpoint: {e}")
                return -1, []
        
        return -1, []
    
    def _save_checkpoint(self, last_processed_index: int, processed_variables: List[Dict]):
        """Save checkpoint"""
        checkpoint = {
            'last_processed_index': last_processed_index,
            'processed_variables': processed_variables,
            'timestamp': datetime.now().isoformat(),
            'total_variables': len(self.universe_data),
            'categories': self.categories,
            'weight_threshold': self.weight_threshold
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def _save_final_results(self, processed_variables: List[Dict]):
        """Save final enriched universe with category weights"""
        
        # Check if output file already exists
        if Path(self.output_file).exists():
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{Path(self.output_file).stem}_backup_{timestamp}.json"
            logger.info(f"📁 Output file exists, creating backup: {backup_file}")
            Path(self.output_file).rename(backup_file)
        
        final_results = {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'source_universe_file': self.universe_file,
                'source_ontology_file': self.ontology_file,
                'sentence_transformer_model': 'sentence-transformers/all-roberta-large-v1',
                'total_variables': len(processed_variables),
                'categories': self.categories,
                'processing_batch_size': self.batch_size,
                'embed_batch_size': self.embed_batch_size,
                'weight_threshold': self.weight_threshold,
                '                weight_approach': '8_category_dual_normalization'
            },
            'variables': processed_variables
        }
        
        with open(self.output_file, 'w') as f:
            json.dump(final_results, f, indent=2)
        
        logger.info(f"✅ Final results saved to: {self.output_file}")
        
        # Clean up checkpoint
        if Path(self.checkpoint_file).exists():
            Path(self.checkpoint_file).unlink()
    
    def _progress_update(self, current: int, total: int, batch_stats: Dict = None):
        """Update progress on same line"""
        percentage = (current / total) * 100
        progress_bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
        
        stats_str = ""
        if batch_stats:
            avg_categories = batch_stats.get('avg_categories', 0)
            max_categories = batch_stats.get('max_categories', 0)
            zero_categories = batch_stats.get('zero_categories', 0)
            stats_str = f" | Avg: {avg_categories:.1f} | Max: {max_categories} | Zero: {zero_categories}"
        
        # Use \r to overwrite the same line
        print(f"\r🔄 [{progress_bar}] {current:,}/{total:,} ({percentage:.1f}%){stats_str}", end='', flush=True)
    
    def extract_weights(self):
        """Main extraction process with optimized batch processing"""
        
        # Load checkpoint if exists
        last_processed_index, processed_variables = self._load_checkpoint()
        start_index = last_processed_index + 1
        
        # Initialize processed_variables as a dict for efficient lookups if resuming
        processed_dict = {var.get('name', var.get('variable_id', f'var_{i}')): var
                         for i, var in enumerate(processed_variables)}
        
        total_variables = len(self.universe_data)
        remaining = total_variables - start_index
        
        logger.info(f"🎯 Starting category weight extraction from index {start_index:,}")
        logger.info(f"📊 Processing {remaining:,} remaining variables in batches of {self.embed_batch_size}")
        logger.info(f"🎛️  Weight threshold: {self.weight_threshold} (5% minimum)")
        
        # Process in batches
        for batch_start in range(start_index, total_variables, self.embed_batch_size):
            batch_end = min(batch_start + self.embed_batch_size, total_variables)
            batch_variables = self.universe_data[batch_start:batch_end]
            
            # Skip already processed variables
            new_batch_variables = []
            new_batch_indices = []
            for i, variable in enumerate(batch_variables):
                variable_name = variable.get('name') or variable.get('variable_id', f'var_{batch_start + i}')
                if variable_name not in processed_dict:
                    new_batch_variables.append(variable)
                    new_batch_indices.append(batch_start + i)
            
            if not new_batch_variables:
                # Update progress and continue
                self._progress_update(batch_end, total_variables)
                continue
            
            # Extract analysis texts for batch
            analysis_texts = self._extract_analysis_text_batch(new_batch_variables)
            
            # Compute category weights for batch (vectorized) - returns both linear and log
            linear_weights_batch, log_weights_batch = self._compute_category_weights_batch(analysis_texts)
            
            # Add weights to variables
            batch_stats = {'linear_category_counts': [], 'log_category_counts': []}
            for i, (variable, linear_weights, log_weights) in enumerate(zip(new_batch_variables, linear_weights_batch, log_weights_batch)):
                enriched_variable = variable.copy()
                enriched_variable['category_weights_linear'] = linear_weights
                enriched_variable['category_weights_log'] = log_weights
                enriched_variable['category_weights_metadata'] = {
                    'extracted_at': datetime.now().isoformat(),
                    'num_categories_linear': len(linear_weights),
                    'num_categories_log': len(log_weights),
                    'max_weight_linear': max(linear_weights.values()) if linear_weights else 0.0,
                    'max_weight_log': max(log_weights.values()) if log_weights else 0.0,
                    'weight_threshold': self.weight_threshold,
                    'weight_approach': '8_category_dual_normalization'
                }
                
                # Add to processed list
                processed_variables.append(enriched_variable)
                variable_name = variable.get('name') or variable.get('variable_id', f'var_{new_batch_indices[i]}')
                processed_dict[variable_name] = enriched_variable
                
                # Track stats for both weight types
                batch_stats['linear_category_counts'].append(len(linear_weights))
                batch_stats['log_category_counts'].append(len(log_weights))
            
            # Calculate batch statistics
            if batch_stats['linear_category_counts']:
                batch_stats['avg_categories_linear'] = np.mean(batch_stats['linear_category_counts'])
                batch_stats['avg_categories_log'] = np.mean(batch_stats['log_category_counts'])
                batch_stats['max_categories'] = max(batch_stats['linear_category_counts'])
                batch_stats['zero_categories'] = sum(1 for c in batch_stats['linear_category_counts'] if c == 0)
            
            # Update progress
            self._progress_update(batch_end, total_variables, batch_stats)
            
            # Save checkpoint every batch_size variables
            if (batch_end - start_index) % self.batch_size == 0:
                self._save_checkpoint(batch_end - 1, processed_variables)
        
        # Final newline after progress updates
        print()
        
        # Save final results
        logger.info(f"🎉 Extraction complete! Processed {len(processed_variables):,} variables")
        self._save_final_results(processed_variables)
        
        # Print summary statistics
        self._print_summary_stats(processed_variables)
    
    def _print_summary_stats(self, processed_variables: List[Dict]):
        """Print summary statistics for both weight types"""
        linear_counts = [len(var.get('category_weights_linear', {})) for var in processed_variables]
        log_counts = [len(var.get('category_weights_log', {})) for var in processed_variables]
        linear_max_weights = [var.get('category_weights_metadata', {}).get('max_weight_linear', 0) for var in processed_variables]
        log_max_weights = [var.get('category_weights_metadata', {}).get('max_weight_log', 0) for var in processed_variables]
        
        logger.info(f"\n📊 EXTRACTION SUMMARY (DUAL NORMALIZATION):")
        logger.info(f"   Total variables processed: {len(processed_variables):,}")
        logger.info(f"   LINEAR WEIGHTS:")
        logger.info(f"     Avg categories per variable: {np.mean(linear_counts):.2f}")
        logger.info(f"     Max categories per variable: {max(linear_counts) if linear_counts else 0}")
        logger.info(f"     Variables with 0 categories: {sum(1 for c in linear_counts if c == 0):,}")
        logger.info(f"     Avg max weight per variable: {np.mean(linear_max_weights):.3f}")
        logger.info(f"   LOG WEIGHTS:")
        logger.info(f"     Avg categories per variable: {np.mean(log_counts):.2f}")
        logger.info(f"     Max categories per variable: {max(log_counts) if log_counts else 0}")
        logger.info(f"     Variables with 0 categories: {sum(1 for c in log_counts if c == 0):,}")
        logger.info(f"     Avg max weight per variable: {np.mean(log_max_weights):.3f}")
        logger.info(f"   Weight threshold applied: {self.weight_threshold}")
        
        # Category frequency analysis for both weight types
        linear_frequency = {}
        log_frequency = {}
        linear_total_weights = {}
        log_total_weights = {}
        
        for var in processed_variables:
            # Linear weights
            for category, weight in var.get('category_weights_linear', {}).items():
                linear_frequency[category] = linear_frequency.get(category, 0) + 1
                linear_total_weights[category] = linear_total_weights.get(category, 0) + weight
            
            # Log weights
            for category, weight in var.get('category_weights_log', {}).items():
                log_frequency[category] = log_frequency.get(category, 0) + 1
                log_total_weights[category] = log_total_weights.get(category, 0) + weight
        
        if linear_frequency:
            logger.info(f"\n🏷️  LINEAR CATEGORY DISTRIBUTION:")
            sorted_linear = sorted(linear_frequency.items(), key=lambda x: x[1], reverse=True)
            for category, count in sorted_linear:
                avg_weight = linear_total_weights[category] / count if count > 0 else 0
                percentage = (count / len(processed_variables)) * 100
                logger.info(f"   {category}: {count:,} variables ({percentage:.1f}%) | Avg weight: {avg_weight:.3f}")
        
        if log_frequency:
            logger.info(f"\n🔥 LOG CATEGORY DISTRIBUTION:")
            sorted_log = sorted(log_frequency.items(), key=lambda x: x[1], reverse=True)
            for category, count in sorted_log:
                avg_weight = log_total_weights[category] / count if count > 0 else 0
                percentage = (count / len(processed_variables)) * 100
                logger.info(f"   {category}: {count:,} variables ({percentage:.1f}%) | Avg weight: {avg_weight:.3f}")

def main():
    parser = argparse.ArgumentParser(description='Extract category weights from enriched universe using 8-category semantic similarity')
    parser.add_argument('--ontology-file', required=True, help='Path to unified ontology file (COOS_Complete_Ontology.json)')
    parser.add_argument('--universe-file', required=True, help='Path to enriched universe file (2023_ACS_Enriched_Universe.json)')
    parser.add_argument('--output', help='Output file path (default: 2023_ACS_Enriched_Universe_With_Category_Weights.json)')
    parser.add_argument('--batch-size', type=int, default=100, help='Checkpoint batch size (default: 100)')
    parser.add_argument('--embed-batch-size', type=int, default=50, help='Embedding batch size (default: 50)')
    parser.add_argument('--weight-threshold', type=float, default=0.05, help='Minimum weight threshold (default: 0.05)')
    
    args = parser.parse_args()
    
    # Validate input files exist
    if not Path(args.ontology_file).exists():
        raise FileNotFoundError(f"Ontology file not found: {args.ontology_file}")
    
    if not Path(args.universe_file).exists():
        raise FileNotFoundError(f"Universe file not found: {args.universe_file}")
    
    # Initialize and run extractor
    extractor = CategoryWeightExtractor(
        ontology_file=args.ontology_file,
        universe_file=args.universe_file,
        output_file=args.output,
        batch_size=args.batch_size,
        embed_batch_size=args.embed_batch_size
    )
    
    # Set weight threshold
    extractor.weight_threshold = args.weight_threshold
    
    logger.info(f"🚀 Starting 8-category weight extraction...")
    logger.info(f"📁 Input ontology: {args.ontology_file}")
    logger.info(f"📁 Input universe: {args.universe_file}")
    logger.info(f"📁 Output file: {extractor.output_file}")
    logger.info(f"📦 Embed batch size: {args.embed_batch_size}")
    logger.info(f"💾 Checkpoint batch size: {args.batch_size}")
    logger.info(f"🎯 Weight threshold: {args.weight_threshold} (5% minimum)")
    
    start_time = time.time()
    extractor.extract_weights()
    end_time = time.time()
    
    logger.info(f"⏱️  Total processing time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
