#!/usr/bin/env python3
"""
Concept Builder Pipeline
Refactored from llm_concept_reviewer.py to support dual-mode concept building
using GPT-4.1-mini (topic specialist) and Claude Sonnet 4 (census generalist)
"""

import os
import json
import argparse
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import time
import re

# Third-party imports
import openai
import anthropic
import tiktoken
from dotenv import load_dotenv

# Import our robust JSON fixer
try:
    from llm_json_fixer import fix_llm_json, LLMJSONFixer
except ImportError:
    # Fallback if module not available
    logger.warning("llm_json_fixer module not found, using basic JSON parsing")
    def fix_llm_json(content):
        return json.loads(content)
    LLMJSONFixer = None

# Load environment variables from parent directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Configure logging
def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

# Initialize logger (will be reconfigured in main)
logger = setup_logging()

@dataclass
class Config:
    """Configuration for concept builder"""
    mode: str = "topical"  # topical or geo
    clusters: int = 7  # default number of top-level concepts
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    input_dir: str = "knowledge-base/data"
    output_dir: str = "knowledge-base/concepts"
    max_tokens_per_batch: int = 1000
    max_retries: int = 3
    retry_delay: int = 2
    gpt_temperature: float = 0.4
    gpt_max_tokens: int = 3000
    skip_failed_batches: bool = False  # New option
    
    def __post_init__(self):
        # Set API keys from environment if not provided
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.anthropic_api_key:
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        
        # Validate API keys
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment or config")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment or config")
        
        # Set defaults based on mode
        if self.mode == "geo" and self.clusters == 7:
            self.clusters = 5  # Default for geo mode

class ConceptBuilder:
    """Main concept builder class"""
    
    def __init__(self, config: Config):
        self.config = config
        self.openai_client = openai.OpenAI(api_key=config.openai_api_key)
        self.anthropic_client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        
        # Ensure output directory exists
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized ConceptBuilder in {config.mode} mode with {config.clusters} clusters")
    
    def load_phrases(self) -> List[str]:
        """Load phrases based on mode"""
        filename = "topical_phrases.txt" if self.config.mode == "topical" else "geo_phrases.txt"
        filepath = Path(self.config.input_dir) / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Phrase file not found: {filepath}")
        
        with open(filepath, 'r') as f:
            phrases = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Loaded {len(phrases)} phrases from {filename}")
        return phrases
    
    def batch_phrases(self, phrases: List[str]) -> List[List[str]]:
        """Batch phrases to stay under token limit"""
        batches = []
        current_batch = []
        current_tokens = 0
        
        for phrase in phrases:
            phrase_tokens = len(self.tokenizer.encode(phrase))
            
            if current_tokens + phrase_tokens > self.config.max_tokens_per_batch:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [phrase]
                current_tokens = phrase_tokens
            else:
                current_batch.append(phrase)
                current_tokens += phrase_tokens
        
        if current_batch:
            batches.append(current_batch)
        
        logger.info(f"Created {len(batches)} batches from {len(phrases)} phrases")
        return batches
    
    async def gpt4_split_and_label(self, phrases: List[str]) -> Dict[str, Any]:
        """Use GPT-4.1-mini to cluster and label phrases"""
        
        if self.config.mode == "topical":
            prompt = f"""You are a topical domain specialist for US Census data. 
            Analyze these phrases and organize them into exactly {self.config.clusters} topical concept clusters.
            
            Phrases to analyze:
            {json.dumps(phrases, indent=2)}
            
            For each cluster:
            1. Create a clear, concise label (2-3 words max)
            2. Write a definition that explains what Census variables in this cluster measure
            3. List all phrases that belong to this cluster
            
            Return JSON in this exact format:
            {{
                "cluster_name_1": {{
                    "label": "Clear Label",
                    "definition": "Variables that measure...",
                    "phrases": ["phrase1", "phrase2", ...]
                }},
                "cluster_name_2": {{
                    "label": "Another Label",
                    "definition": "Variables that measure...",
                    "phrases": ["phrase3", "phrase4", ...]
                }}
            }}
            
            Focus on creating semantically coherent clusters that represent major Census data themes."""
        
        else:  # geo mode
            prompt = f"""You are a geographic classification specialist for US Census data.
            Analyze these geographic phrases and organize them into exactly {self.config.clusters} geographic concept clusters.
            
            Phrases to analyze:
            {json.dumps(phrases, indent=2)}
            
            For each cluster:
            1. Create a geographic category label (e.g., "Administrative Boundaries", "Statistical Areas")
            2. Write a definition explaining what geographic level or type this represents
            3. List all phrases that belong to this cluster
            
            Return JSON in this exact format:
            {{
                "geo_category_1": {{
                    "label": "Geographic Category",
                    "definition": "Geographic units that represent...",
                    "phrases": ["geo_phrase1", "geo_phrase2", ...]
                }},
                "geo_category_2": {{
                    "label": "Another Category",
                    "definition": "Geographic units that represent...",
                    "phrases": ["geo_phrase3", "geo_phrase4", ...]
                }}
            }}
            
            Focus on creating logical geographic hierarchies and relationships."""
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4.1-mini",  # GPT-4.1-mini as specified
                    messages=[
                        {"role": "system", "content": "You are an expert at organizing Census data concepts."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.gpt_temperature,
                    max_tokens=self.config.gpt_max_tokens,
                    response_format={"type": "json_object"}
                )
                
                raw_content = response.choices[0].message.content
                logger.debug(f"Raw GPT response length: {len(raw_content)} characters")
                
                # Try to parse JSON
                try:
                    if LLMJSONFixer:
                        result = fix_llm_json(raw_content)
                    else:
                        result = json.loads(raw_content)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"JSON decode error: {e}")
                    logger.debug(f"Raw content length: {len(raw_content)}")
                    
                    # Save raw response for debugging
                    debug_file = Path(self.config.output_dir) / f"debug_gpt_response_batch_{attempt+1}_{int(time.time())}.txt"
                    with open(debug_file, 'w') as f:
                        f.write(raw_content)
                    logger.info(f"Saved raw GPT response to: {debug_file}")
                    
                    # Re-raise to trigger retry
                    raise
                
                logger.info(f"GPT-4 created {len(result)} clusters")
                return result
                
            except Exception as e:
                logger.error(f"GPT-4 API error (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise
    
    async def sonnet_validate(self, concept_json: Dict[str, Any]) -> Dict[str, Any]:
        """Use Claude Sonnet 4 to validate and refine concepts"""
        
        if self.config.mode == "topical":
            prompt = f"""You are a census generalist QA expert. Review these topical concept clusters for US Census data.
            
            Concepts to review:
            {json.dumps(concept_json, indent=2)}
            
            Your tasks:
            1. Validate that labels are clear and appropriate for Census data
            2. Ensure definitions accurately describe what Census variables measure
            3. Remove any duplicate phrases across clusters
            4. Verify semantic coherence within each cluster
            5. Suggest improvements to labels or definitions if needed
            
            CRITICAL: Return ONLY valid JSON. Common mistakes to avoid:
            - Use only straight quotes ("), never curly quotes ("" or '')
            - Ensure all strings are properly terminated
            - Add commas between all array elements and object properties
            - Do not include any text before or after the JSON object
            
            Your response must be a valid JSON object with the same structure as the input."""
        
        else:  # geo mode
            prompt = f"""You are a census geography QA expert. Review these geographic concept clusters.
            
            Concepts to review:
            {json.dumps(concept_json, indent=2)}
            
            Your tasks:
            1. Validate geographic hierarchy and relationships
            2. Ensure definitions follow Census geographic standards
            3. Remove any duplicate geographic terms
            4. Verify that each cluster represents a coherent geographic concept
            5. Improve labels to match Census geographic terminology
            
            CRITICAL: Return ONLY valid JSON. Common mistakes to avoid:
            - Use only straight quotes ("), never curly quotes ("" or '')
            - Ensure all strings are properly terminated
            - Add commas between all array elements and object properties
            - Do not include any text before or after the JSON object
            
            Your response must be a valid JSON object with the same structure as the input."""
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",  # Claude Sonnet 4 (from original script)
                    max_tokens=4000,
                    temperature=0,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # Extract JSON from response
                content = response.content[0].text
                
                # Debug logging
                logger.debug(f"Raw Sonnet response: {content[:500]}...")
                
                # Fix common LLM issues
                # Replace smart quotes with regular quotes
                content = content.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
                
                # Try to find JSON in the response
                json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1).strip()
                else:
                    # Try to find JSON object directly
                    json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(1)
                
                try:
                    result = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    logger.debug(f"Error at position {e.pos}: {content[max(0, e.pos-50):e.pos+50]}")
                    
                    # Save the response for debugging
                    debug_file = Path(self.config.output_dir) / f"debug_sonnet_response_batch_{attempt+1}_{int(time.time())}.txt"
                    with open(debug_file, 'w') as f:
                        f.write(f"=== ORIGINAL CONTENT ===\n{response.content[0].text}\n")
                        f.write(f"\n=== AFTER SMART QUOTE FIX ===\n{content}\n")
                        f.write(f"\n=== ERROR ===\n{e}\n")
                    logger.info(f"Saved problematic Sonnet response to: {debug_file}")
                    
                    raise
                logger.info(f"Sonnet validated {len(result)} concepts")
                return result
                
            except Exception as e:
                logger.error(f"Sonnet API error (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise
    
    async def process_batch(self, phrases: List[str]) -> Dict[str, Any]:
        """Process a single batch through both models"""
        logger.info(f"Processing batch with {len(phrases)} phrases")
        
        # Step 1: GPT-4 clustering
        gpt_result = await self.gpt4_split_and_label(phrases)
        
        # Step 2: Sonnet validation
        validated_result = await self.sonnet_validate(gpt_result)
        
        return validated_result
    
    def merge_batch_results(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge results from multiple batches"""
        merged = {}
        
        for batch_result in batch_results:
            for concept_key, concept_data in batch_result.items():
                if concept_key not in merged:
                    merged[concept_key] = concept_data
                else:
                    # Merge phrases from duplicate concept names
                    existing_phrases = set(merged[concept_key].get("phrases", []))
                    new_phrases = set(concept_data.get("phrases", []))
                    merged[concept_key]["phrases"] = sorted(list(existing_phrases | new_phrases))
        
        logger.info(f"Merged {len(batch_results)} batches into {len(merged)} concepts")
        return merged
    
    async def run(self) -> None:
        """Main processing pipeline"""
        start_time = time.time()
        
        # Load phrases
        phrases = self.load_phrases()
        
        # Create batches
        batches = self.batch_phrases(phrases)
        
        # Check for checkpoint file
        checkpoint_file = Path(self.config.output_dir) / f".checkpoint_{self.config.mode}.json"
        batch_results = []
        start_batch = 0
        
        if checkpoint_file.exists():
            logger.info(f"Found checkpoint file: {checkpoint_file}")
            try:
                with open(checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                    batch_results = checkpoint.get("batch_results", [])
                    start_batch = checkpoint.get("next_batch", 0)
                    logger.info(f"Resuming from batch {start_batch}/{len(batches)}")
                    logger.info(f"Already completed: {len(batch_results)} batches")
            except Exception as e:
                logger.error(f"Error loading checkpoint: {e}")
                # Create backup of corrupted checkpoint
                backup_name = checkpoint_file.with_suffix(f".backup_{int(time.time())}.json")
                checkpoint_file.rename(backup_name)
                logger.info(f"Backed up corrupted checkpoint to: {backup_name}")
                batch_results = []
                start_batch = 0
        
        # Process each batch
        for i in range(start_batch, len(batches)):
            batch = batches[i]
            logger.info(f"Processing batch {i+1}/{len(batches)}")
            
            try:
                result = await self.process_batch(batch)
                batch_results.append(result)
                
                # Save checkpoint after each successful batch
                # First save to temp file, then rename (atomic operation)
                temp_checkpoint = checkpoint_file.with_suffix('.tmp')
                with open(temp_checkpoint, 'w') as f:
                    json.dump({
                        "batch_results": batch_results,
                        "next_batch": i + 1,
                        "total_batches": len(batches),
                        "last_updated": datetime.now().isoformat()
                    }, f, indent=2)
                
                # Atomic rename
                temp_checkpoint.replace(checkpoint_file)
                logger.debug(f"Checkpoint saved: {len(batch_results)} batches completed")
                    
            except Exception as e:
                logger.error(f"Failed to process batch {i+1}: {e}")
                logger.info("Progress saved to checkpoint file. You can resume by running the script again.")
                
                # Save error details for debugging
                error_file = Path(self.config.output_dir) / f"error_batch_{i+1}_{self.config.mode}.json"
                with open(error_file, 'w') as f:
                    json.dump({
                        "batch_index": i,
                        "batch_size": len(batch),
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }, f, indent=2)
                logger.info(f"Error details saved to: {error_file}")
                
                if self.config.skip_failed_batches:
                    logger.warning(f"Skipping failed batch {i+1} and continuing...")
                    # Add empty result for this batch
                    batch_results.append({"skipped_batch": i+1, "error": str(e)})
                    
                    # Update checkpoint to skip this batch
                    temp_checkpoint = checkpoint_file.with_suffix('.tmp')
                    with open(temp_checkpoint, 'w') as f:
                        json.dump({
                            "batch_results": batch_results,
                            "next_batch": i + 1,
                            "total_batches": len(batches),
                            "last_updated": datetime.now().isoformat()
                        }, f, indent=2)
                    temp_checkpoint.replace(checkpoint_file)
                else:
                    raise
        
        # Merge results
        final_concepts = self.merge_batch_results(batch_results)
        
        # If we have too many concepts, run a final consolidation
        if len(final_concepts) > self.config.clusters:
            logger.info(f"Consolidating {len(final_concepts)} concepts down to {self.config.clusters}")
            consolidated = await self.sonnet_validate({
                "task": f"Consolidate these {len(final_concepts)} concepts into exactly {self.config.clusters} concepts",
                "concepts": final_concepts
            })
            final_concepts = consolidated
        
        # Add metadata
        final_output = {
            "metadata": {
                "mode": self.config.mode,
                "created_at": datetime.now().isoformat(),
                "total_phrases": len(phrases),
                "num_concepts": len(final_concepts),
                "models_used": {
                    "clustering": "gpt-4.1-mini",
                    "validation": "claude-sonnet-4-20250514"
                }
            },
            "concepts": final_concepts
        }
        
        # Save output
        output_filename = "topical_concepts.json" if self.config.mode == "topical" else "geo_language_tags.json"
        output_path = Path(self.config.output_dir) / output_filename
        
        with open(output_path, 'w') as f:
            json.dump(final_output, f, indent=2)
        
        # Archive checkpoint file on success (don't delete in case you want to review)
        if checkpoint_file.exists():
            archive_name = checkpoint_file.with_suffix(f".completed_{int(time.time())}.json")
            checkpoint_file.rename(archive_name)
            logger.info(f"Archived checkpoint to: {archive_name}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Complete! Processed {len(phrases)} phrases into {len(final_concepts)} concepts")
        logger.info(f"⏱️  Total time: {elapsed_time:.2f} seconds")
        logger.info(f"💾 Output saved to: {output_path}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Build Census concepts using dual LLM approach")
    parser.add_argument("--geo", action="store_true", help="Run in geo mode (default: topical)")
    parser.add_argument("--clusters", type=int, help="Number of top-level concepts to create")
    parser.add_argument("--openai-api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--anthropic-api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--input-dir", default="knowledge-base/data", help="Input directory for phrase files")
    parser.add_argument("--output-dir", default="knowledge-base/concepts", help="Output directory for concept files")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--skip-failed-batches", action="store_true", help="Skip failed batches instead of stopping")
    
    args = parser.parse_args()
    
    # Setup logging
    global logger
    logger = setup_logging(args.debug)
    
    # Create config
    config = Config(
        mode="geo" if args.geo else "topical",
        clusters=args.clusters if args.clusters else (5 if args.geo else 7),
        openai_api_key=args.openai_api_key or "",
        anthropic_api_key=args.anthropic_api_key or "",
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        skip_failed_batches=args.skip_failed_batches
    )
    
    # Create and run builder
    builder = ConceptBuilder(config)
    
    # Run async pipeline
    asyncio.run(builder.run())

if __name__ == "__main__":
    main()
