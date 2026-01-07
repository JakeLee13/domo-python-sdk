"""
User management client for Domo SDK.
"""

from typing import Optional, Union, List
import pandas as pd

from ..core import _get_pydomo_client


class Users:
    """User management client through PyDomo."""
    
    def list_all(self, as_dataframe: bool = True, batch_size: int = 500) -> Union[pd.DataFrame, List[dict]]:
        """
        Get all users in the Domo instance.
        
        Args:
            as_dataframe: Return as pandas DataFrame (True) or list of dicts (False)
            batch_size: Number of users to fetch per batch
            
        Returns:
            DataFrame or list containing all users with id, displayName, emailAddress, etc.
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.users.list_all(df_output=as_dataframe, batch_size=batch_size)
    
    def get(self, user_id: str) -> dict:
        """
        Get details for a specific user.
        
        Args:
            user_id: ID of the user to retrieve
            
        Returns:
            User information dictionary
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.users.get(user_id)
    
    def find_by_email(self, email: str) -> Optional[dict]:
        """
        Find a user by their email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            User information dictionary if found, None otherwise
        """
        users_df = self.list_all(as_dataframe=True)
        matches = users_df[users_df['emailAddress'].str.lower() == email.lower()]
        
        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches.iloc[0].to_dict()
        else:
            # Multiple matches - return the first active one or just the first
            active_matches = matches[matches.get('active', True)]
            if len(active_matches) > 0:
                return active_matches.iloc[0].to_dict()
            return matches.iloc[0].to_dict()
    
    def find_by_name(self, name: str) -> Optional[dict]:
        """
        Find a user by their display name.
        
        Args:
            name: Display name to search for (case-insensitive)
            
        Returns:
            User information dictionary if found, None otherwise
        """
        users_df = self.list_all(as_dataframe=True)
        matches = users_df[users_df['displayName'].str.lower() == name.lower()]
        
        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches.iloc[0].to_dict()
        else:
            # Multiple matches - return the first active one or just the first
            active_matches = matches[matches.get('active', True)]
            if len(active_matches) > 0:
                return active_matches.iloc[0].to_dict()
            return matches.iloc[0].to_dict()
    
    def create(self, user_request: dict, send_invite: bool = True) -> dict:
        """
        Create a new user.
        
        Args:
            user_request: Dictionary containing user details (name, email, role, etc.)
            send_invite: Whether to send invitation email to the new user
            
        Returns:
            Created user information
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.users.create(user_request, send_invite)
    
    def update(self, user_id: str, user_update: dict) -> dict:
        """
        Update an existing user.
        
        Args:
            user_id: ID of user to update
            user_update: Dictionary containing fields to update
            
        Returns:
            Updated user information
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.users.update(user_id, user_update)
    
    def delete(self, user_id: str) -> bool:
        """
        Delete a user.
        
        Args:
            user_id: ID of user to delete
            
        Returns:
            True if successful
        """
        pydomo_client = _get_pydomo_client()
        pydomo_client.users.delete(user_id)
        return True