"""
Dataset management client for Domo SDK.
"""

from ..core import _get_pydomo_client


class Data:
    """
    Dataset management client through PyDomo.
    
    Note: This is a thin wrapper around PyDomo. For advanced features,
    consider using PyDomo directly.
    """
    
    def get(self, dataset_id: str, use_schema: bool = True):
        """
        Get dataset as pandas DataFrame.
        
        Args:
            dataset_id: Domo dataset ID
            use_schema: Whether to use schema for data types
            
        Returns:
            pandas.DataFrame containing the dataset
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.ds_get(dataset_id, use_schema=use_schema)
    
    def create(self, dataframe, name: str, description: str = ""):
        """
        Create new dataset from DataFrame.
        
        Args:
            dataframe: pandas DataFrame to upload
            name: Dataset name
            description: Dataset description
            
        Returns:
            Dataset creation response
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.ds_create(dataframe, name, description)
    
    def replace(self, dataset_id: str, dataframe):
        """
        Replace existing dataset with new data.
        
        Args:
            dataset_id: ID of dataset to replace
            dataframe: New pandas DataFrame data
            
        Returns:
            Dataset update response
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.ds_update(dataset_id, dataframe)
    
    def query(self, dataset_id: str, query):
        """
        Query a dataset using SQL.
        
        Args:
            dataset_id: Dataset to query
            query: SQL query string
            
        Returns:
            Query results as DataFrame
        """
        pydomo_client = _get_pydomo_client()
        return pydomo_client.ds_query(dataset_id, query)