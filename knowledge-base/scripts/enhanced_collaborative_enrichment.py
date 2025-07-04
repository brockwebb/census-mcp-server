#!/usr/bin/env python3
"""
Enhanced Collaborative Enrichment with Configurable Agent Framework
Census variable enrichment using agreement-based domain specialist ensemble
"""

import json
import time
import argparse
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml
import asyncio
from threading import Lock

# Import API clients
try:
    from openai import OpenAI
    import anthropic
except ImportError as e:
    print(f"Missing required packages: {e}")
    print("Install with: pip install openai anthropic")
    exit(1)

# Import sentence transformers for agreement scoring
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError as e:
    print(f"Missing sentence-transformers: {e}")
    print("Install with: pip install sentence-transformers")
    exit(1)

# Import agent configuration
from agent_config import load_agent_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Container for enrichment results"""
    variable_id: str
    enrichment: str
    agents_used: List[str]
    agent_responses: int
    agreement_score: float
    processing_cost: float
    strategy: str
    processing_time: float
    timestamp: float
    metadata: Dict = None


class ConfigurableCollaborativeEnrichment:
    """Enhanced collaborative enrichment using configurable agent framework"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize with configuration"""
        # Load agent configuration
        self.agent_config = load_agent_config(config_path)
        
        # Initialize API clients (will be set later)
        self.openai_client = None
        self.claude_client = None
        
        # Rate limiting
        self.last_openai_call = 0
        self.last_claude_call = 0
        self.openai_call_lock = Lock()
        self.claude_call_lock = Lock()
        
        # Rate limits (requests per minute)
        self.openai_rpm_limit = 500  # Conservative for GPT-4.1-mini
        self.claude_rpm_limit = 50   # Conservative for Claude
        
        # Calculate minimum delays
        self.openai_min_delay = 60.0 / self.openai_rpm_limit  # seconds between calls
        self.claude_min_delay = 60.0 / self.claude_rpm_limit
        
        # Initialize sentence transformer for agreement scoring
        if self.agent_config.get_quality_control_config().get('agreement_scoring', {}).get('enabled', True):
            model_name = self.agent_config.get_quality_control_config().get('agreement_scoring', {}).get('model', 'all-MiniLM-L6-v2')
            self.agreement_model = SentenceTransformer(model_name)
            logger.info(f"Loaded agreement scoring model: {model_name}")
        else:
            self.agreement_model = None
        
        # Runtime state
        self.total_cost = 0.0
        self.processed_count = 0
        self.arbitration_count = 0
        
        # Quality control config
        self.qc_config = self.agent_config.get_quality_control_config()
        self.agreement_threshold = self.agent_config.get_agreement_threshold()
        
        logger.info(f"Rate limits: OpenAI {self.openai_rpm_limit} RPM, Claude {self.claude_rpm_limit} RPM")
        
    def initialize_api_clients(self, openai_api_key: str, claude_api_key: str):
        """Initialize API clients"""
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
        logger.info("Initialized API clients")
        
    def get_agents_for_variable(self, variable_id: str, coos_variables: Set[str]) -> List[str]:
        """
        Determine which agents to use for a variable based on config
        
        Args:
            variable_id: Census variable ID
            coos_variables: Set of COOS curated variables
            
        Returns:
            List of agent names to use
        """
        # Check if this is a COOS variable requiring multi-agent treatment
        if self.agent_config.should_use_coos_strategy(variable_id, coos_variables):
            # Use table-based routing for COOS variables
            return self.agent_config.get_table_routing(variable_id)
        else:
            # Use single census specialist for bulk variables
            return ['census_specialist']
    
    def _build_system_prompt(self, agent_config: Dict) -> str:
        """Build system prompt based on agent configuration"""
        expertise = agent_config.get('expertise', [])
        role = agent_config.get('role', 'Census Data Analyst')
        
        system_prompt = f"""You are a {role} with expertise in:
{chr(10).join('• ' + item for item in expertise)}

Your task is to analyze Census variable data and provide detailed insights about:
1. Statistical methodology and data collection approach
2. Key limitations and measurement caveats  
3. Appropriate interpretation guidelines
4. Universe and coverage considerations
5. Relationship to other related variables

Focus on your domain expertise and provide actionable insights for researchers using this data.
Be specific about statistical limitations, proxy variables, and methodological concerns.
"""
        return system_prompt
    
    def _call_openai_agent(self, model: str, variable_data: Dict, prompt: str, agent_config: Dict) -> str:
        """Call OpenAI agent with rate limiting"""
        
        # Rate limiting for OpenAI
        with self.openai_call_lock:
            time_since_last = time.time() - self.last_openai_call
            if time_since_last < self.openai_min_delay:
                sleep_time = self.openai_min_delay - time_since_last
                logger.debug(f"OpenAI rate limit: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
            self.last_openai_call = time.time()
        
        system_prompt = self._build_system_prompt(agent_config)
        
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            return response.choices[0].message.content
            
        except Exception as e:
            if "rate_limit" in str(e).lower():
                logger.warning(f"OpenAI rate limit hit, waiting 60s...")
                time.sleep(60)
                return self._call_openai_agent(model, variable_data, prompt, agent_config)
            logger.error(f"OpenAI API error for {model}: {e}")
            return f"Error: Could not get response from {model}"
    
    def _call_claude_agent(self, model: str, variable_data: Dict, prompt: str, agent_config: Dict) -> str:
        """Call Claude agent with rate limiting"""
        
        # Rate limiting for Claude
        with self.claude_call_lock:
            time_since_last = time.time() - self.last_claude_call
            if time_since_last < self.claude_min_delay:
                sleep_time = self.claude_min_delay - time_since_last
                logger.debug(f"Claude rate limit: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
            self.last_claude_call = time.time()
        
        system_prompt = self._build_system_prompt(agent_config)
        
        try:
            message = self.claude_client.messages.create(
                model=model,
                max_tokens=1000,
                temperature=0.1,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
            
        except Exception as e:
            if "rate_limit" in str(e).lower():
                logger.warning(f"Claude rate limit hit, waiting 60s...")
                time.sleep(60)
                return self._call_claude_agent(model, variable_data, prompt, agent_config)
            logger.error(f"Claude API error for {model}: {e}")
            return f"Error: Could not get response from {model}"
    
    def _estimate_call_cost(self, model: str, prompt: str, response: str) -> float:
        """Estimate cost of API call"""
        pricing = self.agent_config.config.get('cost_management', {}).get('model_pricing', {})
        
        if model not in pricing:
            return 0.0  # Unknown model cost
        
        model_pricing = pricing[model]
        
        # Rough token estimation (4 characters per token)
        input_tokens = len(prompt) / 4
        output_tokens = len(response) / 4
        
        input_cost = (input_tokens / 1_000_000) * model_pricing['input']
        output_cost = (output_tokens / 1_000_000) * model_pricing['output']
        
        return input_cost + output_cost
    
    def call_agent(self, agent_name: str, variable_data: Dict, prompt: str) -> Dict:
        """
        Call a specific agent based on configuration
        
        Args:
            agent_name: Name of agent from config
            variable_data: Census variable data
            prompt: Analysis prompt
            
        Returns:
            Agent response with metadata
        """
        agent_config = self.agent_config.get_agent_config(agent_name)
        model = agent_config['model']
        
        start_time = time.time()
        
        if model.startswith('gpt-'):
            # OpenAI models
            response = self._call_openai_agent(model, variable_data, prompt, agent_config)
        elif model.startswith('claude-'):
            # Anthropic models
            response = self._call_claude_agent(model, variable_data, prompt, agent_config)
        else:
            raise ValueError(f"Unknown model type: {model}")
        
        end_time = time.time()
        cost = self._estimate_call_cost(model, prompt, response)
        
        return {
            'agent_name': agent_name,
            'model': model,
            'response': response,
            'processing_time': end_time - start_time,
            'cost': cost,
            'tokens_estimated': len(prompt + response) // 4
        }
    
    def _calculate_agreement_score(self, agent_responses: List[Dict]) -> float:
        """Calculate agreement score between agent responses"""
        if not self.agreement_model or len(agent_responses) < 2:
            return 1.0
        
        try:
            responses = [resp['response'] for resp in agent_responses]
            embeddings = self.agreement_model.encode(responses)
            
            # Calculate pairwise similarities
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    similarity = np.dot(embeddings[i], embeddings[j]) / (
                        np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                    )
                    similarities.append(similarity)
            
            return float(np.mean(similarities)) if similarities else 1.0
            
        except Exception as e:
            logger.warning(f"Agreement calculation failed: {e}")
            return 0.5  # Conservative estimate
    
    def _synthesize_agent_responses(self, agent_responses: List[Dict], variable_data: Dict) -> str:
        """Synthesize multiple agent responses into coherent analysis"""
        if len(agent_responses) == 1:
            return agent_responses[0]['response']
        
        # For multiple agents, create synthesis
        synthesis_parts = []
        
        # Add header
        agents_used = [resp['agent_name'] for resp in agent_responses]
        synthesis_parts.append(f"Multi-specialist analysis from: {', '.join(agents_used)}")
        synthesis_parts.append("")
        
        # Combine insights
        for i, resp in enumerate(agent_responses):
            agent_name = resp['agent_name'].replace('_', ' ').title()
            synthesis_parts.append(f"**{agent_name} Analysis:**")
            synthesis_parts.append(resp['response'])
            synthesis_parts.append("")
        
        return "\n".join(synthesis_parts)
    
    def _perform_arbitration(self, agent_responses: List[Dict], variable_data: Dict, agreement_score: float) -> str:
        """Perform Claude arbitration for low-agreement responses"""
        self.arbitration_count += 1
        logger.info(f"Performing arbitration for variable {variable_data.get('label', 'Unknown')} (agreement: {agreement_score:.3f})")
        
        arbitrator_model = self.agent_config.get_arbitrator_model()
        
        # Build arbitration prompt
        responses_text = "\n\n".join([
            f"**{resp['agent_name']}**: {resp['response']}"
            for resp in agent_responses
        ])
        
        arbitration_prompt = f"""
You are reviewing multiple expert analyses of a Census variable that show significant disagreement (agreement score: {agreement_score:.3f}).

Variable: {variable_data.get('label', 'Unknown')}
Concept: {variable_data.get('concept', 'Unknown')}

Expert Analyses:
{responses_text}

Please provide a balanced synthesis that:
1. Identifies areas of agreement between experts
2. Addresses conflicting interpretations with evidence
3. Provides clear, actionable guidance for researchers
4. Highlights genuine uncertainty where experts disagree

Your synthesis should be authoritative yet acknowledge limitations.
"""
        
        try:
            if arbitrator_model.startswith('claude-'):
                message = self.claude_client.messages.create(
                    model=arbitrator_model,
                    max_tokens=1200,
                    temperature=0.1,
                    system="You are an expert Census methodology arbitrator resolving disagreements between domain specialists.",
                    messages=[{"role": "user", "content": arbitration_prompt}]
                )
                arbitrated_response = message.content[0].text
                
                # Track arbitration cost
                arbitration_cost = self._estimate_call_cost(arbitrator_model, arbitration_prompt, arbitrated_response)
                self.total_cost += arbitration_cost
                
                return f"**Arbitrated Analysis (Agreement: {agreement_score:.3f})**\n\n{arbitrated_response}"
                
            else:
                logger.error(f"Unsupported arbitrator model: {arbitrator_model}")
                return self._synthesize_agent_responses(agent_responses, variable_data)
                
        except Exception as e:
            logger.error(f"Arbitration failed: {e}")
            return self._synthesize_agent_responses(agent_responses, variable_data)
    
    def process_variable_with_config(self, variable_id: str, variable_data: Dict, coos_variables: Set[str]) -> EnrichmentResult:
        """
        Process a single variable using configuration-driven agent selection
        
        Args:
            variable_id: Census variable ID
            variable_data: Variable metadata
            coos_variables: Set of COOS curated variables
            
        Returns:
            Enrichment results with agent metadata
        """
        start_time = time.time()
        
        # Determine which agents to use
        agent_names = self.get_agents_for_variable(variable_id, coos_variables)
        
        # Build analysis prompt
        prompt = f"""
Census Variable Analysis Request:

Variable ID: {variable_id}
Label: {variable_data.get('label', 'Unknown')}
Concept: {variable_data.get('concept', 'Unknown')}
Universe: {variable_data.get('universe', 'Unknown')}

Please provide a comprehensive analysis including:
1. Statistical methodology and data collection approach
2. Key limitations and measurement caveats
3. Appropriate interpretation guidelines
4. Universe and coverage considerations
5. Relationship to other related variables

Focus on your domain expertise and provide actionable insights for researchers using this data.
Be specific about statistical limitations, proxy variables, and methodological concerns.
"""
        
        # Call agents in parallel for same variable (much faster)
        agent_responses = []
        total_cost = 0.0
        
        logger.info(f"Processing {variable_id} with {len(agent_names)} agents in parallel: {agent_names}")
        
        if len(agent_names) == 1:
            # Single agent - no need for parallel processing
            try:
                result = self.call_agent(agent_names[0], variable_data, prompt)
                agent_responses.append(result)
                total_cost += result['cost']
            except Exception as e:
                logger.error(f"Error calling agent {agent_names[0]}: {e}")
        else:
            # Multiple agents - process in parallel
            with ThreadPoolExecutor(max_workers=min(len(agent_names), 4)) as executor:
                # Submit all agent calls simultaneously
                future_to_agent = {
                    executor.submit(self.call_agent, agent_name, variable_data, prompt): agent_name
                    for agent_name in agent_names
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_agent):
                    agent_name = future_to_agent[future]
                    try:
                        result = future.result(timeout=60)  # 60 second timeout per agent
                        agent_responses.append(result)
                        total_cost += result['cost']
                    except Exception as e:
                        logger.error(f"Error calling agent {agent_name}: {e}")
                        continue
        
        # Calculate agreement score if multiple agents
        agreement_score = self._calculate_agreement_score(agent_responses) if len(agent_responses) > 1 else 1.0
        
        # Synthesize responses based on agreement
        if len(agent_responses) == 0:
            synthesis = "Error: No agent responses available"
        elif len(agent_responses) == 1:
            synthesis = agent_responses[0]['response']
        elif agreement_score >= self.agreement_threshold:
            # High agreement - simple synthesis
            synthesis = self._synthesize_agent_responses(agent_responses, variable_data)
        else:
            # Low agreement - trigger arbitration if enabled
            if self.agent_config.should_enable_arbitration():
                synthesis = self._perform_arbitration(agent_responses, variable_data, agreement_score)
            else:
                synthesis = self._synthesize_agent_responses(agent_responses, variable_data)
        
        # Track costs
        self.total_cost += total_cost
        self.processed_count += 1
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Determine strategy
        strategy = 'coos_concepts' if variable_id in coos_variables else 'bulk_variables'
        
        return EnrichmentResult(
            variable_id=variable_id,
            enrichment=synthesis,
            agents_used=agent_names,
            agent_responses=len(agent_responses),
            agreement_score=agreement_score,
            processing_cost=total_cost,
            strategy=strategy,
            processing_time=processing_time,
            timestamp=time.time(),
            metadata={
                'agent_details': agent_responses,
                'complexity': self.agent_config.get_routing_complexity(variable_id),
                'arbitration_triggered': agreement_score < self.agreement_threshold if len(agent_responses) > 1 else False
            }
        )


def load_coos_variables(coos_file: str) -> Set[str]:
    """Load COOS variable set from file"""
    if not coos_file or not os.path.exists(coos_file):
        return set()
    
    try:
        with open(coos_file, 'r') as f:
            coos_data = json.load(f)
        return set(coos_data.keys())
    except Exception as e:
        logger.warning(f"Could not load COOS variables from {coos_file}: {e}")
        return set()


def print_progress_report(enricher: ConfigurableCollaborativeEnrichment, processed: int, total: int):
    """Print progress report"""
    if enricher.processed_count == 0:
        return
    
    avg_cost = enricher.total_cost / enricher.processed_count
    arbitration_rate = enricher.arbitration_count / enricher.processed_count
    
    print(f"   Progress: {processed}/{total} | "
          f"Avg cost: ${avg_cost:.4f} | "
          f"Total: ${enricher.total_cost:.2f} | "
          f"Arbitration: {arbitration_rate:.1%}")


def save_results(results: List[EnrichmentResult], output_file: str):
    """Save enrichment results to JSON file without overwriting existing data"""
    # Load any existing results first
    existing_data = {}
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r') as f:
                existing_results = json.load(f)
            # Convert to dict by variable_id for easy merging
            for result in existing_results:
                if isinstance(result, dict) and 'variable_id' in result:
                    existing_data[result['variable_id']] = result
        except Exception as e:
            logger.warning(f"Could not load existing results: {e}")
    
    # Add new results (will overwrite if variable_id exists - that's intentional)
    for result in results:
        result_dict = {
            'variable_id': result.variable_id,
            'enrichment': result.enrichment,
            'agents_used': result.agents_used,
            'agent_responses': result.agent_responses,
            'agreement_score': result.agreement_score,
            'processing_cost': result.processing_cost,
            'strategy': result.strategy,
            'processing_time': result.processing_time,
            'timestamp': result.timestamp
        }
        if result.metadata:
            result_dict['metadata'] = result.metadata
        existing_data[result.variable_id] = result_dict
    
    # Save atomically to prevent corruption
    temp_file = output_file + '.tmp'
    with open(temp_file, 'w') as f:
        json.dump(list(existing_data.values()), f, indent=2)
    
    # Atomic rename
    os.rename(temp_file, output_file)


def load_existing_results(output_file: str) -> Dict[str, Dict]:
    """Load existing results if resuming"""
    if not os.path.exists(output_file):
        return {}
    
    try:
        with open(output_file, 'r') as f:
            existing_results = json.load(f)
        
        # Convert to lookup dict by variable_id
        processed_vars = {}
        for result in existing_results:
            if isinstance(result, dict) and 'variable_id' in result:
                processed_vars[result['variable_id']] = result
        
        logger.info(f"Found {len(processed_vars)} existing results in {output_file}")
        return processed_vars
        
    except Exception as e:
        logger.warning(f"Could not load existing results: {e}")
        return {}


def save_checkpoint(results: List[EnrichmentResult], output_file: str):
    """Save checkpoint during processing"""
    try:
        save_results(results, output_file)
        logger.info(f"Checkpoint saved: {len(results)} results")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")


def main():
    """Main execution function using configurable framework"""
    
    parser = argparse.ArgumentParser(description='Configurable Census Variable Enrichment')
    parser.add_argument('--input-file', required=True, help='Input JSON file with variables')
    parser.add_argument('--output-file', required=True, help='Output JSON file for results')
    parser.add_argument('--config-file', help='Agent configuration YAML file')
    parser.add_argument('--openai-api-key', required=True, help='OpenAI API key')
    parser.add_argument('--claude-api-key', required=True, help='Claude API key')
    parser.add_argument('--coos-variables', help='JSON file with COOS variable set')
    parser.add_argument('--dry-run', action='store_true', help='Show cost estimate without processing')
    parser.add_argument('--max-variables', type=int, help='Limit number of variables to process')
    parser.add_argument('--resume', action='store_true', help='Resume from existing results file')
    parser.add_argument('--checkpoint-interval', type=int, default=50, help='Save checkpoint every N variables')
    parser.add_argument('--openai-rpm', type=int, default=500, help='OpenAI requests per minute limit')
    parser.add_argument('--claude-rpm', type=int, default=50, help='Claude requests per minute limit')
    parser.add_argument('--variable-delay', type=float, default=1.0, help='Delay between variables (seconds)')
    parser.add_argument('--parallel-variables', type=int, default=1, help='Process N variables simultaneously')
    
    args = parser.parse_args()
    
    # Initialize configurable enrichment
    try:
        enricher = ConfigurableCollaborativeEnrichment(args.config_file)
        
        # Override rate limits if specified
        if args.openai_rpm:
            enricher.openai_rpm_limit = args.openai_rpm
            enricher.openai_min_delay = 60.0 / args.openai_rpm
        if args.claude_rpm:
            enricher.claude_rpm_limit = args.claude_rpm
            enricher.claude_min_delay = 60.0 / args.claude_rpm
            
        logger.info(f"Rate limits set: OpenAI {enricher.openai_rpm_limit} RPM, Claude {enricher.claude_rpm_limit} RPM")
        
        enricher.initialize_api_clients(args.openai_api_key, args.claude_api_key)
    except Exception as e:
        logger.error(f"Failed to initialize enricher: {e}")
        return 1
    
    # Load input data
    try:
        with open(args.input_file, 'r') as f:
            variables_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load input file {args.input_file}: {e}")
        return 1
    
    # Limit variables if requested
    if args.max_variables and args.max_variables < len(variables_data):
        var_items = list(variables_data.items())[:args.max_variables]
        variables_data = dict(var_items)
        logger.info(f"Limited to {args.max_variables} variables for testing")
    
    # Load COOS variables if provided
    coos_variables = load_coos_variables(args.coos_variables)
    
    # Load existing results if resuming
    existing_results = {}
    if args.resume:
        existing_results = load_existing_results(args.output_file)
        if existing_results:
            print(f"🔄 Resume mode: Found {len(existing_results)} existing results")
    
    # Filter out already processed variables
    if existing_results:
        original_count = len(variables_data)
        variables_data = {k: v for k, v in variables_data.items() if k not in existing_results}
        skipped_count = original_count - len(variables_data)
        print(f"   Skipping {skipped_count} already processed variables")
        print(f"   Remaining to process: {len(variables_data)}")
    
    print(f"🚀 Configurable Census Variable Enrichment")
    print(f"   Variables to process: {len(variables_data)}")
    print(f"   COOS variables: {len(coos_variables)}")
    
    # Print configuration summary
    enricher.agent_config.print_config_summary()
    
    # Cost estimation
    total_vars = len(variables_data)
    coos_vars = len([v for v in variables_data.keys() if v in coos_variables])
    bulk_vars = total_vars - coos_vars
    
    cost_config = enricher.agent_config.config['cost_management']['target_costs']
    coos_cost = coos_vars * cost_config['coos_concepts']
    bulk_cost = bulk_vars * cost_config['bulk_variables']
    total_estimated = coos_cost + bulk_cost
    
    print(f"\n💰 Cost Estimate:")
    print(f"   COOS variables: {coos_vars} × ${cost_config['coos_concepts']:.3f} = ${coos_cost:.2f}")
    print(f"   Bulk variables: {bulk_vars} × ${cost_config['bulk_variables']:.3f} = ${bulk_cost:.2f}")
    print(f"   Total estimated: ${total_estimated:.2f}")
    
    if args.dry_run:
        print("🔍 Dry run complete - no processing performed")
        return 0
    
    # Process variables
    results = []
    
    # Add existing results to the results list if resuming
    if existing_results:
        for result_dict in existing_results.values():
            # Convert dict back to EnrichmentResult
            result = EnrichmentResult(
                variable_id=result_dict['variable_id'],
                enrichment=result_dict['enrichment'],
                agents_used=result_dict['agents_used'],
                agent_responses=result_dict['agent_responses'],
                agreement_score=result_dict['agreement_score'],
                processing_cost=result_dict['processing_cost'],
                strategy=result_dict['strategy'],
                processing_time=result_dict['processing_time'],
                timestamp=result_dict['timestamp'],
                metadata=result_dict.get('metadata')
            )
            results.append(result)
        
        # Update enricher stats for existing results
        enricher.total_cost = sum(r.processing_cost for r in results)
        enricher.processed_count = len(results)
        print(f"📊 Resumed with ${enricher.total_cost:.2f} total cost from {len(results)} existing results")
    
    start_time = time.time()
    
    # Process variables in parallel batches
    variable_items = list(variables_data.items())
    batch_size = args.parallel_variables
    
    try:
        for batch_start in range(0, len(variable_items), batch_size):
            batch_end = min(batch_start + batch_size, len(variable_items))
            batch_items = variable_items[batch_start:batch_end]
            
            if batch_size == 1:
                # Single variable processing (original behavior)
                var_id, var_data = batch_items[0]
                total_processed = len(existing_results) + batch_start + 1
                total_vars = len(existing_results) + len(variables_data)
                
                print(f"📊 Processing {total_processed}/{total_vars}: {var_id}")
                
                result = enricher.process_variable_with_config(var_id, var_data, coos_variables)
                results.append(result)
                
                # Delay between variables
                if args.variable_delay > 0:
                    time.sleep(args.variable_delay)
            else:
                # Parallel variable processing
                batch_num = (batch_start // batch_size) + 1
                total_batches = (len(variable_items) + batch_size - 1) // batch_size
                variables_processed_so_far = len(existing_results) + batch_start
                total_vars = len(existing_results) + len(variables_data)
                
                print(f"📊 Processing batch {batch_num}/{total_batches} ({variables_processed_so_far}/{total_vars} variables): {len(batch_items)} variables in parallel")
                
                # Process batch in parallel using ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    # Submit all variables in batch simultaneously
                    future_to_var = {
                        executor.submit(enricher.process_variable_with_config, var_id, var_data, coos_variables): (var_id, var_data)
                        for var_id, var_data in batch_items
                    }
                    
                    # Collect results as they complete
                    batch_results = []
                    completed_in_batch = 0
                    for future in as_completed(future_to_var):
                        var_id, var_data = future_to_var[future]
                        try:
                            result = future.result(timeout=120)  # 2 minute timeout per variable
                            batch_results.append(result)
                            completed_in_batch += 1
                            total_completed = variables_processed_so_far + completed_in_batch
                            print(f"   ✅ Completed {completed_in_batch}/{len(batch_items)}: {var_id} ({total_completed}/{total_vars} total)")
                        except Exception as e:
                            logger.error(f"Error processing variable {var_id}: {e}")
                            # Create error result to maintain progress tracking
                            error_result = EnrichmentResult(
                                variable_id=var_id,
                                enrichment=f"Error: {str(e)}",
                                agents_used=[],
                                agent_responses=0,
                                agreement_score=0.0,
                                processing_cost=0.0,
                                strategy='error',
                                processing_time=0.0,
                                timestamp=time.time()
                            )
                            batch_results.append(error_result)
                            completed_in_batch += 1
                            total_completed = variables_processed_so_far + completed_in_batch
                            print(f"   ❌ Error {completed_in_batch}/{len(batch_items)}: {var_id} ({total_completed}/{total_vars} total)")
                    
                    results.extend(batch_results)
                
                # Brief pause between batches
                if args.variable_delay > 0:
                    time.sleep(args.variable_delay)
            
            # Progress update and checkpoint
            current_batch = (batch_start // batch_size) + 1
            total_processed = len(existing_results) + batch_end
            total_vars = len(existing_results) + len(variables_data)
            
            # Save checkpoint periodically
            if current_batch % (args.checkpoint_interval // batch_size) == 0:
                save_checkpoint(results, args.output_file)
                print(f"💾 Checkpoint saved at {total_processed}/{total_vars} variables")
            
            # Detailed progress update every few batches
            if current_batch % 5 == 0:  # Every 5 batches
                print_progress_report(enricher, total_processed, total_vars)
                elapsed_time = time.time() - start_time
                variables_per_minute = total_processed / (elapsed_time / 60) if elapsed_time > 0 else 0
                estimated_remaining = (total_vars - total_processed) / variables_per_minute if variables_per_minute > 0 else 0
                print(f"🚀 Performance: {variables_per_minute:.1f} variables/min | ETA: {estimated_remaining:.0f} minutes")
    
    except KeyboardInterrupt:
        print(f"\n⚠️ Processing interrupted. Saving {len(results)} completed results...")
    except Exception as e:
        logger.error(f"Processing error: {e}")
        print(f"⚠️ Error occurred. Saving {len(results)} completed results...")
    
    # Save results
    try:
        save_results(results, args.output_file)
    except Exception as e:
        logger.error(f"Failed to save results: {e}")
        return 1
    
    end_time = time.time()
    
    # Final summary
    print(f"\n✅ Processing complete!")
    print(f"   Total variables processed: {len(results)}")
    print(f"   Total cost: ${enricher.total_cost:.2f}")
    print(f"   Average cost per variable: ${enricher.total_cost / len(results):.4f}" if results else "   No variables processed")
    print(f"   Processing time: {end_time - start_time:.1f}s")
    print(f"   Arbitrations performed: {enricher.arbitration_count}")
    print(f"   Results saved to: {args.output_file}")
    
    # Strategy breakdown
    coos_results = [r for r in results if r.strategy == 'coos_concepts']
    bulk_results = [r for r in results if r.strategy == 'bulk_variables']
    
    if coos_results:
        coos_avg_cost = sum(r.processing_cost for r in coos_results) / len(coos_results)
        print(f"   COOS strategy: {len(coos_results)} variables, ${coos_avg_cost:.4f} avg cost")
    
    if bulk_results:
        bulk_avg_cost = sum(r.processing_cost for r in bulk_results) / len(bulk_results)
        print(f"   Bulk strategy: {len(bulk_results)} variables, ${bulk_avg_cost:.4f} avg cost")
    
    return 0


if __name__ == "__main__":
    exit(main())
