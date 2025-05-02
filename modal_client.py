"""
Client example for connecting to the Comind Modal inference server.

This script demonstrates how to use the OpenAI client library to connect
to the Modal-hosted vLLM server.

Usage:
    python modal_client.py --prompt "Your prompt here"
"""

import argparse
from openai import OpenAI

# ANSI colors for prettier output
BLUE = "\033[94m"
GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

def main():
    parser = argparse.ArgumentParser(description="Comind Modal LLM Client")
    parser.add_argument("--prompt", type=str, default="Hello! How are you today?",
                        help="The prompt to send to the LLM")
    parser.add_argument("--workspace", type=str, required=True,
                        help="Your Modal workspace name")
    parser.add_argument("--api-key", type=str, default="comind-api-key",
                        help="API key matching the one in modal_inference.py")
    parser.add_argument("--model", type=str, default="phi4",
                        help="Model endpoint to use (phi4 or embeddings)")
    parser.add_argument("--stream", action="store_true",
                        help="Whether to stream the response")
    
    args = parser.parse_args()
    
    # Construct the base URL based on the model choice
    if args.model == "phi4":
        function_name = "serve-phi4"
        model_name = "microsoft/Phi-4"
    elif args.model == "embeddings":
        function_name = "embeddings"
        model_name = "mixedbread-ai/mxbai-embed-xsmall-v1"
    else:
        print(f"{RED}Error: Unknown model '{args.model}'{END}")
        return

    base_url = f"https://{args.workspace}--comind-vllm-inference-{function_name}.modal.run/v1"
    
    # Initialize the OpenAI client with our Modal API endpoint
    client = OpenAI(
        api_key=args.api_key,
        base_url=base_url
    )
    
    print(f"{BOLD}Connecting to:{END} {base_url}")
    print(f"{BOLD}Prompt:{END} {args.prompt}")
    
    try:
        # Create messages for the chat API
        messages = [{"role": "user", "content": args.prompt}]
        
        if args.stream:
            # Stream the response for a more interactive experience
            print(f"\n{BOLD}{GREEN}Response:{END}", end=" ")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True
            )
            
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    print(f"{content}", end="", flush=True)
            print("\n")
        else:
            # Get the full response at once
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            print(f"\n{BOLD}{GREEN}Response:{END} {response.choices[0].message.content}\n")
            
    except Exception as e:
        print(f"\n{RED}Error: {str(e)}{END}")
        print(f"\n{BLUE}Troubleshooting:{END}")
        print(" - Check that your Modal server is running")
        print(" - Verify the workspace name is correct")
        print(" - Ensure the API key matches the one in modal_inference.py")
        print(" - Check that you're using the correct model endpoint")

if __name__ == "__main__":
    main() 