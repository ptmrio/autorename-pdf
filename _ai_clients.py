"""
AI client initialization and management for OpenAI and PrivateGPT.
This module handles the initialization and management of AI clients.
"""

import os
import logging
import httpx
from openai import OpenAI
from pgpt_python.client import PrivateGPTApi

# Global client variable
client = None

def set_env_vars(env_vars):
    """Set environment variables from a dictionary."""
    for key, value in env_vars.items():
        os.environ[key] = value

def initialize_privateai_client():
    """Initialize the PrivateGPT client."""
    global client
    
    scheme = os.getenv('PRIVATEAI_SCHEME', 'http')
    host = os.getenv('PRIVATEAI_HOST', "localhost")
    port = os.getenv('PRIVATEAI_PORT', "8001")
    timeout = os.getenv('PRIVATEAI_TIMEOUT', 720)
    base_url = f'%s://%s:%s' % (scheme, host, port)        
    
    httpx_client = httpx.Client(timeout=timeout)
    client = PrivateGPTApi(base_url=base_url, 
                           httpx_client=httpx_client)
    
    try:
        health_status = client.health.health()
        logging.info(f"PrivateGPT health check: {health_status.status}")
    except Exception as e:
        logging.warning(f"PrivateGPT health check failed: {e}")

def initialize_openai_client(api_key):
    """Initialize the OpenAI client."""
    global client
    client = OpenAI(api_key=api_key)

def get_client():
    """Get the current AI client instance."""
    return client
