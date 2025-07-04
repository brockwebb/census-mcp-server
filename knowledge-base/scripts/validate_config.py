#!/usr/bin/env python3
"""
Validate configuration setup before running enrichment
"""

import sys
from pathlib import Path

def validate_config_setup():
    """Validate all components are ready"""
    
    print("🔧 Validating Configuration Setup")
    print("=" * 50)
    
    validation_passed = True
    
    # Check for required files
    required_files = {
        'agent_config.yaml': 'Agent configuration file',
        'agent_config.py': 'Configuration loader module', 
        'enhanced_collaborative_enrichment.py': 'Main enrichment script'
    }
    
    print("📁 Checking required files:")
    for filename, description in required_files.items():
        if Path(filename).exists():
            print(f"   ✅ {filename} - {description}")
        else:
            print(f"   ❌ {filename} - {description} (MISSING)")
            validation_passed = False
    
    # Check Python imports
    print(f"\n📦 Checking Python dependencies:")
    
    try:
        import yaml
        print("   ✅ PyYAML - Configuration parsing")
    except ImportError:
        print("   ❌ PyYAML (install with: pip install pyyaml)")
        validation_passed = False
    
    try:
        from openai import OpenAI
        print("   ✅ OpenAI - API client")
    except ImportError:
        print("   ❌ OpenAI (install with: pip install openai)")
        validation_passed = False
    
    try:
        import anthropic
        print("   ✅ Anthropic - Claude API client")
    except ImportError:
        print("   ❌ Anthropic (install with: pip install anthropic)")
        validation_passed = False
    
    try:
        from sentence_transformers import SentenceTransformer
        print("   ✅ Sentence Transformers - Agreement scoring")
    except ImportError:
        print("   ❌ Sentence Transformers (install with: pip install sentence-transformers)")
        validation_passed = False
    
    # Try to load config if available
    if Path('agent_config.yaml').exists():
        print(f"\n⚙️ Testing configuration loading:")
        try:
            # Add current directory to path for import
            sys.path.insert(0, str(Path.cwd()))
            from agent_config import load_agent_config
            
            config = load_agent_config('agent_config.yaml')
            print("   ✅ Configuration loaded successfully")
            
            # Test some basic config operations
            agents = list(config.config['agents'].keys())
            print(f"   ✅ Found {len(agents)} configured agents: {', '.join(agents)}")
            
            # Test table routing
            test_tables = ['B19013', 'B25001', 'B08301']
            print(f"   ✅ Table routing test:")
            for table in test_tables:
                routing = config.get_table_routing(table)
                complexity = config.get_routing_complexity(table)
                print(f"      {table}: {len(routing)} agents ({complexity})")
            
        except Exception as e:
            print(f"   ❌ Configuration loading failed: {e}")
            validation_passed = False
    
    # Check environment variables
    import os
    print(f"\n🔑 Checking API keys:")
    
    openai_key = os.getenv('OPENAI_API_KEY')
    claude_key = os.getenv('CLAUDE_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
    
    if openai_key:
        key_preview = f"{openai_key[:8]}...{openai_key[-4:]}" if len(openai_key) > 12 else "short_key"
        print(f"   ✅ OPENAI_API_KEY: {key_preview}")
    else:
        print(f"   ⚠️ OPENAI_API_KEY not set")
    
    if claude_key:
        key_preview = f"{claude_key[:8]}...{claude_key[-4:]}" if len(claude_key) > 12 else "short_key"
        print(f"   ✅ CLAUDE_API_KEY: {key_preview}")
    else:
        print(f"   ⚠️ CLAUDE_API_KEY/ANTHROPIC_API_KEY not set")
    
    # Look for data files
    print(f"\n📊 Checking for data files:")
    data_files = [
        'test_10_variables.json',
        'coos_variables_extracted.json',
        '../complete_2023_acs_variables/complete_variables.csv'
    ]
    
    found_data = False
    for data_file in data_files:
        if Path(data_file).exists():
            print(f"   ✅ {data_file}")
            found_data = True
        else:
            print(f"   ❌ {data_file} (not found)")
    
    if not found_data:
        print(f"   ⚠️ No data files found - run extract script first")
    
    # Summary
    print(f"\n" + "=" * 50)
    if validation_passed and found_data:
        print("🎉 Validation PASSED - Ready to run enrichment!")
        print(f"\n🚀 Suggested test command:")
        print(f"   python enhanced_collaborative_enrichment.py \\")
        print(f"     --input-file test_10_variables.json \\")
        print(f"     --output-file test_results.json \\")
        print(f"     --config-file agent_config.yaml \\")
        print(f"     --openai-api-key $OPENAI_API_KEY \\")
        print(f"     --claude-api-key $CLAUDE_API_KEY \\")
        print(f"     --dry-run")
        print(f"\n   (Remove --dry-run when ready to spend API credits)")
        return True
    else:
        print("❌ Validation FAILED - Fix issues above before proceeding")
        return False

if __name__ == "__main__":
    success = validate_config_setup()
    sys.exit(0 if success else 1)
