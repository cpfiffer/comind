import modal

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

# Create our Modal application
app = modal.App("comind-vllm-inference")

# Configuration options (can be modified as needed)
MINUTES = 60  # seconds
VLLM_PORT = 8000
API_KEY = "comind-api-key"  # Replace with a secret for production use

# Define available models (uncomment desired model)
MODELS = {
    "phi4": {
        "name": "microsoft/Phi-4",
        "revision": None,  # Use latest
        "gpu": "A100:1",   # Adjust based on model size and budget
    },
    # "llama3": {
    #     "name": "neuralmagic/Meta-Llama-3.1-8B-Instruct-quantized.w4a16",
    #     "revision": "a7c09948d9a632c2c840722f519672cd94af885d",
    #     "gpu": "A10G:1",
    # },
    # Uncomment and add other models as needed
}

@app.function(
    image=vllm_image,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
)
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def serve_model(model_key="phi4"):
    """
    Serves a vLLM model with OpenAI-compatible API endpoints.
    
    Args:
        model_key: The key of the model to serve from the MODELS dictionary.
    """
    import subprocess
    
    model_config = MODELS.get(model_key)
    if not model_config:
        raise ValueError(f"Model {model_key} not found in MODELS dictionary")
    
    model_name = model_config["name"]
    model_revision = model_config["revision"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
    ]
    
    if model_revision:
        cmd.extend(["--revision", model_revision])
    
    cmd.extend([
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", API_KEY,
    ])
    
    # Optional parameters - uncomment and adjust as needed
    # cmd.extend(["--max-model-len", "15000"])
    # cmd.extend(["--guided-decoding-backend", "outlines"])
    # cmd.extend(["--tensor-parallel-size", "1"])  # For multi-GPU
    
    subprocess.Popen(" ".join(cmd), shell=True)

@app.function(
    image=vllm_image,
    gpu=MODELS["phi4"]["gpu"],  # Use the GPU configuration from the specified model
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    scaledown_window=15 * MINUTES,  # How long to wait with no traffic before scaling down
)
@modal.concurrent(max_inputs=100)  # How many requests can one replica handle
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def serve_phi4():
    """Serves the Phi-4 model with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_config = MODELS["phi4"]
    model_name = model_config["name"]
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", API_KEY,
        "--max-model-len", "15000",
        "--guided-decoding-backend", "outlines",
    ]
    
    subprocess.Popen(" ".join(cmd), shell=True)

@app.function(
    image=vllm_image,
    gpu="A10G:1",  # Embeddings also need GPU access
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    scaledown_window=15 * MINUTES,  # How long to wait with no traffic before scaling down
)
@modal.concurrent(max_inputs=100)  # How many requests can one replica handle
@modal.web_server(port=VLLM_PORT, startup_timeout=5 * MINUTES)
def embeddings():
    """Serves the embeddings model with OpenAI-compatible API endpoints."""
    import subprocess
    
    model_name = "mixedbread-ai/mxbai-embed-xsmall-v1"
    
    cmd = [
        "vllm",
        "serve",
        "--uvicorn-log-level=info",
        model_name,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", API_KEY,
        "--guided-decoding-backend", "outlines",
        "--trust-remote-code",
    ]
    
    subprocess.Popen(" ".join(cmd), shell=True)

@app.local_entrypoint()
def main(model_key="phi4", test=True):
    """
    Local entrypoint for testing the Modal server.
    
    Args:
        model_key: The key of the model to serve from the MODELS dictionary.
        test: Whether to run a test request against the server.
    """
    import json
    import time
    import urllib
    
    # Use the specific model endpoint if available, otherwise use the generic one
    if model_key == "phi4":
        serve_function = serve_phi4
    else:
        # This line would be used for a generic function that can serve any model
        # In this simplified example, we don't define it that way
        raise ValueError(f"No specific endpoint for model {model_key}. Use phi4 or extend the script.")
    
    print(f"Starting server for model {model_key} at {serve_function.web_url}")
    
    if test:
        # Test the server with a health check
        print(f"Running health check for server at {serve_function.web_url}")
        up, start, delay = False, time.time(), 10
        test_timeout = 5 * MINUTES
        
        while not up:
            try:
                with urllib.request.urlopen(serve_function.web_url + "/health") as response:
                    if response.getcode() == 200:
                        up = True
            except Exception:
                if time.time() - start > test_timeout:
                    break
                time.sleep(delay)
        
        assert up, f"Failed health check for server at {serve_function.web_url}"
        print(f"Successful health check for server at {serve_function.web_url}")
        
        # Test with a sample message
        messages = [{"role": "user", "content": "Testing! Is this thing on?"}]
        print(f"Sending a sample message to {serve_function.web_url}", *messages, sep="\n")
        
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }
        payload = json.dumps({"messages": messages, "model": MODELS[model_key]["name"]})
        req = urllib.request.Request(
            serve_function.web_url + "/v1/chat/completions",
            data=payload.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            print(json.loads(response.read().decode()))

# To deploy:
# modal deploy modal_inference.py

# To test:
# modal run modal_inference.py

# Client usage example:
# from openai import OpenAI
# client = OpenAI(
#     api_key="comind-api-key",  # Must match API_KEY above
#     base_url="https://yourworkspace--comind-vllm-inference-serve-phi4.modal.run/v1"
# )
# response = client.chat.completions.create(
#     model="microsoft/Phi-4",
#     messages=[{"role": "user", "content": "Hello, how are you?"}]
# )
# print(response.choices[0].message.content) 