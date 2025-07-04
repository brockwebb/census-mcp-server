#!/usr/bin/env python3

import json
import asyncio
import argparse
import logging
import csv
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import openai
import anthropic
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMConceptReviewer:
    def __init__(self, openai_api_key: str, anthropic_api_key: str, mode: str = "review"):
        self.openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
        self.anthropic_client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self.mode = mode
        
        # Initialize results tracking
        self.review_results = {
            'total_reviewed': 0,
            'approved': 0,
            'modified': 0,
            'rejected': 0,
            'processing_errors': []
        }
        
        # Define prompts for different modes
        self.prompts = {
            "review": """You are validating Census concept mappings. Your job is to determine if a concept is accurately mapped to the right Census tables and statistical methods.

CONCEPT TO VALIDATE:
- Label: {label}
- Universe: {universe}
- Statistical Method: {stat_method}
- Mapped Census Tables: {census_tables}
- Definition: {definition}

VALIDATION CRITERIA:
1. ACCURACY: Does this concept mapping correctly represent what Census actually measures?
2. METHODOLOGY: Is the statistical method appropriate for this universe?
3. TABLES: Are the mapped tables correct for this concept?
4. FEASIBILITY: Can this actually be calculated from available Census data?

Respond in JSON format:
{{
  "validation_decision": "approve|modify|reject",
  "reasoning": "Detailed explanation of your decision",
  "suggested_changes": "If modify: specific changes needed",
  "confidence": 0.0-1.0,
  "alternative_tables": ["table1", "table2"] if current mapping is wrong,
  "complexity_rating": "simple|moderate|complex"
}}""",
            
            "negative_knowledge": """You are analyzing rejected Census concepts to create a negative knowledge taxonomy for user guidance.

REJECTED CONCEPT:
- Label: {label}
- Universe: {universe}
- Definition: {definition}
- Original Rejection Reason: {reasoning}

CATEGORIZE THE REJECTION TYPE:
- methodologically_flawed: Universe/method combinations that don't work statistically
- better_routed: Available elsewhere with higher quality (BLS, CDC, etc.)
- reliability_issues: Exists but has known problems (sample sizes, margins of error)
- universe_mismatch: Concept valid but not available for requested geography/population
- temporal_limitations: Data exists but not at requested frequency/recency
- mapping_error: Concept valid but assigned to wrong Census tables

CREATE USER GUIDANCE:
- What to tell users who request this concept
- Why this approach is problematic
- What alternative approaches to suggest
- When (if ever) this concept might be appropriate

Respond in JSON format:
{{
  "rejection_category": "methodologically_flawed|better_routed|reliability_issues|universe_mismatch|temporal_limitations|mapping_error",
  "severity": "hard_stop|warning|caution",
  "user_message": "Clear message to show users requesting this concept",
  "why_problematic": "Technical explanation of the issue",
  "alternatives": ["Alternative approach 1", "Alternative approach 2"],
  "appropriate_contexts": "When this concept might still be valid (if any)",
  "routing_suggestion": "census|bls|cdc|other|unavailable"
}}""",
            
            "complex_analysis": """You are analyzing complex statistical concepts that require sophisticated implementation strategies. These concepts passed validation but need detailed implementation guidance.

COMPLEX CONCEPT:
- Label: {label}
- Universe: {universe}
- Statistical Method: {stat_method}
- Census Tables: {census_tables}
- Definition: {definition}
- Implementation Notes: {implementation_notes}

PROVIDE DETAILED ANALYSIS:
1. CALCULATION STRATEGY: Step-by-step approach for computing this measure
2. METHODOLOGICAL CHALLENGES: Potential issues during implementation
3. RELIABILITY THRESHOLDS: When results become unreliable (geography, sample size, etc.)
4. PRECISION ESTIMATES: Expected margins of error, confidence intervals
5. ALTERNATIVE APPROACHES: Simpler proxies or different methodologies
6. USE CASE GUIDANCE: When to use vs. when to avoid this measure

Respond in JSON format:
{{
  "calculation_strategy": "Step-by-step implementation approach",
  "methodological_challenges": ["Challenge 1", "Challenge 2"],
  "reliability_thresholds": {{
    "min_sample_size": 100,
    "min_geography": "county",
    "confidence_intervals": "90%|95%|99%"
  }},
  "precision_estimates": "Expected margins of error",
  "alternative_approaches": ["Simpler proxy 1", "Different methodology 2"],
  "use_case_guidance": {{
    "recommended_for": ["Use case 1", "Use case 2"],
    "avoid_for": ["Problematic use case 1", "Problematic use case 2"]
  }},
  "implementation_complexity": "moderate|high|very_high"
}}"""
        }
    
    def _load_rejected_concepts(self, ontology_file: str) -> List[Dict]:
        """Load rejected concepts from unified ontology"""
        with open(ontology_file, 'r') as f:
            ontology = json.load(f)
        
        rejected_concepts = ontology.get('rejected_concepts', [])
        logger.info(f"Loaded {len(rejected_concepts)} rejected concepts for negative knowledge analysis")
        return rejected_concepts
    
    def _load_complex_concepts(self, ontology_file: str) -> List[Dict]:
        """Load complex concepts from unified ontology"""
        with open(ontology_file, 'r') as f:
            ontology = json.load(f)
        
        # Get approved and modified concepts marked as complex
        complex_concepts = []
        
        for concept in ontology.get('approved_concepts', []):
            if concept.get('complexity') == 'complex':
                complex_concepts.append(concept)
        
        for concept in ontology.get('modified_concepts', []):
            if concept.get('complexity') == 'complex':
                complex_concepts.append(concept)
        
        logger.info(f"Loaded {len(complex_concepts)} complex concepts for detailed analysis")
        return complex_concepts
    
    def load_concepts_from_category(self, category: str, concepts_dir: str = "../concepts") -> Dict[str, List[Dict]]:
        """Load all concepts (high/medium/low) for a category"""
        concepts_path = Path(concepts_dir)
        
        category_concepts = {
            'high': [],
            'medium': [],
            'low': []
        }
        
        # Load high confidence (auto-approved JSON)
        high_file = concepts_path / f"{category}.json"
        if high_file.exists():
            try:
                with open(high_file, 'r') as f:
                    data = json.load(f)
                    category_concepts['high'] = data.get('concepts', [])
            except Exception as e:
                logger.warning(f"Error loading high confidence concepts for {category}: {e}")
        
        # Load medium confidence (review queue TXT)
        medium_file = concepts_path / f"{category}_review.txt"
        if medium_file.exists():
            try:
                category_concepts['medium'] = self._parse_review_file(medium_file, category)
            except Exception as e:
                logger.warning(f"Error loading medium confidence concepts for {category}: {e}")
        
        # Load low confidence (CSV)
        low_file = concepts_path / f"{category}_low_confidence.csv"
        if low_file.exists():
            try:
                category_concepts['low'] = self._parse_low_confidence_csv(low_file, category)
            except Exception as e:
                logger.warning(f"Error loading low confidence concepts for {category}: {e}")
        
        logger.info(f"Loaded {category}: {len(category_concepts['high'])} high, {len(category_concepts['medium'])} medium, {len(category_concepts['low'])} low confidence concepts")
        return category_concepts
    
    def _parse_review_file(self, file_path: Path, category: str) -> List[Dict]:
        """Parse review TXT file into concept dictionaries"""
        concepts = []
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Split by concept sections (assuming they're separated by double newlines or similar)
        concept_sections = re.split(r'\n\s*\n', content.strip())
        
        for section in concept_sections:
            if not section.strip():
                continue
                
            try:
                # Parse the section for key information
                lines = section.strip().split('\n')
                concept = {
                    'id': f"cendata:UnknownConcept_{len(concepts)}",
                    'label': 'Unknown Concept',
                    'universe': 'Unknown',
                    'stat_method': 'Unknown',
                    'definition': section,
                    'census_tables': [],
                    'status': 'medium_confidence',
                    'bucket': category
                }
                
                # Try to extract label from first line
                if lines:
                    first_line = lines[0].strip()
                    if first_line and not first_line.startswith('-'):
                        concept['label'] = first_line
                        concept['id'] = f"cendata:{first_line.replace(' ', '').replace('(', '').replace(')', '')}"
                
                concepts.append(concept)
                
            except Exception as e:
                logger.warning(f"Error parsing concept section: {e}")
                continue
        
        return concepts
    
    def _parse_low_confidence_csv(self, file_path: Path, category: str) -> List[Dict]:
        """Parse low confidence CSV into concept dictionaries"""
        concepts = []
        
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                concept = {
                    'id': f"cendata:{row['label'].replace(' ', '').replace('(', '').replace(')', '')}",
                    'label': row['label'],
                    'confidence': float(row['confidence']),
                    'universe': row['universe'],
                    'stat_method': row['stat_method'],
                    'definition': row['definition'],
                    'census_tables': [],  # Not provided in CSV
                    'status': 'low_confidence',
                    'bucket': category
                }
                concepts.append(concept)
        
        return concepts
    
    async def review_concept_with_llm(self, concept: Dict, use_openai: bool = True) -> Dict:
        """Review a single concept with LLM based on mode"""
        
        # Select prompt and prepare it based on mode
        if self.mode == "review":
            prompt = self.prompts["review"].format(
                label=concept.get('label', 'Unknown'),
                universe=concept.get('universe', 'Unknown'),
                stat_method=concept.get('stat_method', 'Unknown'),
                census_tables=concept.get('census_tables', []),
                definition=concept.get('definition', 'No definition provided')
            )
        elif self.mode == "negative_knowledge":
            prompt = self.prompts["negative_knowledge"].format(
                label=concept.get('label', 'Unknown'),
                universe=concept.get('universe', 'Unknown'),
                definition=concept.get('definition', 'No definition provided'),
                reasoning=concept.get('reasoning', 'No reasoning provided')
            )
        elif self.mode == "complex_analysis":
            prompt = self.prompts["complex_analysis"].format(
                label=concept.get('label', 'Unknown'),
                universe=concept.get('universe', 'Unknown'),
                stat_method=concept.get('stat_method', 'Unknown'),
                census_tables=concept.get('census_tables', []),
                definition=concept.get('definition', 'No definition provided'),
                implementation_notes=concept.get('implementation_notes', 'None provided')
            )
        else:
            raise ValueError(f"Unknown mode: {self.mode}")
        
        try:
            # Call appropriate LLM
            if use_openai:
                model = "gpt-4o"
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an expert statistical analyst with deep knowledge of US Census methodology. You understand survey design, sampling methodology, and the specific structure of American Community Survey data."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )
                review_text = response.choices[0].message.content
            else:
                # Use Claude Opus 4 for complex analysis, Sonnet for others
                if self.mode == "complex_analysis":
                    model = "claude-opus-4-20250514"
                    max_tokens = 2000
                    
                    try:
                        response = await self.anthropic_client.messages.create(
                            model=model,
                            max_tokens=max_tokens,
                            system="You are an expert statistical analyst with deep knowledge of US Census methodology. You focus on the validity and soundness of statistical approaches across domains.",
                            messages=[
                                {"role": "user", "content": prompt}
                            ]
                        )
                        review_text = response.content[0].text
                    except Exception as e:
                        if "model" in str(e).lower() or "not found" in str(e).lower():
                            logger.warning(f"⚠️  Claude Opus 4 not available, falling back to Sonnet 4 for complex analysis")
                            model = "claude-sonnet-4-20250514"
                            response = await self.anthropic_client.messages.create(
                                model=model,
                                max_tokens=max_tokens,
                                system="You are an expert statistical analyst with deep knowledge of US Census methodology. You focus on the validity and soundness of statistical approaches across domains.",
                                messages=[
                                    {"role": "user", "content": prompt}
                                ]
                            )
                            review_text = response.content[0].text
                        else:
                            raise e
                else:
                    model = "claude-3-5-sonnet-20241022"
                    response = await self.anthropic_client.messages.create(
                        model=model,
                        max_tokens=1500,
                        system="You are an expert statistical analyst with deep knowledge of US Census methodology. You focus on the validity and soundness of statistical approaches across domains.",
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
                    review_text = response.content[0].text
            
            # Parse JSON response
            try:
                # Extract JSON from response (handle markdown code blocks)
                json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', review_text, re.DOTALL)
                if json_match:
                    review_text = json_match.group(1)
                
                review_result = json.loads(review_text)
                
                # Add metadata
                review_result['llm_used'] = model
                review_result['reviewed_at'] = datetime.now().isoformat()
                review_result['original_concept'] = concept
                review_result['mode'] = self.mode
                
                return review_result
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for {concept.get('label', 'unknown')}: {e}")
                logger.error(f"Raw response: {review_text}")
                return {
                    'validation_decision': 'ERROR',
                    'error': f"JSON parsing failed: {e}",
                    'raw_response': review_text,
                    'original_concept': concept
                }
        
        except Exception as e:
            logger.error(f"LLM review error for {concept.get('label', 'unknown')}: {e}")
            self.review_results['processing_errors'].append({
                'concept': concept.get('label', 'unknown'),
                'error': str(e)
            })
            return {
                'validation_decision': 'ERROR',
                'error': str(e),
                'original_concept': concept
            }
    
    async def process_concepts(self, concepts: List[Dict]) -> Dict[str, Any]:
        """Process concepts based on mode"""
        
        all_reviewed_concepts = []
        
        logger.info(f"\n🔍 Processing {len(concepts)} concepts in {self.mode} mode...")
        
        for i, concept in enumerate(concepts):
            # Skip high-confidence concepts in review mode only
            if self.mode == "review" and concept.get('confidence_level') == 'high':
                review_result = {
                    'validation_decision': 'approve',
                    'reasoning': 'Auto-approved (high confidence)',
                    'confidence': 1.0,
                    'complexity_rating': 'simple',
                    'original_concept': concept,
                    'reviewed_at': datetime.now().isoformat(),
                    'llm_used': 'auto'
                }
            else:
                # Alternate between OpenAI and Anthropic for review and negative_knowledge modes
                # Use only Anthropic for complex_analysis (Opus 4 preferred)
                if self.mode == "complex_analysis":
                    use_openai = False
                else:
                    use_openai = (i % 2 == 0)  # Alternate for review and negative_knowledge
                review_result = await self.review_concept_with_llm(concept, use_openai)
            
            all_reviewed_concepts.append(review_result)
            
            # Update counters
            decision = review_result.get('validation_decision', 'ERROR')
            if decision == 'approve':
                self.review_results['approved'] += 1
            elif decision == 'modify':
                self.review_results['modified'] += 1
            elif decision == 'reject':
                self.review_results['rejected'] += 1
            
            self.review_results['total_reviewed'] += 1
            
            # Progress logging
            if (i + 1) % 10 == 0:
                logger.info(f"✅ Processed {i + 1}/{len(concepts)} concepts")
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        return all_reviewed_concepts
    
    def load_all_concepts(self, categories: List[str], concepts_dir: str) -> List[Dict]:
        """Load concepts from category files (original functionality)"""
        all_concepts = []
        
        for category in categories:
            logger.info(f"\n🔍 Loading {category} concepts...")
            category_concepts = self.load_concepts_from_category(category, concepts_dir)
            
            # Flatten and add to all_concepts
            for confidence_level in ['high', 'medium', 'low']:
                for concept in category_concepts[confidence_level]:
                    concept['category'] = category
                    concept['confidence_level'] = confidence_level
                    all_concepts.append(concept)
        
        return all_concepts
    
    async def run_review(self, categories: List[str], concepts_dir: str) -> Dict[str, Any]:
        """Run concept review (original mode)"""
        
        # Load all concepts
        all_concepts = self.load_all_concepts(categories, concepts_dir)
        
        # Process concepts
        all_reviewed_concepts = await self.process_concepts(all_concepts)
        
        # Organize results by decision
        results = {
            'approved_concepts': [],
            'modified_concepts': [],
            'rejected_concepts': [],
            'error_concepts': [],
            'summary': self.review_results,
            'generated_at': datetime.now().isoformat()
        }
        
        for review in all_reviewed_concepts:
            decision = review.get('validation_decision', 'ERROR')
            if decision == 'approve':
                results['approved_concepts'].append(review)
            elif decision == 'modify':
                results['modified_concepts'].append(review)
            elif decision == 'reject':
                results['rejected_concepts'].append(review)
            else:
                results['error_concepts'].append(review)
        
        return results
    
    async def run_negative_knowledge(self, ontology_file: str) -> Dict[str, Any]:
        """Run negative knowledge analysis"""
        
        # Load rejected concepts
        rejected_concepts = self._load_rejected_concepts(ontology_file)
        
        # Process concepts
        analyzed_concepts = await self.process_concepts(rejected_concepts)
        
        # Organize results by rejection category
        results = {
            'negative_knowledge_taxonomy': {},
            'analyzed_concepts': analyzed_concepts,
            'summary': {
                'total_analyzed': len(analyzed_concepts),
                'categories': {}
            },
            'generated_at': datetime.now().isoformat()
        }
        
        # Group by rejection category
        for analysis in analyzed_concepts:
            category = analysis.get('rejection_category', 'uncategorized')
            if category not in results['negative_knowledge_taxonomy']:
                results['negative_knowledge_taxonomy'][category] = []
            results['negative_knowledge_taxonomy'][category].append(analysis)
            
            # Update category counts
            if category not in results['summary']['categories']:
                results['summary']['categories'][category] = 0
            results['summary']['categories'][category] += 1
        
        return results
    
    async def run_complex_analysis(self, ontology_file: str) -> Dict[str, Any]:
        """Run complex concept analysis"""
        
        # Load complex concepts
        complex_concepts = self._load_complex_concepts(ontology_file)
        
        # Process concepts
        analyzed_concepts = await self.process_concepts(complex_concepts)
        
        # Organize results by complexity level
        results = {
            'complex_implementation_strategies': analyzed_concepts,
            'summary': {
                'total_analyzed': len(analyzed_concepts),
                'complexity_distribution': {}
            },
            'generated_at': datetime.now().isoformat()
        }
        
        # Group by implementation complexity
        for analysis in analyzed_concepts:
            complexity = analysis.get('implementation_complexity', 'unknown')
            if complexity not in results['summary']['complexity_distribution']:
                results['summary']['complexity_distribution'][complexity] = 0
            results['summary']['complexity_distribution'][complexity] += 1
        
        return results

async def main():
    parser = argparse.ArgumentParser(description='LLM-powered concept reviewer with multiple modes')
    parser.add_argument('--openai-api-key', required=True, help='OpenAI API key')
    parser.add_argument('--anthropic-api-key', required=True, help='Anthropic API key')
    parser.add_argument('--mode', choices=['review', 'negative_knowledge', 'complex_analysis'],
                        default='review', help='Review mode')
    parser.add_argument('--concepts-dir', default='../concepts', help='Directory containing concept files')
    parser.add_argument('--ontology-file', help='Unified ontology file (required for negative_knowledge and complex_analysis modes)')
    parser.add_argument('--output', help='Output file path (auto-generated if not specified)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.mode in ['negative_knowledge', 'complex_analysis'] and not args.ontology_file:
        parser.error(f"--ontology-file is required for {args.mode} mode")
    
    # Initialize reviewer
    reviewer = LLMConceptReviewer(args.openai_api_key, args.anthropic_api_key, args.mode)
    
    # Run based on mode
    if args.mode == 'review':
        categories = ['core_demographics', 'economics', 'education', 'geography',
                     'health_social', 'housing', 'specialized_populations', 'transportation']
        results = await reviewer.run_review(categories, args.concepts_dir)
        default_output = 'COOS_Complete_Ontology.json'
        
    elif args.mode == 'negative_knowledge':
        results = await reviewer.run_negative_knowledge(args.ontology_file)
        default_output = 'COOS_Negative_Knowledge.json'
        
    elif args.mode == 'complex_analysis':
        results = await reviewer.run_complex_analysis(args.ontology_file)
        default_output = 'COOS_Complex_Analysis.json'
    
    # Save results
    output_file = args.output or default_output
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\n✅ {args.mode.title()} complete! Results saved to {output_file}")
    
    # Print summary
    if args.mode == 'review':
        summary = results['summary']
        logger.info(f"📊 Summary: {summary['total_reviewed']} concepts reviewed")
        logger.info(f"   ✅ Approved: {summary['approved']}")
        logger.info(f"   ✏️  Modified: {summary['modified']}")
        logger.info(f"   ❌ Rejected: {summary['rejected']}")
        logger.info(f"   🚫 Errors: {len(summary['processing_errors'])}")
        
    elif args.mode == 'negative_knowledge':
        summary = results['summary']
        logger.info(f"📊 Summary: {summary['total_analyzed']} rejected concepts analyzed")
        for category, count in summary['categories'].items():
            logger.info(f"   📂 {category}: {count}")
            
    elif args.mode == 'complex_analysis':
        summary = results['summary']
        logger.info(f"📊 Summary: {summary['total_analyzed']} complex concepts analyzed")
        for complexity, count in summary['complexity_distribution'].items():
            logger.info(f"   🔧 {complexity}: {count}")

if __name__ == "__main__":
    asyncio.run(main())
