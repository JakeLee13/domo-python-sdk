"""
User group management client for Domo SDK.
"""

from typing import Union, List, Optional

from ..core import _get_pydomo_client


class Groups:
    """User group management client."""
    
    def create(self, group_name: str, users: Optional[Union[str, List[str]]] = None, active: bool = True):
        """
        Create new group with optional user assignment.
        
        Args:
            group_name: Name for the new group
            users: User ID or list of user IDs to add to group
            active: Whether the group should be active
            
        Returns:
            Created group information
        """
        pydomo_client = _get_pydomo_client()
        req_body = {'name': group_name, 'active': str(active).lower()}
        group_created = pydomo_client.groups.create(req_body)
        
        if users is not None:
            users = [users] if isinstance(users, str) else users
            if users:
                pydomo_client.groups_add_users(group_created['id'], users)
        
        return group_created
    
    def add(self, group_id: str, user_ids: Union[str, List[str]]):
        """
        Add users to existing group.
        
        Args:
            group_id: ID of the group
            user_ids: User ID or list of user IDs to add
            
        Returns:
            Operation result
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.groups_add_users(group_id, user_ids)
    
    def remove(self, group_id: str, user_ids: Union[str, List[str]]):
        """
        Remove users from group.
        
        Args:
            group_id: ID of the group
            user_ids: User ID or list of user IDs to remove
            
        Returns:
            Operation result
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.groups_remove_users(group_id, user_ids)
