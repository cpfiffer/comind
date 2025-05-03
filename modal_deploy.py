#!/usr/bin/env python3
"""
Modal Deployment Helper for Comind

This script simplifies deploying the Modal inference server and ensures
containers stay warm to reduce cold start time.

Usage:
    python modal_deploy.py deploy       # Deploy and keep containers warm
    python modal_deploy.py warm         # Just warm up existing containers
    python modal_deploy.py status       # Check container status
    python modal_deploy.py create-secret # Create the API key secret
    python modal_deploy.py run MODEL    # Test a specific model
"""

import sys
import time
import subprocess
import modal
import os

# Import from modal_inference, with error handling
try:
    from modal_inference import (
        app, 
        serve_phi4, 
        serve_hermes_8b,
        serve_hermes_3b,
        serve_phi3_mini,
        serve_tiny_llama,
        serve_qwen3_0_6b,
        embeddings, 
        get_api_key, 
        MODELS,
        DEFAULT_MODEL
    )
except ImportError as e:
    print(f"Error importing from modal_inference.py: {e}")
    print("Make sure modal_inference.py is in the same directory and has no errors.")
    sys.exit(1)

def create_secret():
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

def deploy_and_warm():
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
            create_secret()
    
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
    time.sleep(2)  # Give Modal a moment to register the deployment
    
    # Only warm the models that were selected
    warm_specific_models(models_to_deploy)
    
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

def warm_specific_models(models_to_warm):
    """Warm specific model containers."""
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

def warm_containers():
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
    
    warm_specific_models(models_to_warm)
    
    print("✅ Containers are warming up!")
    print("   This reduces cold start time for your next requests.")

def test_model(model_key):
    """Test a specific model."""
    if model_key not in MODELS:
        available_models = ", ".join(MODELS.keys())
        print(f"❌ Model '{model_key}' not found. Available models: {available_models}")
        return
        
    print(f"Running test against the {model_key} server...")
    
    try:
        if model_key == "phi4":
            serve_phi4.remote("Hello, world!")
        elif model_key == "hermes-8b":
            serve_hermes_8b.remote("Hello, world!")
        elif model_key == "hermes-3b":
            serve_hermes_3b.remote("Hello, world!")
        elif model_key == "phi3-mini":
            serve_phi3_mini.remote("Hello, world!")
        elif model_key == "tiny-llama":
            serve_tiny_llama.remote("Hello, world!")
        elif model_key == "qwen3-0.6b":
            serve_qwen3_0_6b.remote("Hello, world!")
        elif model_key == "embeddings":
            embeddings.remote("Hello, world!")
        print("✅ Test completed successfully!")
    except Exception as e:
        print(f"❌ Test failed: {e}")

def check_status():
    """Check the status of your Modal app."""
    try:
        result = subprocess.run(
            ["modal", "app", "show", "comind-vllm-inference"], 
            capture_output=True, 
            text=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        print("Make sure you have the Modal CLI installed and configured.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "deploy":
        deploy_and_warm()
    elif command == "warm":
        warm_containers()
    elif command == "status":
        check_status()
    elif command == "create-secret":
        create_secret()
    elif command == "run":
        if len(sys.argv) < 3:
            print(f"❌ Please specify a model to run. Available models: {', '.join(MODELS.keys())}")
            sys.exit(1)
        model = sys.argv[2].lower()
        test_model(model)
    else:
        print(f"❌ Unknown command: {command}")
        print(__doc__)
        sys.exit(1) 