#!/usr/bin/env python3
"""
Real API Collaborative LLM Enrichment for Spatial Topology Discovery
Process intelligent sample through Claude 3.5 Sonnet + GPT-4.1 mini ensemble
"""

import pandas as pd
import json
import asyncio
import aiohttp
import time
import os
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib
from sentence_transformers import SentenceTransformer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealAPICollaborativeEnrichment:
    def __init__(self, base_path="../"):
        self.base_path = Path(base_path)
        self.variables_path = self.base_path / "complete_2023_acs_variables"
        self.enrichment_path = self.base_path / "spatial_topology_discovery"
        self.enrichment_path.mkdir(parents=True, exist_ok=True)
        
        # Load API keys from environment
        self.claude_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        if not self.claude_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")
        
        # API endpoints
        self.claude_url = "https://api.anthropic.com/v1/messages"
        self.openai_url = "https://api.openai.com/v1/chat/completions"
        
        # Load embedding model for semantic similarity
        logger.info("Loading sentence transformer for agreement scoring...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Rate limiting
        self.claude_delay = 1.0  # 1 second between Claude calls
        self.openai_delay = 0.5  # 0.5 seconds between OpenAI calls
        
        # Enrichment schema
        self.enrichment_schema = {
            "statistical_limitations": "Proxy variables, coverage gaps, methodological caveats",
            "precision_notes": "Data quality, margins of error, reliability guidance",
            "universe_definition": "Population/housing unit universe and exclusions",
            "calculation_method": "How rates/percentages are derived, base denominators",
            "comparable_variables": "Related variables in same domain",
            "usage_patterns": "Common analytical applications and contexts",
            "interpretation_caveats": "Common misinterpretations to avoid"
        }
    
    async def load_intelligent_sample(self) -> pd.DataFrame:
        """Load the intelligent sample for enrichment"""
        sample_file = self.variables_path / "intelligent_sample_999.csv"
        
        if not sample_file.exists():
            raise FileNotFoundError(f"Intelligent sample not found: {sample_file}")
        
        df = pd.read_csv(sample_file)
        logger.info(f"📊 Loaded intelligent sample: {len(df)} variables")
        
        return df
    
    async def call_claude_api(self, prompt: str) -> Dict:
        """Make API call to Claude 3.5 Sonnet"""
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.claude_api_key,
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.claude_url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Claude API error {response.status}: {error_text}")
                    raise Exception(f"Claude API error: {response.status}")
                
                result = await response.json()
                return result["content"][0]["text"]
    
    async def call_openai_api(self, prompt: str, model: str = "gpt-4.1-mini-2025-04-14") -> Dict:
        """Make API call to OpenAI (GPT-4.1 mini or full)"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.openai_url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenAI API error {response.status}: {error_text}")
                    raise Exception(f"OpenAI API error: {response.status}")
                
                result = await response.json()
                return result["choices"][0]["message"]["content"]
    
    async def enrich_variable_claude(self, variable_data: Dict) -> Dict:
        """Enrich single variable using Claude 3.5 Sonnet API"""
        
        prompt = f"""Analyze this Census ACS variable for statistical methodology and limitations. Focus on methodological rigor and statistical caveats.

Variable ID: {variable_data['variable_id']}
Label: {variable_data['label']}
Concept: {variable_data['concept']}
Table Family: {variable_data.get('table_family', 'unknown')}
Survey: {variable_data['survey']}

Provide analysis as valid JSON only (no markdown, no explanations):
{{
    "statistical_limitations": "What are the specific proxy variables, coverage gaps, and methodological caveats that affect this measure?",
    "precision_notes": "What are the data quality concerns, margin of error considerations, and reliability issues?", 
    "universe_definition": "What population or housing units are specifically included/excluded from this measure?",
    "calculation_method": "How are rates/percentages calculated? What is the exact denominator and any adjustments?",
    "comparable_variables": "What other ACS variables measure similar or related concepts?",
    "usage_patterns": "What are the most common analytical uses and research applications for this variable?",
    "interpretation_caveats": "What specific misinterpretations or analytical errors should researchers avoid?",
    "confidence_score": 0.85
}}

Focus on statistical methodology, measurement limitations, and analytical precision. Be specific about methodological issues."""
        
        try:
            await asyncio.sleep(self.claude_delay)  # Rate limiting
            response_text = await self.call_claude_api(prompt)
            
            # Parse JSON from response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            result = json.loads(response_text)
            
            # Add metadata
            result.update({
                "enrichment_source": "claude_3_5_sonnet",
                "enrichment_timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Claude enrichment failed for {variable_data['variable_id']}: {e}")
            return {
                "statistical_limitations": f"ERROR: Claude analysis failed - {str(e)}",
                "precision_notes": "Analysis unavailable due to API error",
                "universe_definition": "Unable to analyze universe definition",
                "calculation_method": "Calculation method analysis failed",
                "comparable_variables": "Comparable variable analysis failed",
                "usage_patterns": "Usage pattern analysis failed",
                "interpretation_caveats": "Interpretation guidance unavailable",
                "confidence_score": 0.1,
                "enrichment_source": "claude_3_5_sonnet_error",
                "enrichment_timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def enrich_variable_gpt(self, variable_data: Dict) -> Dict:
        """Enrich single variable using GPT-4.1 mini API"""
        
        prompt = f"""Analyze this US Census variable for conceptual relationships and real-world usage patterns. Focus on how this variable is actually used in research and analysis.

Variable: {variable_data['variable_id']} - {variable_data['label']}
Concept: {variable_data['concept']}
Survey: {variable_data['survey']}
Table Family: {variable_data.get('table_family', 'unknown')}

Return valid JSON analysis focusing on:
{{
    "statistical_limitations": "What are the key limitations, proxy issues, and measurement challenges?",
    "precision_notes": "Data quality considerations and reliability factors?", 
    "universe_definition": "Population scope and definitional boundaries?",
    "calculation_method": "How are derived measures calculated and what are the components?",
    "comparable_variables": "What related variables provide similar or complementary information?",
    "usage_patterns": "How is this variable commonly used in demographic analysis and research?",
    "interpretation_caveats": "What misinterpretations or analytical pitfalls should be avoided?",
    "confidence_score": 0.82
}}

Focus on practical usage, conceptual relationships, and real-world applications. Be specific about how researchers actually use this variable."""
        
        try:
            await asyncio.sleep(self.openai_delay)  # Rate limiting
            response_text = await self.call_openai_api(prompt, "gpt-4.1-mini-2025-04-14")
            
            # Parse JSON from response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            result = json.loads(response_text)
            
            # Add metadata
            result.update({
                "enrichment_source": "gpt_4_1_mini",
                "enrichment_timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"GPT enrichment failed for {variable_data['variable_id']}: {e}")
            return {
                "statistical_limitations": f"ERROR: GPT analysis failed - {str(e)}",
                "precision_notes": "Analysis unavailable due to API error",
                "universe_definition": "Unable to analyze universe definition",
                "calculation_method": "Calculation method analysis failed",
                "comparable_variables": "Comparable variable analysis failed",
                "usage_patterns": "Usage pattern analysis failed",
                "interpretation_caveats": "Interpretation guidance unavailable",
                "confidence_score": 0.1,
                "enrichment_source": "gpt_4_1_mini_error",
                "enrichment_timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts using embeddings"""
        
        try:
            embeddings = self.embedding_model.encode([text1, text2])
            similarity = float(embeddings[0] @ embeddings[1] /
                             (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])))
            return max(0.0, min(1.0, similarity))  # Clamp to [0,1]
        except Exception as e:
            logger.warning(f"Similarity calculation failed: {e}")
            return 0.5  # Default moderate similarity
    
    def calculate_agreement_score(self, claude_result: Dict, gpt_result: Dict) -> float:
        """Calculate agreement between Claude and GPT analyses using semantic similarity"""
        
        agreement_scores = []
        
        # Compare each field semantically
        fields_to_compare = [
            'statistical_limitations',
            'precision_notes',
            'universe_definition',
            'calculation_method',
            'usage_patterns',
            'interpretation_caveats'
        ]
        
        for field in fields_to_compare:
            claude_text = claude_result.get(field, "")
            gpt_text = gpt_result.get(field, "")
            
            if claude_text and gpt_text:
                field_similarity = self.calculate_semantic_similarity(claude_text, gpt_text)
                agreement_scores.append(field_similarity)
        
        # Compare confidence scores
        claude_conf = claude_result.get('confidence_score', 0.5)
        gpt_conf = gpt_result.get('confidence_score', 0.5)
        conf_agreement = 1.0 - abs(claude_conf - gpt_conf)
        agreement_scores.append(conf_agreement)
        
        # Calculate overall agreement
        overall_agreement = sum(agreement_scores) / len(agreement_scores) if agreement_scores else 0.5
        
        return overall_agreement
    
    async def arbitrate_disagreement(self, claude_result: Dict, gpt_result: Dict,
                                   variable_data: Dict, agreement_score: float) -> Dict:
        """Use GPT-4 full for arbitration when there's significant disagreement"""
        
        prompt = f"""Two AI systems analyzed this Census variable and reached different conclusions. Please arbitrate and synthesize the best insights.

Variable: {variable_data['variable_id']} - {variable_data['label']}
Concept: {variable_data['concept']}

CLAUDE ANALYSIS:
Statistical Limitations: {claude_result.get('statistical_limitations', 'N/A')}
Universe Definition: {claude_result.get('universe_definition', 'N/A')}
Usage Patterns: {claude_result.get('usage_patterns', 'N/A')}
Confidence: {claude_result.get('confidence_score', 'N/A')}

GPT ANALYSIS:
Statistical Limitations: {gpt_result.get('statistical_limitations', 'N/A')}
Universe Definition: {gpt_result.get('universe_definition', 'N/A')}
Usage Patterns: {gpt_result.get('usage_patterns', 'N/A')}
Confidence: {gpt_result.get('confidence_score', 'N/A')}

Agreement Score: {agreement_score:.3f}

Please provide a synthesized analysis as valid JSON that:
1. Identifies where the analyses agree and disagree
2. Resolves contradictions with the most accurate information
3. Combines the best insights from both analyses
4. Assigns an appropriate confidence score

{{
    "statistical_limitations": "Synthesized analysis of limitations",
    "precision_notes": "Combined precision guidance",
    "universe_definition": "Resolved universe definition",
    "calculation_method": "Clarified calculation method",
    "comparable_variables": "Synthesized comparable variables",
    "usage_patterns": "Combined usage insights",
    "interpretation_caveats": "Integrated interpretation guidance",
    "confidence_score": 0.75,
    "arbitration_notes": "Key disagreements resolved and synthesis rationale"
}}"""
        
        try:
            response_text = await self.call_openai_api(prompt, "gpt-4.1-2025-04-14")  # Use full GPT-4.1 for arbitration
            
            # Parse JSON from response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            result = json.loads(response_text)
            
            # Add arbitration metadata
            result.update({
                "enrichment_source": "gpt_4_1_arbitration",
                "enrichment_timestamp": datetime.now().isoformat(),
                "arbitration_triggered": True,
                "original_agreement_score": agreement_score
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Arbitration failed for {variable_data['variable_id']}: {e}")
            # Fall back to confidence-weighted average
            return await self.synthesize_enrichments(claude_result, gpt_result, agreement_score)
    
    async def synthesize_enrichments(self, claude_result: Dict, gpt_result: Dict,
                                   agreement_score: float) -> Dict:
        """Synthesize Claude and GPT analyses into final enrichment"""
        
        # Synthesis strategy based on agreement level
        if agreement_score > 0.8:
            # High agreement - merge insights
            synthesis_method = "high_agreement_merge"
            final_confidence = (claude_result['confidence_score'] + gpt_result['confidence_score']) / 2
            
            # Merge complementary insights
            synthesized = {}
            for field in ['statistical_limitations', 'precision_notes', 'universe_definition',
                         'calculation_method', 'comparable_variables', 'usage_patterns', 'interpretation_caveats']:
                claude_text = claude_result.get(field, "")
                gpt_text = gpt_result.get(field, "")
                
                # Combine non-overlapping insights
                if claude_text and gpt_text:
                    synthesized[field] = f"CLAUDE: {claude_text} | GPT: {gpt_text}"
                else:
                    synthesized[field] = claude_text or gpt_text
                    
        elif agreement_score > 0.5:
            # Medium agreement - collaborative resolution
            synthesis_method = "collaborative_resolution"
            final_confidence = max(claude_result['confidence_score'], gpt_result['confidence_score']) * 0.9
            
            # Weighted combination favoring higher confidence
            claude_weight = claude_result['confidence_score']
            gpt_weight = gpt_result['confidence_score']
            total_weight = claude_weight + gpt_weight
            
            synthesized = {}
            for field in ['statistical_limitations', 'precision_notes', 'universe_definition',
                         'calculation_method', 'comparable_variables', 'usage_patterns', 'interpretation_caveats']:
                claude_text = claude_result.get(field, "")
                gpt_text = gpt_result.get(field, "")
                
                if claude_weight > gpt_weight:
                    synthesized[field] = f"PRIMARY: {claude_text} | SECONDARY: {gpt_text}"
                else:
                    synthesized[field] = f"PRIMARY: {gpt_text} | SECONDARY: {claude_text}"
                    
        else:
            # Low agreement - flag for arbitration
            synthesis_method = "arbitration_required"
            final_confidence = 0.3
            
            synthesized = {
                field: f"DISAGREEMENT - Claude: {claude_result.get(field, '')} | GPT: {gpt_result.get(field, '')}"
                for field in ['statistical_limitations', 'precision_notes', 'universe_definition',
                             'calculation_method', 'comparable_variables', 'usage_patterns', 'interpretation_caveats']
            }
        
        synthesized.update({
            "synthesis_metadata": {
                "agreement_score": agreement_score,
                "synthesis_method": synthesis_method,
                "final_confidence": final_confidence,
                "claude_confidence": claude_result['confidence_score'],
                "gpt_confidence": gpt_result['confidence_score'],
                "synthesis_timestamp": datetime.now().isoformat()
            }
        })
        
        return synthesized
    
    async def enrich_variable(self, variable_data: Dict, checkpoint_file: Path) -> Dict:
        """Enrich single variable through collaborative LLM analysis"""
        
        variable_id = variable_data['variable_id']
        
        # Check if already processed (idempotent)
        if checkpoint_file.exists():
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
                if variable_id in checkpoint_data:
                    logger.info(f"  ↻ Skipping {variable_id} (already processed)")
                    return checkpoint_data[variable_id]
        
        logger.info(f"  🔄 Enriching {variable_id}: {variable_data['label'][:60]}...")
        
        # Get enrichments from both LLMs in parallel
        claude_task = self.enrich_variable_claude(variable_data)
        gpt_task = self.enrich_variable_gpt(variable_data)
        
        claude_result, gpt_result = await asyncio.gather(claude_task, gpt_task)
        
        # Calculate agreement
        agreement_score = self.calculate_agreement_score(claude_result, gpt_result)
        logger.info(f"    📊 Agreement score: {agreement_score:.3f}")
        
        # Synthesize or arbitrate based on agreement
        if agreement_score < 0.4:  # Very low agreement - use arbitration
            logger.info(f"    ⚖️  Low agreement, triggering arbitration...")
            synthesized = await self.arbitrate_disagreement(claude_result, gpt_result, variable_data, agreement_score)
        else:
            synthesized = await self.synthesize_enrichments(claude_result, gpt_result, agreement_score)
        
        # Combine original data with enrichments
        enriched_variable = {
            **variable_data,
            "enrichment": synthesized,
            "processing_metadata": {
                "enriched_timestamp": datetime.now().isoformat(),
                "agreement_score": agreement_score,
                "processing_version": "1.0_real_api"
            }
        }
        
        # Update checkpoint
        checkpoint_data = {}
        if checkpoint_file.exists():
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
        
        checkpoint_data[variable_id] = enriched_variable
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        return enriched_variable
    
    async def process_intelligent_sample(self, batch_size: int = 10):
        """Process the intelligent sample through real collaborative enrichment"""
        
        logger.info("🚀 Starting REAL API Collaborative Enrichment")
        logger.info("   Using Claude 3.5 Sonnet + GPT-4o-mini + GPT-4o arbitration")
        
        # Load sample
        df = await self.load_intelligent_sample()
        
        # Set up checkpoint file for real API data
        checkpoint_file = self.enrichment_path / "real_api_enrichment_checkpoint.json"
        
        # Track processing metrics
        start_time = time.time()
        processed_count = 0
        total_count = len(df)
        arbitration_count = 0
        
        # Process in smaller batches for API rate limiting
        for i in range(0, total_count, batch_size):
            batch = df.iloc[i:i+batch_size]
            
            logger.info(f"📦 Processing batch {i//batch_size + 1}/{(total_count-1)//batch_size + 1} ({len(batch)} variables)")
            
            batch_start = time.time()
            
            # Process batch
            for _, row in batch.iterrows():
                variable_data = row.to_dict()
                
                try:
                    enriched = await self.enrich_variable(variable_data, checkpoint_file)
                    processed_count += 1
                    
                    # Check if arbitration was used
                    if enriched.get('enrichment', {}).get('arbitration_triggered', False):
                        arbitration_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {row['variable_id']}: {e}")
                    continue
            
            batch_time = time.time() - batch_start
            rate = len(batch) / batch_time if batch_time > 0 else 0
            
            logger.info(f"  ✅ Batch complete: {rate:.1f} variables/second")
            logger.info(f"  📊 Progress: {processed_count}/{total_count} ({100*processed_count/total_count:.1f}%)")
            logger.info(f"  ⚖️  Arbitrations: {arbitration_count}")
        
        total_time = time.time() - start_time
        
        logger.info(f"🎉 Real API Collaborative Enrichment Complete!")
        logger.info(f"   Processed: {processed_count}/{total_count} variables")
        logger.info(f"   Arbitrations: {arbitration_count} ({100*arbitration_count/processed_count:.1f}%)")
        logger.info(f"   Total time: {total_time/60:.1f} minutes")
        logger.info(f"   Average rate: {processed_count/total_time:.1f} variables/second")
        
        # Generate summary analysis
        await self.generate_enrichment_summary()
        
        return checkpoint_file
    
    async def generate_enrichment_summary(self):
        """Generate summary analysis of real enrichment results"""
        
        checkpoint_file = self.enrichment_path / "enrichment_checkpoint.json"
        
        if not checkpoint_file.exists():
            logger.error("No enrichment data found")
            return
        
        with open(checkpoint_file, 'r') as f:
            enrichment_data = json.load(f)
        
        # Analyze enrichment quality
        agreement_scores = []
        confidence_scores = []
        synthesis_methods = {}
        arbitration_count = 0
        error_count = 0
        
        for var_id, data in enrichment_data.items():
            enrichment = data.get('enrichment', {})
            metadata = enrichment.get('synthesis_metadata', {})
            
            agreement_scores.append(metadata.get('agreement_score', 0))
            confidence_scores.append(metadata.get('final_confidence', 0))
            
            method = metadata.get('synthesis_method', 'unknown')
            synthesis_methods[method] = synthesis_methods.get(method, 0) + 1
            
            if enrichment.get('arbitration_triggered', False):
                arbitration_count += 1
                
            if 'error' in enrichment:
                error_count += 1
        
        summary = {
            "total_variables_enriched": len(enrichment_data),
            "average_agreement_score": sum(agreement_scores) / len(agreement_scores) if agreement_scores else 0,
            "average_confidence_score": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
            "synthesis_method_distribution": synthesis_methods,
            "arbitration_cases": arbitration_count,
            "error_cases": error_count,
            "high_agreement_count": len([s for s in agreement_scores if s > 0.8]),
            "medium_agreement_count": len([s for s in agreement_scores if 0.5 < s <= 0.8]),
            "low_agreement_count": len([s for s in agreement_scores if s <= 0.5]),
            "analysis_timestamp": datetime.now().isoformat(),
            "enrichment_type": "real_api_collaborative"
        }
        
        # Save summary
        summary_file = self.enrichment_path / "enrichment_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📈 Real API Enrichment Summary:")
        logger.info(f"   Total enriched: {summary['total_variables_enriched']}")
        logger.info(f"   Avg agreement: {summary['average_agreement_score']:.3f}")
        logger.info(f"   Avg confidence: {summary['average_confidence_score']:.3f}")
        logger.info(f"   High agreement: {summary['high_agreement_count']} variables")
        logger.info(f"   Medium agreement: {summary['medium_agreement_count']} variables")
        logger.info(f"   Low agreement: {summary['low_agreement_count']} variables")
        logger.info(f"   Arbitrations: {summary['arbitration_cases']} cases")
        logger.info(f"   Errors: {summary['error_cases']} cases")
        
        return summary

# Add missing numpy import
import numpy as np

async def main():
    """Execute real API collaborative enrichment on intelligent sample"""
    
    enricher = RealAPICollaborativeEnrichment()
    
    logger.info("🎯 SPATIAL TOPOLOGY DISCOVERY - PHASE 1: REAL API ENRICHMENT")
    logger.info("   Processing intelligent sample through real Claude + GPT APIs")
    logger.info("   Building foundation for spatial embedding coordinates")
    logger.info("   Ensemble: Claude 3.5 Sonnet + GPT-4.1-mini + GPT-4.1 arbitration")
    
    # Process the sample
    checkpoint_file = await enricher.process_intelligent_sample()
    
    logger.info("✅ READY FOR PHASE 2: SPATIAL EMBEDDING")
    logger.info(f"   Real enriched data saved to: {checkpoint_file}")
    logger.info("   Next: Generate embeddings from real LLM analysis and discover topology")

if __name__ == "__main__":
    asyncio.run(main())
