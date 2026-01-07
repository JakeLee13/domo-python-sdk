"""
Form creation client for Domo SDK.
"""

import uuid

from ..core import _get_domo_client, _config


class Forms:
    """Simple form creation client for data collection."""
    
    def create(self, name: str, question: str, placeholder: str = "", required: bool = False):
        """
        Create single-question form.
        
        Args:
            name: Form name
            question: Question text to display
            placeholder: Placeholder text for input field
            required: Whether the field is required
            
        Returns:
            Created form information
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/forms/v2"
        
        section_id = str(uuid.uuid4())
        domain_id = str(uuid.uuid4())
        field_id = str(uuid.uuid4())
        
        form_data = {
            "version": "0.0.0",
            "domainType": "WORKFLOW",
            "domainId": f"{domain_id} - 1.0.0",
            "name": name,
            "description": "",
            "sections": [{
                "id": section_id,
                "title": "",
                "fields": [{
                    "id": field_id,
                    "label": question,
                    "placeholder": placeholder,
                    "optional": not required,
                    "fieldType": "LONG_ANSWER",
                    "dataType": "text",
                    "acceptsInput": False,
                    "acceptsOutput": True,
                    "alias": "response"
                }]
            }],
            "settings": {"hideSectionHeaderDetails": True},
            "attributes": [{"type": "paragraph", "children": [{"text": ""}]}],
            "fieldConfiguration": {
                field_id: {
                    "options": {"type": "CUSTOM"},
                    "targetMapping": {"target": "response"}
                }
            },
            "submitConfiguration": {"type": "UNASSIGNED", "isDatasetOwner": False},
            "searchable": False,
            "userPermissions": [],
            "submitConfigurationType": "UNASSIGNED"
        }
        
        response = domo_client._post(url, form_data)
        return response.json()
    
    def get(self, form_id: str):
        """
        Get form details by ID.

        Args:
            form_id: ID of form to retrieve

        Returns:
            Form information dictionary
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/forms/v2/{form_id}"

        response = domo_client._get(url)
        return response.json()

