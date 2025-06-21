#!/usr/bin/env python3
import sys
import re

def compact_arrays_in_place(content):
    """Compact multi-line arrays to single lines while preserving comments and trailing commas"""

    # Pattern to match arrays that span multiple lines
    # This will match arrays containing only strings
    def compact_string_array(match):
        """Convert a multi-line string array to single line"""
        full_match = match.group(0)
        indent = match.group(1)

        # Extract all the string values
        strings = re.findall(r'"[^"]*"', full_match)

        # Check if there's a trailing comma after the closing bracket
        trailing_comma = ',' if full_match.rstrip().endswith(',') else ''

        # Reconstruct as single line
        return f'{indent}[{", ".join(strings)}]{trailing_comma}'

    # Pattern for simple string arrays like ["**/*.js", "**/*.jsx", ...]
    pattern1 = r'^(\s*)\[\s*\n(?:\s*"[^"]*",?\s*\n)+\s*\],?'
    content = re.sub(pattern1, compact_string_array, content, flags=re.MULTILINE)

    # Pattern for "before" and "after" arrays in vim keybindings
    def compact_keybinding_array(match):
        """Compact before/after/commands arrays in keybindings"""
        indent = match.group(1)
        key = match.group(2)

        # Extract all string values between the brackets
        array_content = match.group(3)
        strings = re.findall(r'"[^"]*"', array_content)

        # Reconstruct as single line
        return f'{indent}"{key}": [{", ".join(strings)}]'

    # Match "before": [ ... ], "after": [ ... ], "commands": [ ... ]
    pattern2 = r'^(\s*)"(before|after|commands)":\s*\[\s*\n((?:\s*"[^"]*",?\s*\n)+)\s*\]'
    content = re.sub(pattern2, compact_keybinding_array, content, flags=re.MULTILINE)

    # Now compact the keybinding objects themselves onto single lines
    def compact_keybinding_object(match):
        """Put entire keybinding object on one line"""
        indent = match.group(1)
        obj_content = match.group(2)
        trailing_comma = match.group(3)

        # Remove newlines and excessive whitespace
        obj_content = re.sub(r'\s*\n\s*', ' ', obj_content)
        obj_content = re.sub(r'\s+', ' ', obj_content)
        obj_content = obj_content.strip()

        return f'{indent}{{{obj_content}}}{trailing_comma}'

    # Match keybinding objects that have been partially compacted
    # This matches objects containing "before", "after", or "commands"
    pattern3 = r'^(\s*)\{\s*\n((?:\s*"(?:before|after|commands|when)":[^\n]+\n?)+)\s*\}(,?)'
    content = re.sub(pattern3, compact_keybinding_object, content, flags=re.MULTILINE)

    return content

# Get file path from command line or use default
file_path = sys.argv[1] if len(sys.argv) > 1 else 'vscode-settings.json'

# Read the file
with open(file_path, 'r') as f:
    content = f.read()

# Compact arrays while preserving structure
result = compact_arrays_in_place(content)

# Write back
with open(file_path, 'w') as f:
    f.write(result)

print(f"Formatted {file_path} with compact arrays (preserved comments and trailing commas)")
