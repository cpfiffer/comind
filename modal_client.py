#!/usr/bin/env python3
"""
Modal Client for Testing Inference API

This script provides a simple client for testing the Modal inference API endpoints.

Usage:
    python modal_client.py --workspace YOUR_WORKSPACE --prompt "Hello, how are you?"
    python modal_client.py --workspace YOUR_WORKSPACE --model hermes-8b --prompt "Tell me a joke"
    python modal_client.py --workspace YOUR_WORKSPACE --model embeddings --prompt "Compute embeddings for this text"

Options:
    --workspace     Your Modal workspace name (required)
    --model         Model to use (default: phi4)
    --api-key       API key (default: comind-api-key)
    --prompt        Prompt to send (default: "Hello, how are you?")
    --stream        Enable streaming (default: False)
    --max-tokens    Maximum tokens to generate (default: 1000)
    --temperature   Temperature for sampling (default: 0.7)
"""

import argparse
import json
import os
import requests
import sys

# Available model endpoints
MODELS = {
    "phi4": "-serve-phi4",
    "hermes-8b": "-serve-hermes-8b",
    "hermes-3b": "-serve-hermes-3b",
    "phi3-mini": "-serve-phi3-mini",
    "tiny-llama": "-serve-tiny-llama",
    "qwen3-0.6b": "-serve-qwen3-0-6b",
    "embeddings": "-embeddings",
}

def get_modal_workspace():
    """Try to get the Modal workspace name from config file."""
    modal_config_file = os.path.expanduser("~/.modal/config.toml")
    if os.path.exists(modal_config_file):
        try:
            with open(modal_config_file, "r") as f:
                for line in f:
                    if "workspace_name" in line:
                        return line.split("=")[1].strip().strip('"')
        except Exception:
            pass
    return None

def main():
    # Get workspace from environment or config if available
    default_workspace = os.environ.get("MODAL_WORKSPACE") or get_modal_workspace()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test Modal inference API")
    parser.add_argument("--workspace", type=str, required=not bool(default_workspace),
                        default=default_workspace,
                        help="Your Modal workspace name")
    parser.add_argument("--model", type=str, default="phi4",
                        choices=list(MODELS.keys()),
                        help="Model to use")
    parser.add_argument("--api-key", type=str, default="comind-api-key",
                        help="API key for authentication")
    parser.add_argument("--prompt", type=str, default="Hello, how are you?",
                        help="Prompt to send")
    parser.add_argument("--stream", action="store_true",
                        help="Enable streaming responses")
    parser.add_argument("--max-tokens", type=int, default=1000,
                        help="Maximum tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Temperature for sampling")
    
    args = parser.parse_args()
    
    if not args.workspace:
        print("❌ Please provide your Modal workspace name with --workspace")
        sys.exit(1)
    
    # Construct the API URL
    model_suffix = MODELS.get(args.model)
    if not model_suffix:
        print(f"❌ Unknown model: {args.model}")
        print(f"Available models: {', '.join(MODELS.keys())}")
        sys.exit(1)
    
    base_url = f"https://{args.workspace}--comind-vllm-inference{model_suffix}.modal.run/v1"
    
    # Make the API request
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {args.api_key}",
    }
    
    if args.model == "embeddings":
        # Use embeddings endpoint
        endpoint = f"{base_url}/embeddings"
        payload = {
            "input": args.prompt,
            "model": "embedding-model"  # This is ignored by the API but required
        }
    else:
        # Use chat completions endpoint
        endpoint = f"{base_url}/chat/completions"
        payload = {
            "model": args.model,  # This is ignored by the API but required
            "messages": [{"role": "user", "content": args.prompt}],
            "stream": args.stream,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
        }
    
    print(f"🔄 Sending request to {endpoint}")
    print(f"📝 Prompt: {args.prompt}")
    
    try:
        if args.stream:
            # Handle streaming response
            response = requests.post(endpoint, json=payload, headers=headers, stream=True)
            response.raise_for_status()
            
            print("\n🤖 Response:")
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                print(content, end='', flush=True)
                        except json.JSONDecodeError:
                            print(f"Error parsing JSON: {data}")
            print()  # Final newline
        else:
            # Handle normal response
            response = requests.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            if args.model == "embeddings":
                print("\n📊 Embeddings generated successfully!")
                print(f"Dimensions: {len(result['data'][0]['embedding'])}")
                print("First 5 values:", result['data'][0]['embedding'][:5])
            else:
                content = result['choices'][0]['message']['content']
                print("\n🤖 Response:")
                print(content)
        
        print("\n✅ Request completed successfully!")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            try:
                error_details = e.response.json()
                print(f"Error details: {json.dumps(error_details, indent=2)}")
            except:
                print(f"Response text: {e.response.text}")

if __name__ == "__main__":
    main() 