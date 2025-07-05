#!/usr/bin/env python3
"""
subject_categorizer_weighted.py - PASS 2 (Robust Production Version)
Assign weighted multi-domain scores to subject definitions using established COOS architecture

Features:
- Checkpoint/resume capability  
- Exponential backoff retry logic
- Environment variable API keys
- Progress tracking with ETA
- Comprehensive error handling
- Timestamped backups

Usage:
    python knowledge-base/scripts/subject_categorizer_weighted.py [--resume]
"""

import json
import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tqdm import tqdm

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# LLM clients
from openai import OpenAI
import anthropic

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - CATEGORIZER - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 8 target domains (7 non-geo + geography for spatial methodology)
DOMAINS = [
    "core_demographics",
    "economics",
    "education",
    "geography",
    "health_social",
    "housing",
    "specialized_populations",
    "transportation"
]

class WeightedSubjectCategorizer:
    """
    Production-grade subject definition categorizer with robust error handling.
    
    Features:
    - Checkpoint/resume for safe restarts
    - Exponential backoff for API reliability
    - Dual-model validation (GPT-4.1-mini + Claude Sonnet 4)
    - Progress tracking with ETA
    - Comprehensive error handling
    """
    
    def __init__(self, resume: bool = False):
        """Initialize the categorizer with production settings"""
        
        # API clients with environment variables
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # File paths
        self.input_path = Path("knowledge-base/concepts/census_backbone_definitions.json")
        self.output_path = Path("knowledge-base/concepts/subject_definitions_weighted.json")
        self.checkpoint_path = Path("knowledge-base/concepts/categorizer_checkpoint.json")
        
        # Processing state
        self.resume = resume
        self.processed_count = 0
        self.total_count = 0
        self.start_time = None
        
        # Validate setup
        self._validate_setup()
        
    def _validate_setup(self):
        """Validate API keys and file paths"""
        
        # Check API keys
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        if not os.getenv('ANTHROPIC_API_KEY'):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
        # Check input file
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_path}")
            
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ Setup validation complete")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((Exception,))
    )
    def _get_gpt_weights(self, concept_id: str, label: str, definition: str) -> Tuple[Dict[str, float], str, str]:
        """Get domain weights from GPT-4.1-mini with retry logic"""
        
        prompt = f"""You are classifying American Community Survey (ACS) concept definitions
into RELEVANCE WEIGHTS across the following analytic domains
(max 4 domains per concept, weights must sum to 1.0):

• core_demographics
• economics
• education
• health_social
• housing
• specialized_populations
• transportation
• geography   ← (treat as spatial-methodology, not topical content)

For the given definition, return JSON:
{{
  "concept_id": "{concept_id}",
  "label": "{label}",
  "domain_weights": {{
      "<domain>": <weight_float>, ...
  }}
}}

Rules:
1. Include only domains with weight ≥ 0.05.
2. Use at most 4 domains.
3. Normalize weights so total exactly 1.0.
4. Do NOT add extra keys.

CONCEPT TO CLASSIFY:
Label: {label}
Definition: {definition[:500]}...
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                weights = result.get('domain_weights', {"core_demographics": 1.0})
                return weights, prompt, response.id
            else:
                logger.warning(f"Could not parse JSON from GPT response for {concept_id}")
                return {"core_demographics": 1.0}, prompt, getattr(response, 'id', 'unknown')
                
        except Exception as e:
            logger.error(f"GPT API error for {concept_id}: {e}")
            raise e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((Exception,))
    )
    def _get_claude_weights(self, concept_id: str, label: str, definition: str, gpt_weights: Dict[str, float]) -> Dict[str, float]:
        """Get refined weights from Claude Sonnet 4 with retry logic"""
        
        prompt = f"""Review and, if necessary, adjust these domain weights following the same rules:

Original GPT weights: {json.dumps(gpt_weights, indent=2)}

Rules:
1. Include only domains with weight ≥ 0.05
2. Use at most 4 domains  
3. Normalize weights so total exactly 1.0
4. Return only JSON, no commentary

Available domains: core_demographics, economics, education, health_social, housing, specialized_populations, transportation, geography

CONCEPT:
Label: {label}
Definition: {definition[:500]}...

Return JSON:
{{
  "domain_weights": {{
      "<domain>": <weight_float>, ...
  }}
}}"""

        try:
            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = message.content[0].text.strip()
            
            # Strip potential code block fences and parse JSON
            cleaned_text = result_text.lstrip("```json").rstrip("```").strip()
            result = json.loads(cleaned_text)
            return result.get('domain_weights', gpt_weights)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing error in Claude response for {concept_id}: {e}, using GPT weights")
            return gpt_weights
                
        except Exception as e:
            logger.error(f"Claude API error for {concept_id}: {e}, using GPT weights")
            return gpt_weights

    def _validate_and_normalize_weights(self, weights: Dict[str, float], concept_id: str) -> Dict[str, float]:
        """Validate and normalize domain weights"""
        
        # Filter valid domains and weights ≥ 0.05
        valid_weights = {}
        for domain, weight in weights.items():
            if domain in DOMAINS and weight >= 0.05:
                valid_weights[domain] = float(weight)
        
        # If nothing survives the cut, keep the single highest weight
        if not valid_weights:
            if weights:
                max_domain = max(weights.items(), key=lambda x: x[1] if x[0] in DOMAINS else 0)
                if max_domain[0] in DOMAINS:
                    valid_weights = {max_domain[0]: 1.0}
                    logger.warning(f"No weights ≥0.05 for {concept_id}, using highest: {max_domain[0]}")
                else:
                    # Last resort: assign to core_demographics
                    valid_weights = {"core_demographics": 1.0}
                    logger.warning(f"No valid domains for {concept_id}, defaulting to core_demographics")
            else:
                valid_weights = {"core_demographics": 1.0}
                logger.warning(f"Empty weights for {concept_id}, defaulting to core_demographics")
        
        # Keep top 4 if more than 4 domains
        if len(valid_weights) > 4:
            sorted_weights = sorted(valid_weights.items(), key=lambda x: x[1], reverse=True)
            valid_weights = dict(sorted_weights[:4])
        
        # Normalize to sum to 1.0
        total = sum(valid_weights.values())
        if total > 0:
            normalized = {k: v/total for k, v in valid_weights.items()}
        else:
            # This should never happen given the logic above, but just in case
            normalized = {"core_demographics": 1.0}
        
        # Validate sum is close to 1.0
        weight_sum = sum(normalized.values())
        if abs(weight_sum - 1.0) > 1e-6:
            logger.warning(f"Weights for {concept_id} sum to {weight_sum}, not 1.0")
        
        return normalized

    def _process_single_definition(self, definition: Dict) -> Dict:
        """Process a single definition through both models"""
        
        concept_id = definition['concept_id']
        label = definition['label']
        definition_text = definition['definition']
        
        try:
            # Stage 1: GPT-4.1-mini
            gpt_weights, gpt_prompt, gpt_response_id = self._get_gpt_weights(concept_id, label, definition_text)
            time.sleep(0.1)  # Rate limiting
            
            # Skip Claude if GPT already produced valid results
            if (len(gpt_weights) <= 4 and
                abs(sum(gpt_weights.values()) - 1.0) < 1e-6 and
                all(domain in DOMAINS for domain in gpt_weights.keys())):
                
                final_weights = self._validate_and_normalize_weights(gpt_weights, concept_id)
                
                # Return with GPT-only processing
                return {
                    **definition,
                    'domain_weights': final_weights,
                    'gpt_weights': gpt_weights,
                    'categorization_method': 'gpt_only_valid',
                    'models_used': ['gpt-4.1-mini'],
                    'processed_at': datetime.now().isoformat(),
                    'gpt_prompt': gpt_prompt[:400],  # Truncated audit trail
                    'gpt_response_id': gpt_response_id
                }
            
            # Stage 2: Claude Sonnet 4 refinement
            claude_weights = self._get_claude_weights(concept_id, label, definition_text, gpt_weights)
            time.sleep(0.2)  # Rate limiting
            
            # Validate and normalize final weights
            final_weights = self._validate_and_normalize_weights(claude_weights, concept_id)
            
            # Add weights to definition
            enhanced_definition = {
                **definition,
                'domain_weights': final_weights,
                'gpt_weights': gpt_weights,  # Keep for comparison
                'categorization_method': 'dual_model_weighted',
                'models_used': ['gpt-4.1-mini', 'claude-sonnet-4-20250514'],
                'processed_at': datetime.now().isoformat(),
                'gpt_prompt': gpt_prompt[:400],  # Truncated audit trail
                'gpt_response_id': gpt_response_id
            }
            
            return enhanced_definition
            
        except Exception as e:
            logger.error(f"Error processing {concept_id}: {e}")
            # Return with fallback weights
            return {
                **definition,
                'domain_weights': {"core_demographics": 1.0},  # No more "other"
                'categorization_method': 'error_fallback',
                'error_message': str(e),
                'processed_at': datetime.now().isoformat()
            }

    def _load_checkpoint(self) -> Tuple[int, List[Dict]]:
        """Load checkpoint if exists"""
        
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, 'r') as f:
                    checkpoint = json.load(f)
                
                last_processed = checkpoint.get('last_processed_index', -1)
                processed_definitions = checkpoint.get('processed_definitions', [])
                
                logger.info(f"📂 Resuming from checkpoint: {last_processed + 1:,} definitions processed")
                return last_processed, processed_definitions
                
            except Exception as e:
                logger.warning(f"Error loading checkpoint: {e}")
                return -1, []
        
        return -1, []

    def _save_checkpoint(self, last_processed_index: int, processed_definitions: List[Dict]):
        """Save checkpoint for safe restart"""
        
        checkpoint = {
            'last_processed_index': last_processed_index,
            'processed_definitions': processed_definitions,
            'timestamp': datetime.now().isoformat(),
            'total_definitions': self.total_count,
            'processed_count': len(processed_definitions)
        }
        
        with open(self.checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def _create_timestamped_backup(self, file_path: Path) -> str:
        """Create timestamped backup of existing file"""
        
        if file_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{file_path.stem}_backup_{timestamp}.json"
            backup_path = file_path.parent / backup_file
            
            logger.info(f"📁 Creating backup: {backup_file}")
            file_path.rename(backup_path)
            return backup_file
        
        return None

    def _calculate_eta(self, processed: int, total: int, start_time: datetime) -> str:
        """Calculate estimated time of arrival"""
        
        if processed == 0:
            return "Unknown"
            
        elapsed = (datetime.now() - start_time).total_seconds()
        rate = processed / elapsed
        remaining = total - processed
        eta_seconds = remaining / rate if rate > 0 else 0
        
        hours = int(eta_seconds // 3600)
        minutes = int((eta_seconds % 3600) // 60)
        
        return f"{hours:02d}:{minutes:02d}"

    def run(self):
        """Run the categorization process"""
        
        logger.info("🏁 Starting weighted subject categorization")
        logger.info("="*60)
        
        # Load input data
        logger.info("📖 Loading input definitions...")
        with open(self.input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        definitions = data['definitions']
        
        # Filter to only definitions that need categorization (category == "other")
        to_categorize = [d for d in definitions if d.get('category') == 'other']
        already_categorized = [d for d in definitions if d.get('category') != 'other']
        
        self.total_count = len(to_categorize)
        logger.info(f"📊 Found {self.total_count} definitions to categorize")
        logger.info(f"📊 Found {len(already_categorized)} already categorized definitions")
        
        # Handle checkpoint/resume
        processed_definitions = []
        start_index = 0
        
        if self.resume:
            start_index, processed_definitions = self._load_checkpoint()
            start_index += 1
            
        self.start_time = datetime.now()
        
        # Process definitions with progress tracking
        with tqdm(total=self.total_count, initial=len(processed_definitions), desc="Categorizing") as pbar:
            
            for i in range(start_index, len(to_categorize)):
                definition = to_categorize[i]
                
                # Process single definition
                enhanced_definition = self._process_single_definition(definition)
                processed_definitions.append(enhanced_definition)
                
                # Update progress
                pbar.update(1)
                
                # Show current weights
                weights_str = ", ".join([f"{k}: {v:.2f}" for k, v in enhanced_definition['domain_weights'].items()])
                pbar.set_postfix_str(f"Latest: {weights_str[:50]}...")
                
                # Save checkpoint every 10 definitions
                if (i + 1) % 10 == 0:
                    self._save_checkpoint(i, processed_definitions)
                    
                    # Show ETA
                    eta = self._calculate_eta(len(processed_definitions), self.total_count, self.start_time)
                    logger.info(f"📈 Progress: {len(processed_definitions)}/{self.total_count} | ETA: {eta}")
        
        # Handle already categorized definitions (add simple weights)
        for defn in already_categorized:
            category = defn['category']
            if category in DOMAINS:
                defn['domain_weights'] = {category: 1.0}
            else:
                defn['domain_weights'] = {"core_demographics": 1.0}  # No more "other"
            defn['categorization_method'] = 'single_category_preserved'
            processed_definitions.append(defn)
        
        # Save final results
        logger.info("💾 Saving final results...")
        self._save_final_results(data, processed_definitions)
        
        # Clean up checkpoint
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            logger.info("🧹 Checkpoint file cleaned up")
        
        logger.info("🎉 Categorization complete!")

    def _save_final_results(self, original_data: Dict, processed_definitions: List[Dict]):
        """Save final categorized results"""
        
        # Create backup if file exists
        self._create_timestamped_backup(self.output_path)
        
        # Calculate domain statistics
        domain_counts = {}
        multi_domain_count = 0
        
        for defn in processed_definitions:
            weights = defn.get('domain_weights', {})
            
            # Count primary domains (weight ≥ 0.5)
            for domain, weight in weights.items():
                if weight >= 0.5:
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
            
            # Count multi-domain concepts
            if len(weights) > 1:
                multi_domain_count += 1
        
        # Create enhanced metadata
        enhanced_metadata = {
            **original_data['metadata'],
            'total_definitions': len(processed_definitions),
            'categorization_complete': True,
            'categorization_method': 'dual_model_weighted',
            'models_used': ['gpt-4.1-mini', 'claude-sonnet-4-20250514'],
            'primary_domain_counts': domain_counts,
            'multi_domain_concepts': multi_domain_count,
            'weighting_rules': {
                'min_weight': 0.05,
                'max_domains': 4,
                'normalization': 'sum_to_one'
            },
            'processing_completed_at': datetime.now().isoformat()
        }
        
        # Create final output
        output_data = {
            'metadata': enhanced_metadata,
            'definitions': processed_definitions
        }
        
        # Save results
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Results saved to {self.output_path}")
        
        # Print summary statistics
        logger.info("\n📋 Final Statistics:")
        logger.info(f"   Total definitions: {len(processed_definitions)}")
        logger.info(f"   Multi-domain concepts: {multi_domain_count}")
        
        logger.info("\n📊 Primary domain distribution (weight ≥ 0.5):")
        for domain, count in sorted(domain_counts.items()):
            logger.info(f"   {domain}: {count}")
        
        # Show sample multi-domain results
        multi_domain = [d for d in processed_definitions if len(d.get('domain_weights', {})) > 1][:5]
        if multi_domain:
            logger.info(f"\n🔍 Sample multi-domain concepts:")
            for defn in multi_domain:
                weights_str = ", ".join([f"{k}: {v:.2f}" for k, v in defn['domain_weights'].items()])
                logger.info(f"   {defn['label'][:40]}... → {weights_str}")

def main():
    """Main entry point"""
    
    import argparse
    parser = argparse.ArgumentParser(description="Weighted Subject Categorization")
    parser.add_argument("--resume", action="store_true",
                       help="Resume from checkpoint if available")
    
    args = parser.parse_args()
    
    try:
        categorizer = WeightedSubjectCategorizer(resume=args.resume)
        categorizer.run()
        
    except KeyboardInterrupt:
        logger.info("\n⏸️  Process interrupted by user")
        logger.info("💡 Use --resume flag to continue from checkpoint")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
