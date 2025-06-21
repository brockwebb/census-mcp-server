"""
Configuration management for Census MCP Server

Handles paths, environment variables, and settings for containerized deployment.
Supports both local development and Docker container environments.
UPDATED: Uses sentence transformers by default (no API key required)
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class Config:
    """
    Configuration manager for Census MCP Server.
    
    Loads settings from environment variables, config files, and defaults.
    Container-aware for seamless Docker deployment.
    Now uses sentence transformers by default for self-contained deployment.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_file: Optional path to JSON config file
        """
        self.config_file = config_file
        self._load_config()
        self._validate_config()
    
    def _load_config(self):
        """Load configuration from environment, files, and defaults."""
        
        # Base paths - container-aware
        # Fix: Go up to project root (census-mcp-server/) from utils/config.py
        self.base_dir = Path(os.getenv('CENSUS_MCP_BASE', Path(__file__).parent.parent.parent))
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.base_dir / "config"
        self.scripts_dir = self.base_dir / "scripts"
        
        # R Documentation Corpus
        self.r_docs_corpus_path = self.data_dir / "r_docs_corpus"
        
        # Vector Database
        self.vector_db_path = self.data_dir / "vector_db"
        self.vector_db_type = os.getenv('VECTOR_DB_TYPE', 'chromadb')  # chromadb, faiss
        
        # R Configuration
        self.r_executable = self._find_r_executable()
        self.r_script_path = self.scripts_dir / "census_data_retrieval.R"
        self.r_packages_check = os.getenv('R_PACKAGES_CHECK', 'true').lower() == 'true'
        
        # LLM Configuration (for future multi-LLM support)
        self.default_llm = os.getenv('DEFAULT_LLM', 'claude')
        self.claude_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')  # Optional now
        
        # Census API Configuration
        self.census_api_key = os.getenv('CENSUS_API_KEY')  # Optional but recommended
        
        # Embedding Configuration - UPDATED to use sentence transformers by default
        self.embedding_model = os.getenv('EMBEDDING_MODEL', 'all-mpnet-base-v2')  # Local model, no API key
        self.embedding_dimension = self._get_embedding_dimension()
        
        # Server Configuration
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.max_concurrent_requests = int(os.getenv('MAX_CONCURRENT_REQUESTS', '10'))
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '300'))  # 5 minutes
        
        # Vector Search Configuration
        self.vector_search_top_k = int(os.getenv('VECTOR_SEARCH_TOP_K', '5'))
        self.vector_search_threshold = float(os.getenv('VECTOR_SEARCH_THRESHOLD', '0.3'))  # Adjusted for sentence transformers
        
        # R Subprocess Configuration
        self.r_timeout = int(os.getenv('R_TIMEOUT', '120'))  # 2 minutes
        self.r_memory_limit = os.getenv('R_MEMORY_LIMIT', '2G')
        
        # Container-specific settings
        self.is_container = os.getenv('CENSUS_MCP_CONTAINER', 'false').lower() == 'true'
        self.container_data_mount = os.getenv('CONTAINER_DATA_MOUNT', '/app/data')
        
        # Load from config file if provided
        if self.config_file and Path(self.config_file).exists():
            self._load_config_file()
        
        # Load default config if it exists
        default_config = self.config_dir / "mcp_config.json"
        if default_config.exists():
            self._load_config_file(str(default_config))
    
    def _get_embedding_dimension(self) -> int:
        """Get embedding dimension based on model."""
        # Map common sentence transformer models to their dimensions
        model_dimensions = {
            'all-mpnet-base-v2': 768,
            'all-MiniLM-L6-v2': 384,
            'all-MiniLM-L12-v2': 384,
            'all-distilroberta-v1': 768,
            'paraphrase-mpnet-base-v2': 768,
            'sentence-t5-base': 768,
            'sentence-t5-large': 768,
        }
        
        # Check if it's an OpenAI model (legacy)
        if 'text-embedding' in self.embedding_model:
            logger.warning(f"OpenAI model '{self.embedding_model}' detected, switching to sentence transformers")
            self.embedding_model = 'all-mpnet-base-v2'
            return 768
        
        # Get dimension or default
        return int(os.getenv('EMBEDDING_DIMENSION',
                           model_dimensions.get(self.embedding_model, 768)))
    
    def _load_config_file(self, config_path: Optional[str] = None):
        """Load configuration from JSON file."""
        try:
            config_path = config_path or self.config_file
            with open(config_path, 'r') as f:
                file_config = json.load(f)
            
            # Update configuration with file values (environment takes precedence)
            for key, value in file_config.items():
                if not hasattr(self, key) or getattr(self, key) is None:
                    setattr(self, key, value)
            
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.warning(f"Could not load config file {config_path}: {e}")
    
    def _validate_config(self):
        """Validate configuration and create necessary directories."""
        
        # Create data directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.r_docs_corpus_path.mkdir(parents=True, exist_ok=True)
        self.vector_db_path.mkdir(parents=True, exist_ok=True)
        
        # Validate R configuration
        if not self._check_r_availability():
            logger.warning("R is not available. Data retrieval will not work.")
        
        # Validate embedding model
        if not self._validate_embedding_model():
            logger.warning(f"Embedding model {self.embedding_model} may not be available.")
        
        # Log configuration status
        self._log_config_status()
    
    def _find_r_executable(self) -> str:
        """Find R executable in common locations."""
        possible_paths = [
            os.getenv('R_EXECUTABLE'),  # User override
            '/opt/anaconda3/envs/census-mcp/bin/Rscript',  # Current conda setup - CHECK FIRST
            '/opt/conda/bin/Rscript',  # Docker conda
            '/usr/bin/Rscript',  # System R (Linux)
            '/usr/local/bin/Rscript',  # Homebrew (macOS)
            '/opt/homebrew/bin/Rscript',  # Apple Silicon Homebrew
            # Container paths
            '/app/conda/bin/Rscript',
            '/usr/local/lib/R/bin/Rscript',
            'Rscript',  # In PATH - CHECK LAST (may not work in Claude Desktop)
        ]
        
        for path in possible_paths:
            if path and self._test_r_executable(path):
                logger.info(f"Found R executable: {path}")
                return path
        
        logger.warning("R executable not found in common locations, using 'Rscript'")
        return 'Rscript'  # Fallback
    
    def _test_r_executable(self, path: str) -> bool:
        """Test if R executable works at given path."""
        try:
            import subprocess
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _check_r_availability(self) -> bool:
        """Check if R is available and configured correctly."""
        return self._test_r_executable(self.r_executable)
    
    def _validate_embedding_model(self) -> bool:
        """Validate that the embedding model is available."""
        try:
            # For sentence transformers models
            if self.embedding_model in ['all-mpnet-base-v2', 'all-MiniLM-L6-v2', 'all-MiniLM-L12-v2']:
                try:
                    import sentence_transformers
                    return True
                except ImportError:
                    logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")
                    return False
            
            # For other models, assume valid
            return True
            
        except Exception:
            return False
    
    def _log_config_status(self):
        """Log current configuration status."""
        logger.info("Census MCP Server Configuration:")
        logger.info(f"  Base directory: {self.base_dir}")
        logger.info(f"  Data directory: {self.data_dir}")
        logger.info(f"  Vector DB path: {self.vector_db_path}")
        logger.info(f"  Container mode: {self.is_container}")
        logger.info(f"  R executable: {self.r_executable}")
        logger.info(f"  Vector DB type: {self.vector_db_type}")
        logger.info(f"  Embedding model: {self.embedding_model} (local, no API key)")
        logger.info(f"  Embedding dimensions: {self.embedding_dimension}")
        logger.info(f"  Log level: {self.log_level}")
        
        # Check for API keys (without logging them)
        api_keys_status = {
            "Census API": "✓" if self.census_api_key else "⚠ (optional)",
            "Claude API": "✓" if self.claude_api_key else "✗",
            "OpenAI API": "✓" if self.openai_api_key else "⚠ (not needed for sentence transformers)"
        }
        
        for api, status in api_keys_status.items():
            logger.info(f"  {api} key: {status}")
    
    def get_r_script_content(self) -> str:
        """Get the R script template for data retrieval."""
        return '''
# Census Data Retrieval Script
# Called by Python MCP server to fetch ACS data via tidycensus

library(tidycensus)
library(dplyr)
library(jsonlite)

# Parse command line arguments
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
    stop("Usage: Rscript census_data_retrieval.R <location> <variables> <year> <survey>")
}

location_json <- args[1]
variables_json <- args[2]
year <- as.numeric(args[3])
survey <- args[4]

# Parse JSON inputs
location_data <- fromJSON(location_json)
variables_list <- fromJSON(variables_json)

# Set Census API key if available
census_api_key <- Sys.getenv("CENSUS_API_KEY")
if (nchar(census_api_key) > 0) {
    census_api_key(census_api_key)
}

# Main data retrieval function
get_census_data <- function(location_data, variables_list, year, survey) {
    tryCatch({
        # Determine geography type and codes
        geography <- location_data$geography
        state <- location_data$state
        county <- location_data$county
        place <- location_data$place
        
        # Call get_acs based on geography
        if (geography == "state") {
            data <- get_acs(
                geography = "state",
                variables = variables_list,
                year = year,
                survey = survey,
                state = state
            )
        } else if (geography == "county") {
            data <- get_acs(
                geography = "county",
                variables = variables_list,
                year = year,
                survey = survey,
                state = state,
                county = county
            )
        } else if (geography == "place") {
            # Get all places in state, then filter for specific place
            data <- get_acs(
                geography = "place",
                variables = variables_list,
                year = year,
                survey = survey,
                state = state
            )
            
            # Filter for the specific place if specified
            if (!is.null(place) && nchar(place) > 0) {
                # Create search patterns for place matching
                place_patterns <- c(
                    paste0("^", place, "$"),  # Exact match
                    paste0("^", place, ","),  # Place followed by comma
                    paste0(place, " city,"), # City suffix
                    paste0(place, " town,"), # Town suffix
                    paste0(place, " village,") # Village suffix
                )
                
                # Try each pattern until we find a match
                filtered_data <- NULL
                for (pattern in place_patterns) {
                    filtered_data <- data[grepl(pattern, data$NAME, ignore.case = TRUE), ]
                    if (nrow(filtered_data) > 0) {
                        break
                    }
                }
                
                # If no match found, try partial matching
                if (is.null(filtered_data) || nrow(filtered_data) == 0) {
                    # Extract base place name for partial matching
                    base_place <- gsub(" (city|town|village)$", "", place, ignore.case = TRUE)
                    filtered_data <- data[grepl(base_place, data$NAME, ignore.case = TRUE), ]
                }
                
                # Use filtered data if found, otherwise return error
                if (!is.null(filtered_data) && nrow(filtered_data) > 0) {
                    data <- filtered_data
                } else {
                    stop(paste("No data found for place:", place, "in state:", state))
                }
            }
        } else if (geography == "us") {
            data <- get_acs(
                geography = "us",
                variables = variables_list,
                year = year,
                survey = survey
            )
        } else {
            stop(paste("Unsupported geography:", geography))
        }
        
        # Format output
        result <- list(
            data = data,
            source = paste("US Census Bureau American Community Survey", survey, "Estimates"),
            year = year,
            survey = toupper(survey),
            geography = geography,
            success = TRUE
        )
        
        # Convert to JSON and print
        cat(toJSON(result, auto_unbox = TRUE, pretty = TRUE))
        
    }, error = function(e) {
        error_result <- list(
            error = as.character(e),
            success = FALSE
        )
        cat(toJSON(error_result, auto_unbox = TRUE))
    })
}

# Execute main function
get_census_data(location_data, variables_list, year, survey)
'''
    
    def save_r_script(self) -> bool:
        """Save the R script to the scripts directory."""
        try:
            self.scripts_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.r_script_path, 'w') as f:
                f.write(self.get_r_script_content())
            
            logger.info(f"R script saved to {self.r_script_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save R script: {e}")
            return False
    
    def get_env_template(self) -> str:
        """Get the .env template for user configuration."""
        return '''# Census MCP Server Configuration
# Copy this file to .env and update with your settings

# Optional: Census API Key (recommended for higher rate limits)
# Get from: https://api.census.gov/data/key_signup.html
CENSUS_API_KEY=

# Required: Choose your LLM provider and add API key
DEFAULT_LLM=claude
ANTHROPIC_API_KEY=

# OPTIONAL: OpenAI API Key (not needed with sentence transformers)
# OPENAI_API_KEY=

# Optional: Advanced Configuration
LOG_LEVEL=INFO
VECTOR_DB_TYPE=chromadb
EMBEDDING_MODEL=all-mpnet-base-v2
R_EXECUTABLE=Rscript
R_TIMEOUT=120
MAX_CONCURRENT_REQUESTS=10

# Container Configuration (set automatically in Docker)
CENSUS_MCP_CONTAINER=false
'''
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding sensitive data)."""
        config_dict = {}
        for attr_name in dir(self):
            if not attr_name.startswith('_') and not callable(getattr(self, attr_name)):
                value = getattr(self, attr_name)
                # Exclude API keys from dict representation
                if 'api_key' not in attr_name.lower():
                    config_dict[attr_name] = str(value) if isinstance(value, Path) else value
        return config_dict

# Global configuration instance
_config_instance = None

def get_config() -> Config:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance

def reload_config(config_file: Optional[str] = None) -> Config:
    """Reload the global configuration."""
    global _config_instance
    _config_instance = Config(config_file)
    return _config_instance
