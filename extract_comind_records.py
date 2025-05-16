import json
import os
import sys
import argparse
import re
from typing import List, Dict, Any

def print_header(text):
    """Print a header with decoration"""
    print(f"\n{'=' * 40}")
    print(f"   {text}")
    print(f"{'=' * 40}\n")

def find_history_files() -> List[str]:
    """Find all history files in the current directory"""
    files = []
    for filename in os.listdir('.'):
        if filename.startswith('session_') and filename.endswith('.txt'):
            files.append(filename)
        elif filename == 'history.txt':
            files.append(filename)
    return files

def extract_records_from_file(file_path: str) -> List[Dict[str, Any]]:
    """Extract comind records from a history file"""
    records = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for JSON objects that represent comind records
        # Try different patterns to identify JSON objects

        # Pattern 1: Look for {"uri": "at://.../me.comind...} JSON objects
        uri_pattern = r'{\s*"uri":\s*"at://[^"]+/me\.comind\.[^"]+",\s*"cid":'
        for match in re.finditer(uri_pattern, content):
            start_pos = match.start()
            # Find the end of the JSON object
            brace_count = 1
            end_pos = start_pos + 1
            while brace_count > 0 and end_pos < len(content):
                if content[end_pos] == '{':
                    brace_count += 1
                elif content[end_pos] == '}':
                    brace_count -= 1
                end_pos += 1
            
            if brace_count == 0:
                json_str = content[start_pos:end_pos]
                try:
                    record = json.loads(json_str)
                    if "uri" in record and "cid" in record and "value" in record:
                        # Check if record has a URI that contains me.comind
                        if "me.comind" in record["uri"]:
                            records.append(record)
                except json.JSONDecodeError:
                    # Skip invalid JSON
                    continue
        
        # Pattern 2: Look for ATProto records in uploadBlobs calls
        upload_pattern = r'uploadBlobs\(\s*({.*?}),\s*\['
        for match in re.finditer(upload_pattern, content, re.DOTALL):
            try:
                json_str = match.group(1)
                # Clean up the string to make it valid JSON
                json_str = re.sub(r'(\w+):', r'"\1":', json_str)
                json_str = re.sub(r'\'', r'"', json_str)
                record_dict = json.loads(json_str)
                
                # Extract records from the dictionary
                for key, value in record_dict.items():
                    if key.startswith('me.comind.') and isinstance(value, list):
                        for record in value:
                            if isinstance(record, dict) and "uri" in record and "cid" in record and "value" in record:
                                if "me.comind" in record["uri"]:
                                    records.append(record)
            except (json.JSONDecodeError, IndexError):
                # Skip invalid JSON
                continue
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    
    return records

def main():
    parser = argparse.ArgumentParser(description="Extract comind records from history files")
    parser.add_argument('--output', '-o', type=str, default='comind_records.json',
                       help='Output file path (default: comind_records.json)')
    parser.add_argument('--input', '-i', type=str, default=None,
                       help='Specific input file to process (optional)')
    args = parser.parse_args()
    
    print_header("Extracting Comind Records")
    
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file {args.input} not found")
            return
        files = [args.input]
    else:
        files = find_history_files()
        print(f"Found {len(files)} potential history files:")
        for f in files:
            print(f"  - {f}")
    
    all_records = []
    for file_path in files:
        print(f"Processing {file_path}...")
        records = extract_records_from_file(file_path)
        print(f"  Found {len(records)} comind records")
        all_records.extend(records)
    
    # Remove duplicates by URI
    unique_records = {}
    for record in all_records:
        uri = record.get('uri')
        if uri and uri not in unique_records:
            unique_records[uri] = record
    
    final_records = list(unique_records.values())
    print(f"Total unique records: {len(final_records)}")
    
    # Save to output file
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(final_records, f, indent=2)
    
    print(f"Saved {len(final_records)} records to {args.output}")
    print(f"You can now import these records with: python import_comind_records.py")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1) 