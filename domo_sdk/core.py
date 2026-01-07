"""
Core configuration and authentication for Domo SDK.
"""

import os
from domojupyter.domo import Domo, DomoDevTokenAuthentication
from pydomo import Domo as PyDomo


_config = {
    'domo_client': None,
    'pydomo_client': None,
    'dev_token': None,
    'hostname': None,
    'workspace_id': None,
    'llm_settings': {
        'model': "domo.domo_ai.domogpt-medium-v2.1",
        'temperature': 0.5,
        'system': "",
        'max_tokens': 64000
    },
    'email_settings': {
        'package_id': "03ba6971-98d0-4654-9bfd-aa897816df33",
        'version': "2.1.9"
    }
}


def auth(dev_token: str, client_id: str, client_secret: str, 
         hostname: str = None, workspace_id: str = None) -> None:
    """
    Configure Domo authentication with dev token and API credentials.
    
    Args:
        dev_token: Developer token from Domo admin panel
        client_id: API client ID from Domo admin panel  
        client_secret: API client secret from Domo admin panel
        hostname: Domo hostname (defaults to DOMO_HOSTNAME env var)
        workspace_id: Workspace ID (defaults to DOMO_WORKSPACE_ID env var)
    """
    global _config
    
    _config['dev_token'] = dev_token
    _config['hostname'] = hostname or os.environ.get("DOMO_HOSTNAME")
    _config['workspace_id'] = workspace_id or os.environ.get("DOMO_WORKSPACE_ID")
    
    if not _config['dev_token']:
        raise ValueError(f"Dev token required. Generate at: {_config['hostname']}/admin/security/accesstokens")
    if not client_id:
        raise ValueError(f"Client ID required. Create at: {_config['hostname']}/admin/api-clients")
    if not client_secret:
        raise ValueError(f"Client secret required. Create at: {_config['hostname']}/admin/api-clients")
    if not _config['hostname']:
        raise ValueError("Hostname required. Provide as parameter or set DOMO_HOSTNAME environment variable")
    if not _config['workspace_id']:
        raise ValueError("Workspace ID required. Provide as parameter or set DOMO_WORKSPACE_ID environment variable")
    
    _config['domo_client'] = Domo(
        _config['hostname'],
        DomoDevTokenAuthentication(_config['dev_token']), 
        _config['workspace_id']
    )
    
    api_host = os.environ.get('DOMO_API_HOST', 'api.beta.domo.com')
    _config['pydomo_client'] = PyDomo(
        client_id=client_id,
        client_secret=client_secret,
        api_host=api_host
    )
    
    print("Authentication successful")


def _get_domo_client():
    """Get the configured Domo client."""
    if _config['domo_client'] is None:
        raise RuntimeError("SDK not configured. Call auth() first.")
    return _config['domo_client']


def _get_pydomo_client():
    """Get the configured PyDomo client."""
    if _config['pydomo_client'] is None:
        raise RuntimeError("SDK not configured. Call auth() first.")
    return _config['pydomo_client']


def get_config():
    """Get current configuration (for debugging)."""
    return {
        'hostname': _config.get('hostname'),
        'workspace_id': _config.get('workspace_id'),
        'has_domo_client': _config.get('domo_client') is not None,
        'has_pydomo_client': _config.get('pydomo_client') is not None,
        'llm_settings': _config.get('llm_settings'),
        'email_settings': _config.get('email_settings')
    }
