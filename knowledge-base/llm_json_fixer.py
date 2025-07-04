#!/usr/bin/env python3
"""
LLM JSON Fixer Module
A battle-tested JSON repair utility for handling malformed LLM outputs
"""

import json
import re
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class LLMJSONFixer:
    """Robust JSON fixer for LLM outputs"""
    
    @staticmethod
    def fix_json(json_str: str, aggressive: bool = True) -> str:
        """
        Fix common JSON issues in LLM outputs
        
        Args:
            json_str: Potentially malformed JSON string
            aggressive: If True, applies more aggressive fixes
            
        Returns:
            Fixed JSON string
        """
        if not json_str.strip():
            return "{}"
        
        # Apply fixes in order of least to most aggressive
        fixed = json_str
        
        # Level 1: Basic fixes
        fixed = LLMJSONFixer._extract_json_object(fixed)
        fixed = LLMJSONFixer._fix_basic_issues(fixed)
        
        # Level 2: Structural fixes
        fixed = LLMJSONFixer._fix_missing_commas(fixed)
        fixed = LLMJSONFixer._fix_quotes_and_escapes(fixed)
        
        if aggressive:
            # Level 3: Aggressive fixes
            fixed = LLMJSONFixer._fix_newlines_in_strings(fixed)
            fixed = LLMJSONFixer._fix_unterminated_strings(fixed)
            fixed = LLMJSONFixer._ensure_proper_closure(fixed)
        
        return fixed
    
    @staticmethod
    def parse_with_fallbacks(content: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Try multiple strategies to parse JSON
        
        Returns:
            Tuple of (parsed_dict, error_message)
        """
        # Strategy 1: Direct parse
        try:
            return json.loads(content), None
        except json.JSONDecodeError as e:
            error1 = f"Direct parse failed: {e}"
        
        # Strategy 2: Extract and parse
        try:
            extracted = LLMJSONFixer._extract_json_object(content)
            return json.loads(extracted), None
        except json.JSONDecodeError as e:
            error2 = f"Extracted parse failed: {e}"
        
        # Strategy 3: Fix and parse
        try:
            fixed = LLMJSONFixer.fix_json(content, aggressive=False)
            return json.loads(fixed), None
        except json.JSONDecodeError as e:
            error3 = f"Fixed parse failed: {e}"
        
        # Strategy 4: Aggressive fix and parse
        try:
            fixed = LLMJSONFixer.fix_json(content, aggressive=True)
            return json.loads(fixed), None
        except json.JSONDecodeError as e:
            error4 = f"Aggressive fix failed: {e}"
        
        # Strategy 5: Last resort - try to salvage what we can
        try:
            # Try to extract key-value pairs manually
            salvaged = LLMJSONFixer._salvage_json(content)
            if salvaged:
                return salvaged, "Warning: JSON was salvaged, may be incomplete"
        except Exception as e:
            error5 = f"Salvage failed: {e}"
        
        # All strategies failed
        all_errors = "\n".join([error1, error2, error3, error4, error5])
        return None, all_errors
    
    @staticmethod
    def _extract_json_object(text: str) -> str:
        """Extract JSON object from surrounding text"""
        # Try to find JSON in markdown code blocks
        code_block_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1).strip()
        
        # Try to find raw JSON object
        json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        return text.strip()
    
    @staticmethod
    def _fix_basic_issues(json_str: str) -> str:
        """Fix basic JSON formatting issues"""
        # Remove trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Remove comments (not valid in JSON)
        json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # Fix single quotes (JSON requires double quotes)
        # This is tricky - only fix quotes that are clearly field/value delimiters
        json_str = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', json_str)  # Field names
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)    # String values
        
        return json_str
    
    @staticmethod
    def _fix_missing_commas(json_str: str) -> str:
        """Add missing commas between elements"""
        # Add commas between consecutive strings
        json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
        
        # Add commas between array elements
        json_str = re.sub(r'}\s*\n\s*{', '},\n{', json_str)
        json_str = re.sub(r']\s*\n\s*\[', '],\n[', json_str)
        
        # Add commas after values before new fields
        # String values
        json_str = re.sub(r'(":\s*"[^"]*")\s*\n\s*"', r'\1,\n"', json_str)
        # Number values  
        json_str = re.sub(r'(":\s*\d+(?:\.\d+)?)\s*\n\s*"', r'\1,\n"', json_str)
        # Boolean values
        json_str = re.sub(r'(":\s*(?:true|false))\s*\n\s*"', r'\1,\n"', json_str)
        # Null values
        json_str = re.sub(r'(":\s*null)\s*\n\s*"', r'\1,\n"', json_str)
        # Array values
        json_str = re.sub(r'(":\s*\[[^\]]*\])\s*\n\s*"', r'\1,\n"', json_str)
        # Object values (careful with nested objects)
        json_str = re.sub(r'(":\s*\{[^}]*\})\s*\n\s*"', r'\1,\n"', json_str)
        
        return json_str
    
    @staticmethod
    def _fix_quotes_and_escapes(json_str: str) -> str:
        """Fix quote and escape issues"""
        # Fix improperly escaped quotes inside strings
        # This is complex - we need to identify string boundaries first
        
        # Fix obvious cases of unescaped quotes
        # Look for patterns like: "text "quoted" text"
        def fix_internal_quotes(match):
            content = match.group(1)
            # Escape any unescaped quotes inside
            fixed = re.sub(r'(?<!\\)"', r'\"', content)
            return f'"{fixed}"'
        
        # Apply to string values (after colons)
        json_str = re.sub(r':\s*"([^"]*(?:"[^"]*)*)"', lambda m: ': ' + fix_internal_quotes(m), json_str)
        
        return json_str
    
    @staticmethod
    def _fix_newlines_in_strings(json_str: str) -> str:
        """Replace newlines inside strings with spaces"""
        def fix_newlines(match):
            content = match.group(1)
            # Replace newlines with spaces
            fixed = content.replace('\n', ' ').replace('\r', ' ')
            # Collapse multiple spaces
            fixed = re.sub(r'\s+', ' ', fixed)
            return f'"{fixed}"'
        
        # Find strings and fix newlines within them
        # This is tricky because we need to handle escaped quotes
        parts = []
        in_string = False
        current_string_start = 0
        i = 0
        
        while i < len(json_str):
            if json_str[i] == '"' and (i == 0 or json_str[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    current_string_start = i
                else:
                    # End of string
                    string_content = json_str[current_string_start:i+1]
                    fixed_string = fix_newlines(re.match(r'"(.*)"', string_content, re.DOTALL))
                    parts.append(json_str[len(''.join(parts)):current_string_start])
                    parts.append(fixed_string)
                    in_string = False
            i += 1
        
        if not in_string:
            parts.append(json_str[len(''.join(parts)):])
            return ''.join(parts)
        else:
            # Unterminated string, return original
            return json_str
    
    @staticmethod
    def _fix_unterminated_strings(json_str: str) -> str:
        """Fix unterminated strings"""
        lines = json_str.split('\n')
        fixed_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            # Count unescaped quotes
            unescaped_quotes = len(re.findall(r'(?<!\\)"', line))
            
            if unescaped_quotes % 2 == 1:
                # Odd number of quotes - likely unterminated
                if i + 1 < len(lines):
                    # Look ahead to find the terminating quote
                    combined = line
                    j = i + 1
                    while j < len(lines):
                        combined += ' ' + lines[j].strip()
                        total_quotes = len(re.findall(r'(?<!\\)"', combined))
                        if total_quotes % 2 == 0:
                            # Found the closing quote
                            fixed_lines.append(combined)
                            i = j + 1
                            break
                        j += 1
                    else:
                        # Couldn't find closing quote, add one
                        fixed_lines.append(line + '"')
                        i += 1
                else:
                    # Last line with unterminated string
                    fixed_lines.append(line + '"')
                    i += 1
            else:
                fixed_lines.append(line)
                i += 1
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _ensure_proper_closure(json_str: str) -> str:
        """Ensure all brackets and braces are properly closed"""
        # Count opening and closing brackets/braces
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        
        # Add missing closures
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
        if open_brackets > close_brackets:
            json_str += ']' * (open_brackets - close_brackets)
        
        return json_str
    
    @staticmethod
    def _salvage_json(text: str) -> Optional[Dict[str, Any]]:
        """Last resort - try to salvage what we can from the text"""
        result = {}
        
        # Try to find key-value pairs
        # Look for patterns like "key": "value" or "key": value
        patterns = [
            r'"([^"]+)"\s*:\s*"([^"]*)"',  # String values
            r'"([^"]+)"\s*:\s*(\d+(?:\.\d+)?)',  # Number values
            r'"([^"]+)"\s*:\s*(\btrue\b|\bfalse\b)',  # Boolean values
            r'"([^"]+)"\s*:\s*(\bnull\b)',  # Null values
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for key, value in matches:
                if key not in result:  # Don't overwrite existing keys
                    # Convert value to appropriate type
                    if value == 'true':
                        result[key] = True
                    elif value == 'false':
                        result[key] = False
                    elif value == 'null':
                        result[key] = None
                    elif re.match(r'^\d+$', value):
                        result[key] = int(value)
                    elif re.match(r'^\d+\.\d+$', value):
                        result[key] = float(value)
                    else:
                        result[key] = value
        
        return result if result else None

# Convenience function for quick fixes
def fix_llm_json(content: str) -> Dict[str, Any]:
    """
    Convenience function to fix and parse LLM JSON
    
    Args:
        content: Potentially malformed JSON string from LLM
        
    Returns:
        Parsed dictionary
        
    Raises:
        ValueError: If JSON cannot be parsed after all fix attempts
    """
    result, error = LLMJSONFixer.parse_with_fallbacks(content)
    if result is None:
        raise ValueError(f"Could not parse JSON after all attempts:\n{error}")
    return result
