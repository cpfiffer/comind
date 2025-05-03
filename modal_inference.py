import modal
import sys
import os

# Create our Modal application
app = modal.App("comind-vllm-inference")

# Set up the container image with vLLM and necessary packages
vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.7.2",
        "huggingface_hub[hf_transfer]==0.26.2",
        "flashinfer-python==0.2.0.post2",  # pinning, very unstable
        extra_index_url="https://flashinfer.ai/whl/cu124/torch2.5",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})  # faster model transfers
)

# Enable vLLM's V1 engine for better performance
vllm_image = vllm_image.env({"VLLM_USE_V1": "1"})

# Set up persistent volumes to cache models between runs
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

# Configuration options (can be modified as needed)
MINUTES = 60  # seconds
VLLM_PORT = 8000
API_KEY = "comind-api-key"  # Default API key

# Try to use a secret if it exists, but make it optional
try:
    # Try to use an existing secret
    api_key_secret = modal.Secret.from_name("comind-api-key")
    print("Using existing API key secret")
    has_secret = True
except:
    # If it doesn't exist, we'll just use a default API key
    print("No 'comind-api-key' secret found. Using default API key.")
    print("To create a secret, visit: https://modal.com/secrets/create?secret_name=comind-api-key")
    has_secret = False

# Add these configuration variables for cold start optimization
MIN_CONTAINERS = 1  # Keep at least one container warm at all times
BUFFER_CONTAINERS = 1  # Provision one extra container when function is active

# Define available models
MODELS = {
    "phi4": {
        "name": "microsoft/Phi-4",
        "revision": None,  # Use latest
        "gpu": "A10G:1",   # Adjust based on model size and budget
    },
    "hermes-8b": {
        "name": "NousResearch/Hermes-3-Llama-3.1-8B",
        "revision": None,
        "gpu": "A10G:1",   # 8B model should fit in one A10G
    },
    "hermes-3b": {
        "name": "NousResearch/Hermes-3-Llama-3.2-3B",
        "revision": None,
        "gpu": "T4:1",     # 3B model can run on a T4
    },
    "phi3-mini": {
        "name": "microsoft/Phi-3-mini-4k-instruct",
        "revision": None,
        "gpu": "A10G:1",     # Smaller model can run on cheaper ?
    },
    "tiny-llama": {
        "name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "revision": None,
        "gpu": "T4:1",     # Very small model
    },
    "qwen3-0.6b": {
        "name": "RedHatAI/Qwen3-0.6B-FP8_dynamic",
        "revision": None,
        "gpu": "T4:1",     # Ultra-small model, can run on T4
    },
    "embeddings": {
        "name": "mixedbread-ai/mxbai-embed-xsmall-v1",
        "revision": None,
        "gpu": "T4:1",     # Embeddings can run on T4
    },
}

# Get the default model (for backward compatibility)
DEFAULT_MODEL = "phi4"

# Define a function to get optional secrets list
def get_optional_secrets():
    """Return a list with the API key secret if it exists, otherwise an empty list."""
    if has_secret:
        return [api_key_secret]
    return []

# Define a function to get the API key value
def get_api_key():
    """Get the API key from the environment or default."""
    import os
    # Modal automatically injects secret values as environment variables
    # We'll try to get it from environment, but fall back to our default
    return os.environ.get("api_key", API_KEY)

# Define each model function separately instead of dynamically generating them
@app.function(
    image=vllm_image,
    gpu=MODELS["phi4"]["gpu"],
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=get_optional_secrets(),
    min_containers=MIN_CONTAINERS,
    buffer_containers=BUFFER_CONTAINERS,
    scaledown_window=10 * MINUTES,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def serve_phi4():
    """Serves Microsoft Phi-4 with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_name = MODELS["phi4"]["name"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", get_api_key(),
        "--guided-decoding-backend", "outlines",
        "--trust-remote-code",
    ]
    
    print(f"Starting vLLM server for {model_name} with command: {' '.join(cmd)}")
    subprocess.Popen(" ".join(cmd), shell=True)

@app.function(
    image=vllm_image,
    gpu=MODELS["hermes-8b"]["gpu"],
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=get_optional_secrets(),
    min_containers=MIN_CONTAINERS,
    buffer_containers=BUFFER_CONTAINERS,
    scaledown_window=10 * MINUTES,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def serve_hermes_8b():
    """Serves NousResearch Hermes-3-Llama-3.1-8B with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_name = MODELS["hermes-8b"]["name"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", get_api_key(),
        "--guided-decoding-backend", "outlines",
        "--trust-remote-code",
    ]
    
    print(f"Starting vLLM server for {model_name} with command: {' '.join(cmd)}")
    subprocess.Popen(" ".join(cmd), shell=True)

@app.function(
    image=vllm_image,
    gpu=MODELS["hermes-3b"]["gpu"],
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=get_optional_secrets(),
    min_containers=MIN_CONTAINERS,
    buffer_containers=BUFFER_CONTAINERS,
    scaledown_window=10 * MINUTES,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def serve_hermes_3b():
    """Serves NousResearch Hermes-3-Llama-3.2-3B with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_name = MODELS["hermes-3b"]["name"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", get_api_key(),
        "--guided-decoding-backend", "outlines",
        "--trust-remote-code",
        "--dtype", "half",
    ]
    
    print(f"Starting vLLM server for {model_name} with command: {' '.join(cmd)}")
    subprocess.Popen(" ".join(cmd), shell=True)

@app.function(
    image=vllm_image,
    gpu=MODELS["phi3-mini"]["gpu"],
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=get_optional_secrets(),
    min_containers=MIN_CONTAINERS,
    buffer_containers=BUFFER_CONTAINERS,
    scaledown_window=10 * MINUTES,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def serve_phi3_mini():
    """Serves Microsoft Phi-3-mini with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_name = MODELS["phi3-mini"]["name"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", get_api_key(),
        "--guided-decoding-backend", "outlines",
        "--trust-remote-code",
        "--dtype", "half",
    ]
    
    print(f"Starting vLLM server for {model_name} with command: {' '.join(cmd)}")
    subprocess.Popen(" ".join(cmd), shell=True)

@app.function(
    image=vllm_image,
    gpu=MODELS["tiny-llama"]["gpu"],
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=get_optional_secrets(),
    min_containers=MIN_CONTAINERS,
    buffer_containers=BUFFER_CONTAINERS,
    scaledown_window=10 * MINUTES,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def serve_tiny_llama():
    """Serves TinyLlama model with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_name = MODELS["tiny-llama"]["name"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", get_api_key(),
        "--guided-decoding-backend", "outlines",
        "--trust-remote-code",
        "--dtype", "half",
    ]
    
    print(f"Starting vLLM server for {model_name} with command: {' '.join(cmd)}")
    subprocess.Popen(" ".join(cmd), shell=True)

@app.function(
    image=vllm_image,
    gpu=MODELS["qwen3-0.6b"]["gpu"],
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=get_optional_secrets(),
    min_containers=MIN_CONTAINERS,
    buffer_containers=BUFFER_CONTAINERS,
    scaledown_window=10 * MINUTES,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def serve_qwen3_0_6b():
    """Serves RedHatAI Qwen3-0.6B with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_name = MODELS["qwen3-0.6b"]["name"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", get_api_key(),
        "--guided-decoding-backend", "outlines",
        "--trust-remote-code",
        "--dtype", "half",
    ]
    
    print(f"Starting vLLM server for {model_name} with command: {' '.join(cmd)}")
    subprocess.Popen(" ".join(cmd), shell=True)

@app.function(
    image=vllm_image,
    gpu=MODELS["embeddings"]["gpu"],
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=get_optional_secrets(),
    min_containers=MIN_CONTAINERS,
    buffer_containers=BUFFER_CONTAINERS,
    scaledown_window=10 * MINUTES,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def embeddings():
    """Serves the embeddings model with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_name = MODELS["embeddings"]["name"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", get_api_key(),
        "--guided-decoding-backend", "outlines",
        "--trust-remote-code",
        "--dtype", "half",
    ]
    
    print(f"Starting vLLM server for {model_name} with command: {' '.join(cmd)}")
    subprocess.Popen(" ".join(cmd), shell=True)

# Simple utility functions for the CLI

def create_secret_cli():
    """Create the comind-api-key secret in Modal."""
    print("🔑 Creating 'comind-api-key' secret...")
    
    # Ask for the API key value
    api_key = input("Enter the API key value (press Enter to use 'comind-api-key' as default): ").strip()
    if not api_key:
        api_key = "comind-api-key"
    
    # Create the secret
    try:
        modal.Secret.from_dict({"api_key": api_key}, name="comind-api-key")
        print("✅ Secret created successfully!")
        print(f"Your API key is: {api_key}")
        return True
    except Exception as e:
        print(f"❌ Error creating secret: {e}")
        print("Try creating it manually on the Modal website:")
        print("https://modal.com/secrets/create?secret_name=comind-api-key")
        return False

def deploy_and_warm_cli():
    """Deploy the app and immediately keep containers warm."""
    print("🚀 Deploying Modal inference server...")
    
    # First, check if the API key secret exists
    try:
        modal.Secret.from_name("comind-api-key")
        print("✓ API key secret found")
    except:
        print("⚠️ No 'comind-api-key' secret found.")
        print("You can create one now, or continue without it (a default key will be used).")
        create_now = input("Create secret now? (y/n): ").lower().strip() == 'y'
        if create_now:
            create_secret_cli()
    
    # Ask which models to deploy and warm
    print("\nAvailable models:")
    for idx, (model_key, model_info) in enumerate(MODELS.items(), 1):
        print(f"  {idx}. {model_key} - {model_info['name']} ({model_info['gpu']})")
    
    selected = input("Enter model numbers to deploy (comma-separated, or 'all'): ").strip()
    
    if selected.lower() == 'all':
        models_to_deploy = list(MODELS.keys())
    else:
        try:
            indices = [int(idx.strip()) - 1 for idx in selected.split(',')]
            models_to_deploy = [list(MODELS.keys())[i] for i in indices if 0 <= i < len(MODELS)]
        except:
            print("Invalid selection. Deploying default model only.")
            models_to_deploy = [DEFAULT_MODEL]
    
    print(f"\nDeploying models: {', '.join(models_to_deploy)}")
    
    app.deploy()
    
    print("\n✅ Deployment complete!")
    print("\n🔥 Warming up containers (this reduces cold start time)...")
    import time
    time.sleep(2)  # Give Modal a moment to register the deployment
    
    # Only warm the models that were selected
    for model_key in models_to_deploy:
        if model_key == "phi4":
            serve_phi4.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "hermes-8b":
            serve_hermes_8b.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "hermes-3b":
            serve_hermes_3b.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "phi3-mini":
            serve_phi3_mini.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "tiny-llama":
            serve_tiny_llama.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "qwen3-0.6b":
            serve_qwen3_0_6b.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "embeddings":
            embeddings.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
    
    print("\n🎉 Your Modal inference server is ready!")
    print("\nℹ️  You can access your endpoints at:")
    
    # Get your Modal workspace name
    modal_config_file = os.path.expanduser("~/.modal/config.toml")
    workspace = "your-workspace"  # Default fallback
    if os.path.exists(modal_config_file):
        try:
            with open(modal_config_file, "r") as f:
                for line in f:
                    if "workspace_name" in line:
                        workspace = line.split("=")[1].strip().strip('"')
                        break
        except Exception:
            pass
    
    # Only show deployed model endpoints
    for model_key in models_to_deploy:
        if model_key == "phi4":
            print(f"   - Phi-4: https://{workspace}--comind-vllm-inference-serve-phi4.modal.run/v1")
        elif model_key == "hermes-8b":
            print(f"   - Hermes-8B: https://{workspace}--comind-vllm-inference-serve-hermes-8b.modal.run/v1")
        elif model_key == "hermes-3b":
            print(f"   - Hermes-3B: https://{workspace}--comind-vllm-inference-serve-hermes-3b.modal.run/v1")
        elif model_key == "phi3-mini":
            print(f"   - Phi-3-mini: https://{workspace}--comind-vllm-inference-serve-phi3-mini.modal.run/v1")
        elif model_key == "tiny-llama":
            print(f"   - TinyLlama: https://{workspace}--comind-vllm-inference-serve-tiny-llama.modal.run/v1")
        elif model_key == "qwen3-0.6b":
            print(f"   - Qwen3-0.6B: https://{workspace}--comind-vllm-inference-serve-qwen3-0-6b.modal.run/v1")
        elif model_key == "embeddings":
            print(f"   - Embeddings: https://{workspace}--comind-vllm-inference-embeddings.modal.run/v1")
    
    # Get the API key from our function
    api_key = get_api_key()
    print(f"\n💡 Use API key '{api_key}' for authentication")

def warm_containers_cli():
    """Just warm up the containers without deploying."""
    print("🔥 Warming up containers...")
    
    # Ask which models to warm
    print("\nAvailable models:")
    for idx, (model_key, model_info) in enumerate(MODELS.items(), 1):
        print(f"  {idx}. {model_key} - {model_info['name']} ({model_info['gpu']})")
    
    selected = input("Enter model numbers to warm up (comma-separated, or 'all'): ").strip()
    
    if selected.lower() == 'all':
        models_to_warm = list(MODELS.keys())
    else:
        try:
            indices = [int(idx.strip()) - 1 for idx in selected.split(',')]
            models_to_warm = [list(MODELS.keys())[i] for i in indices if 0 <= i < len(MODELS)]
        except:
            print("Invalid selection. Warming default model only.")
            models_to_warm = [DEFAULT_MODEL]
    
    print(f"\nWarming models: {', '.join(models_to_warm)}")
    
    # Only warm the models that were selected
    for model_key in models_to_warm:
        if model_key == "phi4":
            serve_phi4.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "hermes-8b":
            serve_hermes_8b.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "hermes-3b":
            serve_hermes_3b.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "phi3-mini":
            serve_phi3_mini.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "tiny-llama":
            serve_tiny_llama.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "qwen3-0.6b":
            serve_qwen3_0_6b.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
        elif model_key == "embeddings":
            embeddings.keep_warm(1)
            print(f"  ✓ Warming {model_key}")
    
    print("✅ Containers are warming up!")
    print("   This reduces cold start time for your next requests.")

def check_status_cli():
    """Check the status of your Modal app."""
    try:
        import subprocess
        result = subprocess.run(
            ["modal", "app", "show", "comind-vllm-inference"], 
            capture_output=True, 
            text=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        print("Make sure you have the Modal CLI installed and configured.")

@app.local_entrypoint()
def main():
    """
    Main entrypoint for the script. Handles CLI commands.
    
    Usage:
        modal run modal_inference.py deploy       # Deploy and keep containers warm
        modal run modal_inference.py warm         # Just warm up existing containers
        modal run modal_inference.py status       # Check the status of the app
        modal run modal_inference.py create-secret # Create the API key secret
        modal run modal_inference.py run MODEL    # Run a test request against a specific model
    """
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Deploy and manage Modal inference server")
    parser.add_argument("command", choices=["deploy", "warm", "status", "create-secret", "run"], 
                      default="run", nargs="?",
                      help="Command to execute (default: run a test request)")
    parser.add_argument("model", nargs="?", default=DEFAULT_MODEL,
                      help=f"Model to use (default: {DEFAULT_MODEL})")
    
    args = parser.parse_args()
    
    # Execute the appropriate command
    if args.command == "deploy":
        deploy_and_warm_cli()
    elif args.command == "warm":
        warm_containers_cli()
    elif args.command == "status":
        check_status_cli()
    elif args.command == "create-secret":
        create_secret_cli()
    elif args.command == "run":
        # Run a test request against the specified model
        model = args.model
        if model not in MODELS:
            available_models = ", ".join(MODELS.keys())
            print(f"❌ Model '{model}' not found. Available models: {available_models}")
            sys.exit(1)
            
        print(f"Running test against the {model} server...")
        
        if model == "phi4":
            serve_phi4.remote("Hello, world!")
        elif model == "hermes-8b":
            serve_hermes_8b.remote("Hello, world!")
        elif model == "hermes-3b":
            serve_hermes_3b.remote("Hello, world!")
        elif model == "phi3-mini":
            serve_phi3_mini.remote("Hello, world!")
        elif model == "tiny-llama":
            serve_tiny_llama.remote("Hello, world!")
        elif model == "qwen3-0.6b":
            serve_qwen3_0_6b.remote("Hello, world!")
        elif model == "embeddings":
            embeddings.remote("Hello, world!") 