#!/usr/bin/env python3
"""
Census MCP Server - Containerized Census expertise via MCP protocol

Provides natural language access to US Census data through:
- Vector DB/RAG for R documentation and Census knowledge
- R tidycensus integration for data retrieval
- Statistical validation and geographic resolution

Architecture components:
- MCP Server (this file) - Protocol interface
- Knowledge Base - Vector DB with R docs corpus
- Data Retrieval Engine - R subprocess execution
- LLM Adapters - Claude integration (extensible)
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Local imports (Sprint 1 - will create these)
from knowledge.vector_db import KnowledgeBase
from data_retrieval.r_engine import RDataRetrieval
from utils.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CensusMCPServer:
    """
    Main MCP server class that orchestrates Census data requests.
    
    Handles:
    - MCP protocol communication
    - Query parsing and context enrichment via RAG
    - R subprocess coordination for data retrieval
    - Response formatting and statistical validation
    """
    
    def __init__(self):
        """Initialize server components."""
        self.config = Config()
        
        # Initialize knowledge base (Vector DB/RAG)
        logger.info("Initializing knowledge base...")
        self.knowledge_base = KnowledgeBase(
            corpus_path=self.config.r_docs_corpus_path,
            vector_db_path=self.config.vector_db_path
        )
        
        # Initialize R data retrieval engine
        logger.info("Initializing R data retrieval engine...")
        self.r_engine = RDataRetrieval(
            r_script_path=self.config.r_script_path
        )
        
        # Create MCP server instance
        self.server = Server("census-mcp")
        
        # Register tools
        self._register_tools()
        
        logger.info("Census MCP Server initialized successfully")
    
    def _register_tools(self):
        """Register MCP tools that will be available to Claude Desktop."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """Return list of available Census tools."""
            return [
                Tool(
                    name="get_demographic_data",
                    description="Get demographic data for a specific location using US Census ACS",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "Location name (e.g., 'Baltimore, MD', 'California', 'Harris County, TX')"
                            },
                            "variables": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of demographic variables (e.g., ['population', 'median_income', 'poverty_rate'])"
                            },
                            "year": {
                                "type": "integer",
                                "description": "ACS year (default: most recent available)",
                                "default": 2023
                            },
                            "survey": {
                                "type": "string",
                                "description": "ACS survey type: 'acs5' (5-year, default, more reliable) or 'acs1' (1-year, large areas only)",
                                "default": "acs5"
                            }
                        },
                        "required": ["location", "variables"]
                    }
                ),
                Tool(
                    name="compare_locations",
                    description="Compare demographic statistics between multiple locations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "locations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of location names to compare"
                            },
                            "variables": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of variables to compare across locations"
                            },
                            "year": {
                                "type": "integer",
                                "description": "ACS year for comparison",
                                "default": 2023
                            },
                            "survey": {
                                "type": "string",
                                "description": "ACS survey type: 'acs5' (5-year, default) or 'acs1' (1-year)",
                                "default": "acs5"
                            }
                        },
                        "required": ["locations", "variables"]
                    }
                ),
                Tool(
                    name="search_census_knowledge",
                    description="Search Census documentation and methodology for specific concepts",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Question about Census methodology, variables, or concepts"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context for the search",
                                "default": ""
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool execution requests."""
            try:
                if name == "get_demographic_data":
                    return await self._get_demographic_data(arguments)
                elif name == "compare_locations":
                    return await self._compare_locations(arguments)
                elif name == "search_census_knowledge":
                    return await self._search_census_knowledge(arguments)
                else:
                    return [TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )]
            except Exception as e:
                logger.error(f"Error executing tool {name}: {str(e)}")
                return [TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )]
    
    async def _get_demographic_data(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Get demographic data for a specific location.
        
        Uses RAG to enhance variable understanding and R tidycensus for data retrieval.
        """
        location = arguments["location"]
        variables = arguments["variables"]
        year = arguments.get("year", 2023)
        survey = arguments.get("survey", "acs5")
        survey = arguments.get("survey", "acs5")
        
        logger.info(f"Getting demographic data for {location}, variables: {variables}")
        
        # Step 1: Use RAG to enhance variable understanding
        variable_context = await self.knowledge_base.get_variable_context(variables)
        
        # Step 2: Parse and validate location
        location_info = await self.knowledge_base.parse_location(location)
        
        # Step 3: Call R tidycensus to get data
        census_data = await self.r_engine.get_acs_data(
            location=location,
            variables=variables,
            year=year,
            survey=survey,
            context=variable_context
        )
        
        # Step 4: Format response with statistical context
        response = self._format_demographic_response(
            data=census_data,
            location=location,
            variables=variables,
            context=variable_context
        )
        
        return [TextContent(type="text", text=response)]
    
    async def _compare_locations(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Compare demographic statistics between multiple locations."""
        locations = arguments["locations"]
        variables = arguments["variables"]
        year = arguments.get("year", 2023)
        
        logger.info(f"Comparing locations: {locations}, variables: {variables}")
        
        # Get context for variables
        variable_context = await self.knowledge_base.get_variable_context(variables)
        
        # Get data for each location
        comparison_data = []
        for location in locations:
            data = await self.r_engine.get_acs_data(
                location=location,
                variables=variables,
                year=year,
                survey=survey,
                context=variable_context
            )
            comparison_data.append({"location": location, "data": data})
        
        # Format comparison response
        response = self._format_comparison_response(
            comparison_data=comparison_data,
            variables=variables,
            context=variable_context
        )
        
        return [TextContent(type="text", text=response)]
    
    async def _search_census_knowledge(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Search Census documentation and methodology."""
        query = arguments["query"]
        context = arguments.get("context", "")
        
        logger.info(f"Searching knowledge base for: {query}")
        
        # Use RAG to search documentation
        results = await self.knowledge_base.search_documentation(
            query=query,
            context=context
        )
        
        response = self._format_knowledge_response(query, results)
        
        return [TextContent(type="text", text=response)]
    
    def _format_demographic_response(self, data: Dict, location: str, 
                                   variables: List[str], context: Dict) -> str:
        """Format demographic data response with statistical context."""
        response_parts = [f"# Demographic Data for {location}\n"]
        
        if "error" in data:
            response_parts.append(f"⚠️ Error retrieving data: {data['error']}")
            return "\n".join(response_parts)
        
        # Add data with context
        for var in variables:
            if var in data:
                var_data = data[var]
                var_context = context.get(var, {})
                
                response_parts.append(f"## {var_context.get('label', var.title())}")
                response_parts.append(f"**Value**: {var_data.get('estimate', 'N/A')}")
                
                # Add margin of error if available
                if 'moe' in var_data:
                    response_parts.append(f"**Margin of Error**: ±{var_data['moe']}")
                
                # Add context from knowledge base
                if 'definition' in var_context:
                    response_parts.append(f"**Definition**: {var_context['definition']}")
                
                response_parts.append("")  # Add spacing
        
        # Add data source and methodology notes
        response_parts.extend([
            "---",
            f"**Source**: {data.get('source', 'US Census Bureau American Community Survey')}",
            f"**Survey Type**: {data.get('survey', 'ACS 5-Year')} Estimates",
            f"**Year**: {data.get('year', 'Unknown')}",
            "**Note**: ACS 5-year estimates are more reliable but less current than 1-year estimates. Estimates include margins of error."
        ])
        
        return "\n".join(response_parts)
    
    def _format_comparison_response(self, comparison_data: List[Dict], 
                                  variables: List[str], context: Dict) -> str:
        """Format location comparison response."""
        response_parts = ["# Location Comparison\n"]
        
        # Create comparison table for each variable
        for var in variables:
            var_context = context.get(var, {})
            response_parts.append(f"## {var_context.get('label', var.title())}")
            response_parts.append("| Location | Value | Margin of Error |")
            response_parts.append("|----------|-------|-----------------|")
            
            for loc_data in comparison_data:
                location = loc_data["location"]
                data = loc_data["data"]
                
                if var in data and "error" not in data:
                    estimate = data[var].get("estimate", "N/A")
                    moe = data[var].get("moe", "N/A")
                    response_parts.append(f"| {location} | {estimate} | ±{moe} |")
                else:
                    response_parts.append(f"| {location} | Error | - |")
            
            response_parts.append("")  # Add spacing
        
        return "\n".join(response_parts)
    
    def _format_knowledge_response(self, query: str, results: List[Dict]) -> str:
        """Format knowledge search results."""
        response_parts = [f"# Census Knowledge: {query}\n"]
        
        if not results:
            response_parts.append("No relevant documentation found for this query.")
            return "\n".join(response_parts)
        
        for i, result in enumerate(results[:3], 1):  # Top 3 results
            response_parts.extend([
                f"## Result {i}: {result.get('title', 'Untitled')}",
                result.get('content', ''),
                f"**Source**: {result.get('source', 'Unknown')}",
                f"**Relevance Score**: {result.get('score', 0):.3f}",
                ""
            ])
        
        return "\n".join(response_parts)

async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Census MCP Server...")
    
    try:
        # Create server instance
        census_server = CensusMCPServer()
        
        # Run server with stdio transport (for Claude Desktop)
        async with stdio_server() as (read_stream, write_stream):
            await census_server.server.run(
                read_stream,
                write_stream,
                census_server.server.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Entry point for the MCP server
    asyncio.run(main())
