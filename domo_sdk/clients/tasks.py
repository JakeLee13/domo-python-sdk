"""
Task assignment and response collection client for Domo SDK.
"""

import pandas as pd

from ..core import _get_domo_client, _config

class Tasks:
    """Task assignment and response collection client."""
    
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
        from .queues import Queues

        domo_client = _get_domo_client()
        queues_client = Queues()
        queues_client.add(assignee_id, queue_id)
        
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
        Get all task responses as DataFrame with form details using Forms client.

        Args:
            queue_id: ID of queue to get responses from

        Returns:
            pandas.DataFrame with comprehensive task responses including form details
        """
        
        from .forms import Forms
        from .users import Users
        domo_client = _get_domo_client()
        
        url = f"{_config['hostname']}/api/queues/v1/{queue_id}/tasks"

        response = domo_client._get(url)
        tasks_data = response.json()
        tasks = tasks_data if isinstance(tasks_data, list) else tasks_data.get('tasks', [])

        users_client = Users()
        all_users_df = users_client.list_all(as_dataframe=True)

        user_lookup = {}
        for _, user in all_users_df.iterrows():
            user_id = str(user['id'])
            user_lookup[user_id] = {
                'name': user.get('name', ''),
                'email': user.get('email', ''),
                'title': user.get('title', '')
            }

        unique_form_ids = {task.get('displayId') for task in tasks if task.get('displayId')}

        forms_client = Forms()
        form_lookup = {}

        for form_id in unique_form_ids:
            try:
                form_lookup[form_id] = forms_client.get(form_id)
            except Exception as e:
                print(f"Could not fetch form {form_id}: {e}")
                form_lookup[form_id] = {}

        task_records = []
        for task in tasks:
            record = {
                'task_id': task.get('id'),
                'status': task.get('status'),
                'assignee_id': str(task.get('assignedTo', '')),
                'assignee_type': task.get('assigneeType', ''),
                'created_date': task.get('createdOn'),
                'completed_date': task.get('completedOn', ''),
                'assigned_by': str(task.get('assignedBy', '')),
                'completed_by': str(task.get('completedBy', '')),
                'form_id': task.get('displayId'),
                'queue_id': task.get('queueId'),
                'source_system': task.get('sourceSystem', ''),
                'display_type': task.get('displayType', '')
            }

            assignee_id = str(task.get('assignedTo', ''))
            if assignee_id and assignee_id in user_lookup:
                assignee_info = user_lookup[assignee_id]
                record.update({
                    'assignee_name': assignee_info['name'],
                    'assignee_email': assignee_info['email'],
                    'assignee_title': assignee_info['title']
                })
            else:
                record.update({
                    'assignee_name': '',
                    'assignee_email': '',
                    'assignee_title': ''
                })

            form_id = task.get('displayId')
            form_data = form_lookup.get(form_id, {})

            if form_data:
                record.update({
                    'form_name': form_data.get('name', ''),
                    'form_description': form_data.get('description', ''),
                    'form_domain_type': form_data.get('domainType', ''),
                    'form_domain_id': form_data.get('domainId', ''),
                    'form_created_by': str(form_data.get('createdBy', '')),
                    'form_created_date': form_data.get('createdOn', ''),
                })

                sections = form_data.get('sections', [])
                if sections and sections[0].get('fields'):
                    first_field = sections[0]['fields'][0]
                    record.update({
                        'field_label': first_field.get('label', ''),
                        'field_description': first_field.get('description', ''),
                        'field_placeholder': first_field.get('placeholder', ''),
                        'field_alias': first_field.get('alias', ''),
                    })
                else:
                    record.update({
                        'field_label': '',
                        'field_description': '',
                        'field_placeholder': '',
                        'field_alias': '',
                    })
            else:
                record.update({
                    'form_name': '',
                    'form_description': '',
                    'form_domain_id': '',
                    'form_created_by': '',
                    'form_created_date': '',
                    'field_label': '',
                    'field_description': '',
                    'field_placeholder': '',
                    'field_alias': '',
                })

            output_vars = task.get('outputVariables', {})
            for key, value in output_vars.items():
                record[key] = str(value).strip() if value else ''

            task_records.append(record)

        return pd.DataFrame(task_records)