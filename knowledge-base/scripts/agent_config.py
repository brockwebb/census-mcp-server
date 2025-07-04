"""
Agent Configuration Loader for COOS Framework
Loads and manages agent ensemble configuration
"""

import yaml
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)

class AgentConfig:
    """Load and manage agent ensemble configuration"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize agent configuration
        
        Args:
            config_path: Path to agent_config.yaml file
        """
        if config_path is None:
            # Default to agent_config.yaml in same directory as this script
            config_path = Path(__file__).parent / "agent_config.yaml"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded agent config from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Agent config file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing agent config YAML: {e}")
            raise
    
    def _validate_config(self):
        """Validate configuration structure"""
        required_sections = ['processing_strategies', 'agents', 'routing_rules']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required config section: {section}")
        
        # Validate agent definitions
        for agent_name, agent_config in self.config['agents'].items():
            if 'model' not in agent_config:
                raise ValueError(f"Agent {agent_name} missing 'model' field")
    
    def get_processing_strategy(self, strategy_name: str) -> Dict:
        """Get processing strategy configuration"""
        strategies = self.config['processing_strategies']
        if strategy_name not in strategies:
            raise ValueError(f"Unknown processing strategy: {strategy_name}")
        return strategies[strategy_name]
    
    def get_agent_config(self, agent_name: str) -> Dict:
        """Get agent configuration"""
        agents = self.config['agents']
        if agent_name not in agents:
            raise ValueError(f"Unknown agent: {agent_name}")
        return agents[agent_name]
    
    def get_table_routing(self, table_id: str) -> List[str]:
        """
        Get list of agents for a given table ID
        
        Args:
            table_id: Census table ID (e.g., "B19013", "B25001")
            
        Returns:
            List of agent names to use for this table
        """
        routing = self.config['routing_rules']['table_routing']
        
        # Extract table family (first 3 characters)
        table_family = table_id[:3] if len(table_id) >= 3 else table_id
        
        # Check for specific table family routing
        if table_family in routing:
            return routing[table_family]['agents']
        
        # Fall back to DEFAULT routing
        if 'DEFAULT' in routing:
            return routing['DEFAULT']['agents']
        
        # Ultimate fallback
        logger.warning(f"No routing found for table {table_id}, using census_specialist only")
        return ['census_specialist']
    
    def get_routing_complexity(self, table_id: str) -> str:
        """Get complexity level for a table"""
        routing = self.config['routing_rules']['table_routing']
        table_family = table_id[:3] if len(table_id) >= 3 else table_id
        
        if table_family in routing:
            return routing[table_family].get('complexity', 'medium')
        return routing.get('DEFAULT', {}).get('complexity', 'medium')
    
    def should_use_coos_strategy(self, variable_id: str, coos_variables: set) -> bool:
        """
        Determine if variable should use COOS strategy or bulk strategy
        
        Args:
            variable_id: Census variable ID
            coos_variables: Set of variables in COOS taxonomy
            
        Returns:
            True if should use COOS multi-agent strategy, False for bulk single-agent
        """
        return variable_id in coos_variables
    
    def get_cost_estimate(self, num_variables: int, strategy: str = 'hybrid') -> Dict:
        """
        Estimate costs for processing variables
        
        Args:
            num_variables: Number of variables to process
            strategy: 'coos_concepts', 'bulk_variables', or 'hybrid'
            
        Returns:
            Cost breakdown dictionary
        """
        cost_config = self.config['cost_management']['target_costs']
        
        if strategy == 'coos_concepts':
            total_cost = num_variables * cost_config['coos_concepts']
            return {
                'total_cost': total_cost,
                'cost_per_variable': cost_config['coos_concepts'],
                'strategy': 'Multi-agent ensemble',
                'variables': num_variables
            }
        
        elif strategy == 'bulk_variables':
            total_cost = num_variables * cost_config['bulk_variables']
            return {
                'total_cost': total_cost,
                'cost_per_variable': cost_config['bulk_variables'],
                'strategy': 'Single agent',
                'variables': num_variables
            }
        
        elif strategy == 'hybrid':
            # Assume 20% COOS variables, 80% bulk
            coos_vars = int(num_variables * 0.2)
            bulk_vars = num_variables - coos_vars
            
            coos_cost = coos_vars * cost_config['coos_concepts']
            bulk_cost = bulk_vars * cost_config['bulk_variables']
            total_cost = coos_cost + bulk_cost
            
            return {
                'total_cost': total_cost,
                'coos_cost': coos_cost,
                'bulk_cost': bulk_cost,
                'coos_variables': coos_vars,
                'bulk_variables': bulk_vars,
                'strategy': 'Hybrid',
                'average_cost_per_variable': total_cost / num_variables
            }
    
    def get_quality_control_config(self) -> Dict:
        """Get quality control configuration"""
        return self.config.get('quality_control', {})
    
    def get_execution_config(self) -> Dict:
        """Get execution configuration"""
        return self.config.get('execution', {})
    
    def should_enable_arbitration(self) -> bool:
        """Check if arbitration is enabled"""
        qc_config = self.get_quality_control_config()
        return qc_config.get('arbitration', {}).get('enabled', True)
    
    def get_agreement_threshold(self) -> float:
        """Get agreement threshold for consensus"""
        qc_config = self.get_quality_control_config()
        return qc_config.get('agreement_scoring', {}).get('threshold', 0.4)
    
    def get_arbitrator_model(self) -> str:
        """Get model to use for arbitration"""
        qc_config = self.get_quality_control_config()
        return qc_config.get('arbitration', {}).get('arbitrator_model', 'claude-3-5-sonnet-20241022')
    
    def print_config_summary(self):
        """Print configuration summary"""
        print(f"🔧 Agent Configuration Summary")
        print(f"   Config file: {self.config_path}")
        print(f"   Framework: {self.config.get('framework_name', 'Unknown')}")
        
        # Processing strategies
        strategies = self.config['processing_strategies']
        print(f"\n📋 Processing Strategies:")
        for name, strategy in strategies.items():
            if strategy.get('enabled', True):
                cost = strategy.get('estimated_cost_per_variable', 'Unknown')
                print(f"   ✅ {name}: ${cost} per variable")
            else:
                print(f"   ❌ {name}: Disabled")
        
        # Agents
        agents = self.config['agents']
        print(f"\n🤖 Available Agents ({len(agents)}):")
        for name, agent in agents.items():
            model = agent.get('model', 'Unknown')
            always = " (Always)" if agent.get('always_included', False) else ""
            print(f"   • {name}: {model}{always}")
        
        # Cost estimates
        cost_config = self.config['cost_management']['target_costs']
        print(f"\n💰 Cost Targets:")
        print(f"   COOS concepts: ${cost_config['coos_concepts']} per variable")
        print(f"   Bulk variables: ${cost_config['bulk_variables']} per variable")
        print(f"   Total budget: ${cost_config['total_budget']}")


def load_agent_config(config_path: Optional[str] = None) -> AgentConfig:
    """Convenience function to load agent configuration"""
    return AgentConfig(config_path)


# Example usage
if __name__ == "__main__":
    # Test the configuration loader
    config = load_agent_config()
    config.print_config_summary()
    
    # Test table routing
    test_tables = ['B19013', 'B25001', 'B08301', 'B17001']
    print(f"\n🗺️  Table Routing Examples:")
    for table in test_tables:
        agents = config.get_table_routing(table)
        complexity = config.get_routing_complexity(table)
        print(f"   {table}: {agents} ({complexity} complexity)")
    
    # Test cost estimation
    print(f"\n💵 Cost Estimates:")
    estimates = [
        config.get_cost_estimate(2000, 'coos_concepts'),
        config.get_cost_estimate(26000, 'bulk_variables'),
        config.get_cost_estimate(28000, 'hybrid')
    ]
    
    for est in estimates:
        print(f"   {est['strategy']}: ${est['total_cost']:.2f} for {est.get('variables', 'N/A')} variables")
