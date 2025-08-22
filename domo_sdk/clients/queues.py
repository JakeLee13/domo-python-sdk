"""
Task queue management client for Domo SDK.
"""

from ..core import _get_domo_client, _config


class Queues:
    """Task queue management client."""
    
    def create(self, name: str, description: str = "", active: bool = True):
        """
        Create new task queue.
        
        Args:
            name: Queue name
            description: Queue description
            active: Whether queue should be active
            
        Returns:
            Created queue information
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/queues/v1"
        
        queue_data = {
            "name": name,
            "description": description,
            "active": active,
            "taskLevelFiltersEnabled": False,
            "taskLevelFilters": None
        }
        
        response = domo_client._post(url, queue_data)
        return response.json()
    
    def get(self, queue_id: str):
        """
        Get queue details.
        
        Args:
            queue_id: ID of queue to retrieve
            
        Returns:
            Queue information
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/queues/v1/{queue_id}"
        
        response = domo_client._get(url)
        return response.json()
    
    def add(self, user_id: str, queue_id: str):
        """
        Add user to queue permissions.
        
        Args:
            user_id: ID of user to add
            queue_id: ID of queue to add user to
        """
        domo_client = _get_domo_client()
        
        permissions_url = f"{_config['hostname']}/api/queues/v1/{queue_id}/permissions"
        payload = [{
            "id": user_id,
            "permissions": ["WRITE", "READ", "CREATE_CONTENT", "READ_CONTENT", "UPDATE_CONTENT"],
            "name": "",
            "type": "USER"
        }]
        
        try:
            domo_client._post(permissions_url, payload)
        except Exception as e:
            print(f"Warning: Could not add queue permissions for user {user_id}: {e}")
