"""
FlawTrack API Configuration Utility
Handles initialization of FlawTrack API v2.0
"""
import os
from typing import Optional
from services.flawtrack_api import FlawTrackAPI
import logging

logger = logging.getLogger(__name__)

def get_flawtrack_api() -> Optional[FlawTrackAPI]:
    """
    Get FlawTrack API instance

    Returns:
        FlawTrackAPI instance or None if not configured
    """
    try:
        # Load environment variables if not already loaded
        from dotenv import load_dotenv
        load_dotenv()

        # Get FlawTrack API credentials
        api_key = os.getenv('FLAWTRACK_API_TOKEN')
        endpoint = os.getenv('FLAWTRACK_API_ENDPOINT')

        if not api_key or not endpoint:
            logger.error("FlawTrack API configuration incomplete. Missing FLAWTRACK_API_TOKEN or FLAWTRACK_API_ENDPOINT")
            return None

        logger.info(f"Initializing FlawTrack API v2.0 with endpoint: {endpoint}")
        return FlawTrackAPI(api_key, endpoint)

    except Exception as e:
        logger.error(f"Failed to initialize FlawTrack API: {str(e)}")
        return None

def get_api_config() -> dict:
    """
    Get current FlawTrack API configuration details

    Returns:
        Dictionary with configuration information
    """
    # Load environment variables if not already loaded
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('FLAWTRACK_API_TOKEN', '')
    endpoint = os.getenv('FLAWTRACK_API_ENDPOINT', '')

    config = {
        'version': 'v2.0',
        'api_key': api_key[:12] + '...' if api_key else '',
        'endpoint': endpoint,
        'scanning_enabled': os.getenv('FLAWTRACK_SCANNING_ENABLED', 'true').lower() == 'true',
        'timeout': int(os.getenv('FLAWTRACK_TIMEOUT', '30')),
        'retry_count': int(os.getenv('FLAWTRACK_RETRY_COUNT', '3')),
        'rate_limit_per_minute': int(os.getenv('FLAWTRACK_RATE_LIMIT_PER_MINUTE', '60')),
        'search_type': os.getenv('FLAWTRACK_SEARCH_TYPE', 'domain'),
        'data_source': os.getenv('FLAWTRACK_DATA_SOURCE', 'unified'),
        'health_check_interval': int(os.getenv('FLAWTRACK_HEALTH_CHECK_INTERVAL', '300')),
        'supports_service_search': True,
        'supports_source_separation': True,
        'supports_deduplication': True,
        'has_health_check': True
    }

    return config

def is_api_configured() -> bool:
    """Check if FlawTrack API is properly configured"""
    api_key = os.getenv('FLAWTRACK_API_TOKEN')
    endpoint = os.getenv('FLAWTRACK_API_ENDPOINT')
    return bool(api_key and endpoint and not api_key.startswith('your-'))

def validate_configuration() -> dict:
    """
    Validate current FlawTrack API configuration

    Returns:
        Dictionary with validation results
    """
    from dotenv import load_dotenv
    load_dotenv()

    results = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'version': 'v2.0'
    }

    # Check scanning enabled
    if not os.getenv('FLAWTRACK_SCANNING_ENABLED', 'true').lower() == 'true':
        results['warnings'].append("FlawTrack scanning is currently disabled")

    # Validate API configuration
    if not os.getenv('FLAWTRACK_API_TOKEN'):
        results['errors'].append("Missing FLAWTRACK_API_TOKEN")
    if not os.getenv('FLAWTRACK_API_ENDPOINT'):
        results['errors'].append("Missing FLAWTRACK_API_ENDPOINT")

    # Validate search type
    search_type = os.getenv('FLAWTRACK_SEARCH_TYPE', 'domain')
    if search_type not in ['domain', 'service']:
        results['warnings'].append(f"Invalid FLAWTRACK_SEARCH_TYPE '{search_type}', defaulting to 'domain'")

    # Validate data source
    data_source = os.getenv('FLAWTRACK_DATA_SOURCE', 'unified')
    if data_source not in ['unified', 'bigquery', 'database']:
        results['warnings'].append(f"Invalid FLAWTRACK_DATA_SOURCE '{data_source}', defaulting to 'unified'")

    # Validate common settings
    try:
        timeout = int(os.getenv('FLAWTRACK_TIMEOUT', '30'))
        if timeout <= 0:
            results['warnings'].append("FLAWTRACK_TIMEOUT should be greater than 0")
    except ValueError:
        results['warnings'].append("Invalid FLAWTRACK_TIMEOUT value")

    try:
        retry_count = int(os.getenv('FLAWTRACK_RETRY_COUNT', '3'))
        if retry_count < 0:
            results['warnings'].append("FLAWTRACK_RETRY_COUNT should be non-negative")
    except ValueError:
        results['warnings'].append("Invalid FLAWTRACK_RETRY_COUNT value")

    results['valid'] = len(results['errors']) == 0

    return results