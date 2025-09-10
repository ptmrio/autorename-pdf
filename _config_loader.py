"""
Configuration loader for YAML files.
Replaces the old .env file loading functionality.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional


def load_yaml_config(config_path: str) -> Optional[Dict[str, Any]]:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path (str): Path to the YAML configuration file
        
    Returns:
        Dict[str, Any]: Configuration dictionary or None if file doesn't exist
    """
    if not os.path.exists(config_path):
        logging.warning(f'Config file {config_path} not found')
        return None
        
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            logging.info(f'Successfully loaded config from {config_path}')
            return config
    except yaml.YAMLError as e:
        logging.error(f'Error parsing YAML config file {config_path}: {e}')
        return None
    except Exception as e:
        logging.error(f'Error loading config file {config_path}: {e}')
        return None


def load_company_names(yaml_path: str) -> Dict[str, list]:
    """
    Load harmonized company names from YAML file.
    
    Args:
        yaml_path (str): Path to the company names YAML file
        
    Returns:
        Dict[str, list]: Company name mappings
    """
    if not os.path.exists(yaml_path):
        logging.warning(f'Company names file {yaml_path} not found')
        return {}
        
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            company_names = yaml.safe_load(file)
            if not company_names:
                return {}
            logging.info(f'Successfully loaded {len(company_names)} company name mappings')
            return company_names
    except yaml.YAMLError as e:
        logging.error(f'Error parsing YAML company names file {yaml_path}: {e}')
        return {}
    except Exception as e:
        logging.error(f'Error loading company names file {yaml_path}: {e}')
        return {}


def flatten_config_for_env(config: Dict[str, Any], prefix: str = '', separator: str = '_') -> Dict[str, str]:
    """
    Flatten nested YAML config into environment variable format.
    
    Args:
        config: The configuration dictionary
        prefix: Prefix for environment variable names
        separator: Separator for nested keys
        
    Returns:
        Dict[str, str]: Flattened configuration suitable for environment variables
    """
    env_vars = {}
    
    def _flatten(obj: Any, parent_key: str = '') -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{parent_key}{separator}{key.upper()}" if parent_key else key.upper()
                _flatten(value, new_key)
        else:
            env_vars[parent_key] = str(obj) if obj is not None else ''
    
    _flatten(config, prefix.upper() if prefix else '')
    return env_vars


def config_to_env_mapping(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Convert YAML config structure to the environment variable format expected by the application.
    
    Args:
        config: The loaded YAML configuration
        
    Returns:
        Dict[str, str]: Environment variable mappings
    """
    if not config:
        return {}
        
    env_mapping = {}
    
    # OpenAI configuration
    if 'openai' in config:
        openai_config = config['openai']
        if 'api_key' in openai_config:
            env_mapping['OPENAI_API_KEY'] = openai_config['api_key']
        if 'model' in openai_config:
            env_mapping['OPENAI_MODEL'] = openai_config['model']
    
    # Company configuration
    if 'company' in config and 'name' in config['company']:
        env_mapping['MY_COMPANY_NAME'] = config['company']['name']
    
    # Private AI configuration
    if 'private_ai' in config:
        private_ai = config['private_ai']
        env_mapping['PRIVATEAI_ENABLED'] = str(private_ai.get('enabled', False)).lower()
        env_mapping['PRIVATEAI_SCHEME'] = private_ai.get('scheme', 'http')
        env_mapping['PRIVATEAI_HOST'] = private_ai.get('host', 'localhost')
        env_mapping['PRIVATEAI_PORT'] = str(private_ai.get('port', 8001))
        env_mapping['PRIVATEAI_TIMEOUT'] = str(private_ai.get('timeout', 720))
        env_mapping['PRIVATEAI_POST_PROCESSOR'] = private_ai.get('post_processor', 'ollama')
    
    # PDF configuration
    if 'pdf' in config:
        pdf_config = config['pdf']
        env_mapping['PDF_OUTGOING_INVOICE'] = pdf_config.get('outgoing_invoice', 'AR')
        env_mapping['PDF_INCOMING_INVOICE'] = pdf_config.get('incoming_invoice', 'ER')
    
    # Language and localization
    env_mapping['OUTPUT_LANGUAGE'] = config.get('output_language', 'German')
    env_mapping['OUTPUT_DATE_FORMAT'] = config.get('date_format', '%Y%m%d')
    env_mapping['PROMPT_EXTENSION'] = config.get('prompt_extension', '')
    env_mapping['OCR_LANGUAGES'] = config.get('ocr_languages', 'deu,eng')
    
    return env_mapping
