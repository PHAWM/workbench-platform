import litserve as ls
import os
from typing import Optional, Dict, Any, Union
from starlette.middleware.cors import CORSMiddleware
import litellm
import asyncio

class UnifiedLLMInferenceAPI(ls.LitAPI):
    def setup(self, device):
        """Set up the LLM clients and configurations"""
        # Initialise any persistent configurations
        self.supported_providers = {
            "openai": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
            "anthropic": ["claude-3-sonnet-20240229", "claude-3-haiku-20240307", "claude-3-opus-20240229"],
            "gemini": ["gemini-pro", "gemini-pro-vision"],
            "groq": ["mixtral-8x7b-32768", "llama2-70b-4096"]
        }
        
        # Set default configurations
        self.default_config = {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
        }

    def decode_request(self, request):
        """Convert the request payload to model input."""
        # Check if this is a batch request
        if "batch_requests" in request:
            return {"is_batch": True, "batch_requests": request["batch_requests"]}
        
        # Single request processing
        # Extract required fields
        prompt = request.get("prompt")
        model_name = request.get("model_name")
        api_key = request.get("api_key")
        model_provider = request.get("model_provider", "openai")
        
        # Extract optional fields
        system_prompt = request.get("system_prompt")
        temperature = request.get("temperature", self.default_config["temperature"])
        max_tokens = request.get("max_tokens", self.default_config["max_tokens"])
        
        # Extract additional parameters
        kwargs = {k: v for k, v in request.items() 
                 if k not in ["prompt", "model_name", "api_key", "model_provider", 
                            "system_prompt", "temperature", "max_tokens"]}
        
        return {
            "is_batch": False,
            "prompt": prompt,
            "model_name": model_name,
            "api_key": api_key,
            "model_provider": model_provider,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "kwargs": kwargs
        }

    def predict(self, inputs):
        """
        Run LLM inference - handles both single and batch requests
        
        Args:
            inputs (dict): Dictionary containing either:
                Single request:
                - prompt (str): The input prompt/message
                - model_name (str): Model identifier
                - api_key (str): API key for the model provider
                - model_provider (str): Provider name ("openai", "anthropic", "gemini", etc.)
                - system_prompt (str, optional): System prompt for the model
                - temperature (float): Temperature for generation
                - max_tokens (int): Maximum tokens to generate
                - kwargs (dict): Additional parameters
                
                Batch request:
                - is_batch (bool): True for batch requests
                - batch_requests (list): List of single request dictionaries
                
        Returns:
            dict: Response with success status, output, and metadata
        """
        try:
            # Check if this is a batch request
            if inputs.get("is_batch", False):
                return self._process_batch_requests(inputs["batch_requests"])
            
            # Single request processing
            # Validate required inputs
            if not inputs.get("prompt"):
                raise ValueError("Prompt is required")
            if not inputs.get("model_name"):
                raise ValueError("Model name is required")
            if not inputs.get("api_key"):
                raise ValueError("API key is required")
            
            # Validate provider and model
            provider = inputs["model_provider"].lower()
            model_name = inputs["model_name"]
            
            if provider in self.supported_providers:
                if model_name not in self.supported_providers[provider]:
                    available_models = ", ".join(self.supported_providers[provider])
                    return {
                        "success": False,
                        "output": None,
                        "model_name": model_name,
                        "model_provider": provider,
                        "error": f"Model {model_name} not supported for {provider}. Available models: {available_models}",
                        "usage": None,
                        "cost": None
                    }
            
            # Use LiteLLM for inference
            response = self._run_litellm_inference(inputs)
            return response
            
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "model_name": inputs.get("model_name"),
                "model_provider": inputs.get("model_provider"),
                "error": str(e),
                "usage": None,
                "cost": None
            }

    def _process_batch_requests(self, batch_requests):
        """Process a batch of inference requests"""
        results = []
        total_cost = 0.0
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        for i, single_request in enumerate(batch_requests):
            try:
                # Decode each individual request
                decoded_input = self._decode_single_request(single_request)
                
                # Run single inference
                result = self._run_single_inference(decoded_input)
                results.append(result)
                
                # Aggregate costs and usage
                if result.get("cost"):
                    total_cost += result["cost"]
                if result.get("usage"):
                    usage = result["usage"]
                    total_tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    total_tokens["completion_tokens"] += usage.get("completion_tokens", 0)
                    total_tokens["total_tokens"] += usage.get("total_tokens", 0)
                    
            except Exception as e:
                results.append({
                    "success": False,
                    "output": None,
                    "model_name": single_request.get("model_name"),
                    "model_provider": single_request.get("model_provider"),
                    "error": f"Batch item {i}: {str(e)}",
                    "usage": None,
                    "cost": None
                })
        
        return {
            "is_batch": True,
            "batch_results": results,
            "total_requests": len(batch_requests),
            "successful_requests": sum(1 for r in results if r.get("success")),
            "failed_requests": sum(1 for r in results if not r.get("success")),
            "total_cost": total_cost if total_cost > 0 else None,
            "total_usage": total_tokens if total_tokens["total_tokens"] > 0 else None
        }

    def _decode_single_request(self, request):
        """Decode a single request from batch processing"""
        model_provider = request.get("model_provider", "openai")
        temperature = request.get("temperature", self.default_config["temperature"])
        max_tokens = request.get("max_tokens", self.default_config["max_tokens"])
        
        kwargs = {k: v for k, v in request.items() 
                 if k not in ["prompt", "model_name", "api_key", "model_provider", 
                            "system_prompt", "temperature", "max_tokens"]}
        
        return {
            "prompt": request.get("prompt"),
            "model_name": request.get("model_name"),
            "api_key": request.get("api_key"),
            "model_provider": model_provider,
            "system_prompt": request.get("system_prompt"),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "kwargs": kwargs
        }

    def _run_single_inference(self, inputs):
        """Run a single inference (used by both single and batch processing)"""
        try:
            # Validate required inputs
            if not inputs.get("prompt"):
                raise ValueError("Prompt is required")
            if not inputs.get("model_name"):
                raise ValueError("Model name is required")
            if not inputs.get("api_key"):
                raise ValueError("API key is required")
            
            # Validate provider and model
            provider = inputs["model_provider"].lower()
            model_name = inputs["model_name"]
            
            if provider in self.supported_providers:
                if model_name not in self.supported_providers[provider]:
                    available_models = ", ".join(self.supported_providers[provider])
                    return {
                        "success": False,
                        "output": None,
                        "model_name": model_name,
                        "model_provider": provider,
                        "error": f"Model {model_name} not supported for {provider}. Available models: {available_models}",
                        "usage": None,
                        "cost": None
                    }
            
            # Use LiteLLM for inference
            response = self._run_litellm_inference(inputs)
            return response
            
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "model_name": inputs.get("model_name"),
                "model_provider": inputs.get("model_provider"),
                "error": str(e),
                "usage": None,
                "cost": None
            }

    def _run_litellm_inference(self, inputs):
        """Run inference using LiteLLM"""
        try:
            # Set API key based on provider
            provider = inputs["model_provider"].lower()
            api_key = inputs["api_key"]
            
            # Set environment variable for the provider
            if provider == "openai":
                os.environ["OPENAI_API_KEY"] = api_key
                model_ref = inputs["model_name"]
            elif provider == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = api_key
                model_ref = inputs["model_name"]
            elif provider == "gemini" or provider == "google":
                os.environ["GEMINI_API_KEY"] = api_key
                model_ref = f"gemini/{inputs['model_name']}"
            elif provider == "groq":
                os.environ["GROQ_API_KEY"] = api_key
                model_ref = f"groq/{inputs['model_name']}"
            else:
                model_ref = inputs["model_name"]
            
            # Prepare messages
            messages = []
            if inputs.get("system_prompt"):
                messages.append({"role": "system", "content": inputs["system_prompt"]})
            messages.append({"role": "user", "content": inputs["prompt"]})
            
            # Run inference
            response = litellm.completion(
                model=model_ref,
                messages=messages,
                temperature=inputs["temperature"],
                max_tokens=inputs["max_tokens"],
                **inputs["kwargs"]
            )
            
            # Calculate cost if possible
            try:
                cost = litellm.completion_cost(completion_response=response)
            except:
                cost = None
            
            return {
                "success": True,
                "output": response.choices[0].message.content,
                "model_name": inputs["model_name"],
                "model_provider": inputs["model_provider"],
                "error": None,
                "usage": response.usage._asdict() if response.usage else None,
                "cost": cost
            }
            
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "model_name": inputs["model_name"],
                "model_provider": inputs["model_provider"],
                "error": str(e),
                "usage": None,
                "cost": None
            }

    def encode_response(self, output):
        """Convert the model output to a response payload"""
        return output

class BatchLLMInferenceAPI(ls.LitAPI):
    """Legacy API class - now just redirects to UnifiedLLMInferenceAPI"""
    
    def setup(self, device):
        """Set up the batch processing configuration"""
        self.unified_api = UnifiedLLMInferenceAPI()
        self.unified_api.setup(device)

    def decode_request(self, request):
        """Decode batch request"""
        batch_requests = request.get("batch_requests", [])
        return {"is_batch": True, "batch_requests": batch_requests}

    def predict(self, inputs):
        """Process batch of requests"""
        return self.unified_api.predict(inputs)

    def encode_response(self, output):
        """Encode batch response"""
        return output

def run_llm_inference_api(port=8003):
    """
    Run the unified LLM inference API server (handles both single and batch)
    
    Args:
        port (int): Port to run the server on
    """
    
    api = UnifiedLLMInferenceAPI()
    
    # Configure CORS
    cors_middleware = (
        CORSMiddleware,
        {
            "allow_origins": ["*"],
            "allow_methods": ["GET", "POST"],
            "allow_headers": ["*"],
        }
    )
    
    # Create and configure server
    server = ls.LitServer(
        api,
        middlewares=[cors_middleware],
        workers_per_device=1
    )
    
    print(f"Starting Unified LLM Inference API on port {port}")
    print("API Documentation:")
    print("POST / - Single or Batch inference")
    print("\nSingle Request:")
    print("  Required: prompt, model_name, api_key")
    print("  Optional: model_provider, system_prompt, temperature, max_tokens")
    print("\nBatch Request:")
    print("  Send 'batch_requests' array with multiple inference requests")
    print("  Each item in array should be a single request object")
    print("\nExample single request:")
    print('  {"prompt": "Hello", "model_name": "gpt-3.5-turbo", "api_key": "sk-..."}')
    print("\nExample batch request:")
    print('  {"batch_requests": [{"prompt": "Hello", ...}, {"prompt": "World", ...}]}')
    
    server.run(
        port=port,
        generate_client_file=False
    )

def run_both_apis():
    """Deprecated - now just runs the unified API"""
    print("Note: Both APIs are now unified into a single endpoint.")
    print("The unified API automatically detects single vs batch requests.")
    run_llm_inference_api(port=8003)

if __name__ == "__main__":
    run_llm_inference_api(port=8003)