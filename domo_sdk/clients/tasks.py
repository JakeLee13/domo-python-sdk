"""
Task assignment and response collection client for Domo SDK.
"""

import pandas as pd

from ..core import _get_domo_client, _config
from .queues import Queues


class Tasks:
    """Task assignment and response collection client."""
    
    def __init__(self):
        self._queues = Queues()
    
    def create(self, assignee_id: str, form_id: str, queue_id: str):
        """
        Create task assignment for user.
        
        Args:
            assignee_id: ID of user to assign task to
            form_id: ID of form for the task
            queue_id: ID of queue to add task to
            
        Returns:
            Created task information
        """
        domo_client = _get_domo_client()
        
        self._queues.add(assignee_id, queue_id)
        
        task_data = {
            "queueId": queue_id,
            "assignedTo": int(assignee_id),
            "assigneeType": "USER",
            "status": "OPEN",
            "sourceSystem": "ODYSSEY",
            "displayType": "ENIGMA_FORM",
            "displayId": form_id,
            "contract": {
                "input": [],
                "output": [{
                    "name": "response",
                    "type": "text",
                    "required": False
                }]
            },
            "inputVariables": {},
            "outputVariables": {}
        }
        
        url = f"{_config['hostname']}/api/queues/v1/{queue_id}/tasks"
        response = domo_client._post(url, task_data)
        return response.json()
    
    def responses(self, queue_id: str):
        """
        Get all task responses as DataFrame.
        
        Args:
            queue_id: ID of queue to get responses from
            
        Returns:
            pandas.DataFrame with task responses
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/queues/v1/{queue_id}/tasks"
        
        response = domo_client._get(url, params={'limit': 1000, 'render': 'true'})
        tasks_data = response.json()
        
        tasks = tasks_data if isinstance(tasks_data, list) else tasks_data.get('tasks', [])
        
        task_records = []
        for task in tasks:
            record = {
                'task_id': task.get('id'),
                'status': task.get('status'),
                'assignee_id': str(task.get('assignedTo', '')),
                'assignee_name': task.get('assigneeName', ''),
                'created_date': task.get('createdOn'),
                'completed_date': task.get('completedOn', ''),
                'form_id': task.get('displayId')
            }
            
            output_vars = task.get('outputVariables', {})
            for key, value in output_vars.items():
                record[key] = str(value).strip() if value else ''
            
            task_records.append(record)
        
        return pd.DataFrame(task_records)

