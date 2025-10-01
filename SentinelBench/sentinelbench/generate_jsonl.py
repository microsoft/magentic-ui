#!/usr/bin/env python3
"""
Generate sentinelbench_tasks.jsonl from the current SentinelBench routes.
Parses routes.ts directly and applies the same logic as the browser's downloadChallengesJSONL function.
"""

import json
import os
import re
from typing import List, Dict, Any, Optional

def parse_routes_ts(routes_file_path: str) -> List[Dict[str, Any]]:
    """
    Parse the routes.ts file and extract route objects, applying the same filtering
    logic as the browser's downloadChallengesJSONL function.
    """
    with open(routes_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Get the base directory for resolving imports
    base_dir = os.path.dirname(os.path.dirname(routes_file_path))  # Go up to sentinelbench/src level
    
    # Extract imported constants
    constants = resolve_imported_constants(content, base_dir)
    
    # Load task passwords from passwords.ts
    task_passwords = load_task_passwords(base_dir)
    
    # Find the routes array definition
    routes_match = re.search(r'export const routes.*?=\s*\[(.*?)\];', content, re.DOTALL)
    if not routes_match:
        raise ValueError("Could not find routes array in routes.ts")
    
    routes_content = routes_match.group(1)
    
    # Split into individual route objects
    routes = []
    current_route = ""
    brace_count = 0
    in_route = False
    
    for char in routes_content:
        if char == '{':
            if not in_route:
                in_route = True
                current_route = "{"
            else:
                current_route += char
            brace_count += 1
        elif char == '}':
            current_route += char
            brace_count -= 1
            if brace_count == 0 and in_route:
                # Parse this route object
                route = parse_route_object(current_route, content, constants, task_passwords)
                if route:
                    routes.append(route)
                current_route = ""
                in_route = False
        elif in_route:
            current_route += char
    
    return routes

def parse_route_object(route_str: str, full_content: str, constants: Dict[str, str], task_passwords: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Parse a single route object string into a dictionary."""
    route = {}
    
    # Extract basic fields using regex patterns
    patterns = {
        'path': r'path:\s*(?:([A-Za-z_][A-Za-z0-9_]*)|"([^"]*)")',  # Matches both constants and literal strings
        'title': r'title:\s*"([^"]*)"',
        'description': r'description:\s*"([^"]*)"',
        'url': r'url:\s*"([^"]*)"',
        'icon': r'icon:\s*"([^"]*)"',
        'password': r'password:\s*getTaskPassword\(([A-Za-z_][A-Za-z0-9_]*)\)',  # Matches getTaskPassword(TASK_ID_X)
        'difficulty': r'difficulty:\s*"([^"]*)"',
        'base_task': r'base_task:\s*"([^"]*)"',
        'duration': r'duration:\s*"([^"]*)"',
        'criteria': r'criteria:\s*"([^"]*)"',
        'activity': r'activity:\s*"([^"]*)"',
        'noise': r'noise:\s*"([^"]*)"',
        'realism': r'realism:\s*"([^"]*)"',
        'relative_vs_absolute': r'relative_vs_absolute:\s*"([^"]*)"',
        'failure_tolerance': r'failure_tolerance:\s*"([^"]*)"'
    }
    
    # Extract tags array
    tags_match = re.search(r'tags:\s*\[(.*?)\]', route_str, re.DOTALL)
    if tags_match:
        tags_str = tags_match.group(1)
        tags = [tag.strip().strip('"') for tag in tags_str.split(',') if tag.strip()]
        route['tags'] = tags
    
    # Extract other fields
    for field, pattern in patterns.items():
        match = re.search(pattern, route_str)
        if match:
            if field == 'path':
                # Handle both constants and literal strings for path
                const_value = match.group(1)  # Constant name
                literal_value = match.group(2)  # Literal string
                
                if const_value:  # It's a constant
                    resolved_value = constants.get(const_value)
                    if not resolved_value:
                        resolved_value = resolve_constant(const_value, full_content)
                    route[field] = resolved_value if resolved_value else const_value
                elif literal_value:  # It's a literal string
                    route[field] = literal_value
            elif field == 'password':
                # Handle getTaskPassword(TASK_ID_X) calls
                task_id_const = match.group(1)
                # First resolve the TASK_ID constant to get the actual task id
                task_id = constants.get(task_id_const)
                if not task_id:
                    task_id = resolve_constant(task_id_const, full_content)
                
                if task_id and task_id in task_passwords:
                    # Use the raw password directly from TASK_PASSWORDS
                    route[field] = task_passwords[task_id]
                else:
                    print(f"Warning: Could not resolve password for {task_id_const} -> {task_id}")
                    route[field] = None
            else:
                route[field] = match.group(1)
    
    # Extract boolean fields
    bool_patterns = {
        'adversarial_attacks': r'adversarial_attacks:\s*(true|false)'
    }
    
    for field, pattern in bool_patterns.items():
        match = re.search(pattern, route_str)
        if match:
            route[field] = match.group(1) == 'true'
    
    # Check if route has component (not null)
    component_match = re.search(r'component:\s*([A-Za-z0-9_]+)', route_str)
    if component_match and component_match.group(1) != 'null':
        route['has_component'] = True
    else:
        route['has_component'] = False
    
    return route

def resolve_imported_constants(content: str, base_path: str) -> Dict[str, str]:
    """
    Extract all imported constants from the routes.ts file by reading the imported files.
    """
    constants = {}
    
    # Find all import statements (including multi-line)
    import_pattern = r'import\s+([^,]+),?\s*{([^}]*)}\s*from\s*["\']([^"\']*)["\']'
    imports = re.findall(import_pattern, content, re.MULTILINE | re.DOTALL)
    
    for component_name, import_items, import_path in imports:
        # Skip non-page imports
        if not import_path.startswith('../pages/'):
            continue
            
        # Construct the full file path
        file_path = os.path.join(base_path, import_path.replace('../pages/', 'pages/') + '.tsx')
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                # Extract the specific constants mentioned in the import
                items = [item.strip() for item in import_items.split(',') if item.strip()]
                for item in items:
                    if item.startswith('TASK_ID_') or item.startswith('PASSWORD_'):
                        value = resolve_constant(item, file_content)
                        if value:
                            constants[item] = value
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")
    
    return constants

def load_task_passwords(base_path: str) -> Dict[str, str]:
    """
    Load the TASK_PASSWORDS mapping from passwords.ts
    """
    passwords_file = os.path.join(base_path, 'config', 'passwords.ts')
    if not os.path.exists(passwords_file):
        print(f"Warning: Could not find passwords.ts at {passwords_file}")
        return {}
    
    try:
        with open(passwords_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract the TASK_PASSWORDS object
        task_passwords_match = re.search(r'export const TASK_PASSWORDS\s*=\s*\{(.*?)\}\s*as const;', content, re.DOTALL)
        if not task_passwords_match:
            print("Warning: Could not find TASK_PASSWORDS in passwords.ts")
            return {}
        
        passwords_content = task_passwords_match.group(1)
        passwords = {}
        
        # Parse each line in the TASK_PASSWORDS object
        for line in passwords_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            # Match pattern: 'task-id': 'PASSWORD',
            match = re.match(r"'([^']+)':\s*'([^']+)',?", line)
            if match:
                task_id, password = match.groups()
                passwords[task_id] = password
        
        return passwords
    except Exception as e:
        print(f"Warning: Could not read {passwords_file}: {e}")
        return {}

def resolve_constant(const_name: str, content: str) -> Optional[str]:
    """Resolve a constant name to its actual value by searching in the file content."""
    # Try different patterns for constant definitions
    patterns = [
        rf'export const {const_name}\s*=\s*"([^"]*)"',  # export const X = "value"
        rf'const {const_name}\s*=\s*"([^"]*)"',         # const X = "value"
        rf'{const_name}\s*=\s*"([^"]*)"',               # X = "value"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    return None

def generate_sentinelbench_jsonl(base_url: str = "http://localhost:5174") -> List[Dict[str, Any]]:
    """
    Generate JSONL data by parsing routes.ts directly, applying the same logic
    as the browser's downloadChallengesJSONL function.
    """
    # Find the routes.ts file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    routes_file = os.path.join(script_dir, "src", "router", "routes.ts")
    
    if not os.path.exists(routes_file):
        raise FileNotFoundError(f"Could not find routes.ts at {routes_file}")
    
    print(f"Reading routes from {routes_file}")
    
    # Parse the routes
    all_routes = parse_routes_ts(routes_file)
    
    # Apply the same filtering logic as downloadChallengesJSONL:
    # routes.filter(route => route.tags?.includes("sentinel") && 
    #               route.path !== "sentinel-visualization" && 
    #               route.component !== null &&
    #               route.password !== undefined)
    sentinel_routes = []
    for route in all_routes:
        tags = route.get('tags', [])
        path = route.get('path', '')
        has_component = route.get('has_component', False)
        password = route.get('password')
        
        if ('sentinel' in tags and 
            path != 'sentinel-visualization' and 
            path != 'visualization' and  # Exclude Task Framework
            has_component and
            password is not None):  # Must have a password to be a real task
            sentinel_routes.append(route)
    
    # Clean up routes (same logic as the browser function)
    cleaned_routes = []
    for route in sentinel_routes:
        clean_route = {
            'id': route.get('path'),
            'path': route.get('path'),
            'title': route.get('title'),
            'description': route.get('description'),
            'url': route.get('url', '').replace('{base_url}', base_url),
            'icon': route.get('icon'),
            'tags': route.get('tags'),
            'password': route.get('password'),
            'difficulty': route.get('difficulty'),
            'base_task': route.get('base_task'),
            'duration': route.get('duration'),
            'criteria': route.get('criteria'),
            'activity': route.get('activity'),
            'noise': route.get('noise'),
            'realism': route.get('realism'),
            'relative_vs_absolute': route.get('relative_vs_absolute', ''),
            'adversarial_attacks': route.get('adversarial_attacks', False),
            'failure_tolerance': route.get('failure_tolerance', '')
        }
        
        # Remove undefined/null values to keep JSONL clean (same as browser)
        clean_route = {k: v for k, v in clean_route.items() if v is not None}
        cleaned_routes.append(clean_route)
    
    print(f"Found {len(cleaned_routes)} sentinel tasks")
    return cleaned_routes


def main():
    """Main function to generate the JSONL file."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate SentinelBench tasks JSONL")
    parser.add_argument("--url", default="http://localhost:5174", 
                       help="Base URL for SentinelBench (default: http://localhost:5174)")
    parser.add_argument("--output", default="test.jsonl",
                       help="Output file name (default: test.jsonl)")
    
    args = parser.parse_args()
    
    print(f"Generating SentinelBench tasks from {args.url}...")
    
    tasks = generate_sentinelbench_jsonl(args.url)
    
    # Write JSONL file
    with open(args.output, 'w') as f:
        for task in tasks:
            f.write(json.dumps(task) + '\n')
    
    print(f"Generated {len(tasks)} tasks in {args.output}")
    
    # Print summary
    difficulties = {}
    for task in tasks:
        diff = task.get('difficulty', 'unknown')
        difficulties[diff] = difficulties.get(diff, 0) + 1
    
    print(f"Task breakdown: {difficulties}")


if __name__ == "__main__":
    main()