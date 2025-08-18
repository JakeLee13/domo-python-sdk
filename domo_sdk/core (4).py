"""
Core functionality for the Domo Automation SDK.
"""

import os
import time
import requests
import json
import re
from typing import Any, Dict, Optional, List, Callable, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
from IPython.display import display, HTML
from domojupyter.domo import Domo, DomoDevTokenAuthentication
from domojupyter.ai import PromptTemplate
from domojupyter.ai.models.TextGenerationRequest import TextGenerationRequest
from pydomo import Domo as PyDomo

from . import templates


_config = {
    'domo_client': None,
    'pydomo_client': None,
    'dev_token': None,
    'hostname': None,
    'workspace_id': None,
    'llm_settings': {
        'model': "domo.domo_ai.domogpt-medium-v1.2:anthropic",
        'temperature': 0.5,
        'system': "",
        'max_tokens': 64000
    },
    'email_settings': {
        'package_id': "03ba6971-98d0-4654-9bfd-aa897816df33",
        'version': "2.1.9"
    }
}


def auth(dev_token: str, client_id: str, client_secret: str) -> None:
    """Configure Domo authentication with dev token and API credentials."""
    global _config
    
    _config['dev_token'] = dev_token
    _config['hostname'] = os.environ.get("DOMO_HOSTNAME")
    _config['workspace_id'] = os.environ.get("DOMO_WORKSPACE_ID")
    
    if not _config['dev_token']:
        raise ValueError(f"Dev token required. Generate at: {_config['hostname']}/admin/security/accesstokens")
    if not client_id:
        raise ValueError(f"Client ID required. Create at: {_config['hostname']}/admin/api-clients")
    if not client_secret:
        raise ValueError(f"Client secret required. Create at: {_config['hostname']}/admin/api-clients")
    
    _config['domo_client'] = Domo(
        _config['hostname'],
        DomoDevTokenAuthentication(_config['dev_token']), 
        _config['workspace_id']
    )
    
    _config['pydomo_client'] = PyDomo(
        client_id=client_id,
        client_secret=client_secret,
        api_host='api.domo.com'
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


class _LLMInterface:
    """AI text generation interface with expert prompt scaffolding."""
    
    def _call_api(self, prompt: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Execute API call to Domo's AI service."""
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/ai/v1/text/generation"
        
        request_json = TextGenerationRequest(
            input_str=prompt,
            prompt_template=PromptTemplate(prompt),
            parameters=params or {},
            model=_config['llm_settings']['model'],
            system=_config['llm_settings']['system'],
            model_configuration={
                "temperature": _config['llm_settings']['temperature'],
                "maxTokens": _config['llm_settings']['max_tokens']
            }
        ).to_json()
        
        response_json = domo_client._post(url, request_json).json()
        return response_json["output"]
    
    def generate(self, prompt: str, *args, template=None, **kwargs) -> str:
        """Generate AI content with optional expert scaffold templating."""
        formatted_prompt = prompt.format(*args, **kwargs) if args or kwargs else prompt
        
        if template is not None:
            scaffold = templates.get_scaffold(template)
            formatted_prompt = scaffold.format(formatted_prompt)
        
        return self._call_api(formatted_prompt)
    
    def parallel(self, items: List[Any], prompt_func: Callable[[Any], str], 
                max_workers: int = 4, show_progress: bool = True) -> List[str]:
        """Process multiple items in parallel."""
        if not items:
            return []
        
        results = [None] * len(items)
        
        if show_progress:
            print(f"Processing {len(items)} items with {max_workers} workers...")
            start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(prompt_func, item): idx 
                for idx, item in enumerate(items)
            }
            
            completed = 0
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                    completed += 1
                    
                    if show_progress:
                        print(f"Completed {completed}/{len(items)} tasks")
                        
                except Exception as e:
                    print(f"Error processing item {idx}: {e}")
                    results[idx] = f"ERROR: {str(e)}"
        
        if show_progress:
            elapsed = time.time() - start_time
            print(f"Completed in {elapsed:.1f} seconds")
        
        return results
    

class _EmailsInterface:
    """Email delivery through Domo's Code Engine."""
    
    def _call_function(self, function_name: str, **kwargs) -> bool:
        """Execute Code Engine function call."""
        domo_client = _get_domo_client()
        package_id = _config['email_settings']['package_id']
        version = _config['email_settings']['version']
        
        url = f"{_config['hostname']}/api/codeengine/v2/packages/{package_id}/versions/{version}/functions/{function_name}"
        
        payload = {
            "inputVariables": kwargs,
            "settings": {"getLogs": True}
        }
        
        try:
            response = domo_client._post(url, payload)
            response.raise_for_status()
            result = response.json()
            
            if result.get('status') == 'SUCCESS':
                return True
            else:
                print(f"Email failed: {result.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"Email error: {str(e)}")
            return False
    
    def send(self, email: Union[str, List[str]], subject: str, body: str,
             attachments: Optional[List[int]] = None) -> bool:
        """Send email through Domo's Code Engine."""
        recipient_emails = email if isinstance(email, str) else ",".join(email)
        
        return self._call_function(
            "sendEmail",
            recipientEmails=recipient_emails,
            subject=subject,
            body=body,
            personRecipients=[],
            groupRecipients=[],
            attachments=attachments or [],
            attachment=None,
            includeReplyAll=False
        )

class _DataInterface:
    """Dataset management through PyDomo."""
    
    def get(self, dataset_id: str, use_schema: bool = True):
        """Get dataset as pandas DataFrame."""
        pydomo_client = _get_pydomo_client()
        return pydomo_client.ds_get(dataset_id, use_schema=use_schema)
    
    def create(self, dataframe, name: str, description: str = ""):
        """Create new dataset from DataFrame."""
        pydomo_client = _get_pydomo_client()
        return pydomo_client.ds_create(dataframe, name, description)
    
    def replace(self, dataset_id: str, dataframe):
        """Replace existing dataset with new data."""
        pydomo_client = _get_pydomo_client()
        return pydomo_client.ds_update(dataset_id, dataframe)


class _GroupsInterface:
    """User group management."""
    
    def create(self, group_name: str, users: Optional[Union[str, List[str]]] = None, active: bool = True):
        """Create new group with optional user assignment."""
        pydomo_client = _get_pydomo_client()
        req_body = {'name': group_name, 'active': str(active).lower()}
        group_created = pydomo_client.groups.create(req_body)
        
        if users is not None:
            users = [users] if isinstance(users, str) else users
            if users:
                pydomo_client.groups_add_users(group_created['id'], users)
        
        return group_created
    
    def add(self, group_id: str, user_ids: Union[str, List[str]]):
        """Add users to existing group."""
        pydomo_client = _get_pydomo_client()
        return pydomo_client.groups_add_users(group_id, user_ids)
    
    def remove(self, group_id: str, user_ids: Union[str, List[str]]):
        """Remove users from group."""
        pydomo_client = _get_pydomo_client()
        return pydomo_client.groups_remove_users(group_id, user_ids)


class _FormsInterface:
    """Simple form creation for data collection."""
    
    def create(self, name: str, question: str, placeholder: str = "", required: bool = False):
        """Create single-question form."""
        import uuid
        
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


class _TasksInterface:
    """Task assignment and response collection."""
    
    def create(self, assignee_id: str, form_id: str, queue_id: str):
        """Create task assignment for user."""
        domo_client = _get_domo_client()
        
        queues.add(assignee_id, queue_id)
        
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
        """Get all task responses as DataFrame."""
        import pandas as pd
        
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


class _QueuesInterface:
    """Task queue management."""
    
    def create(self, name: str, description: str = "", active: bool = True):
        """Create new task queue."""
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
        """Get queue details."""
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/queues/v1/{queue_id}"
        
        response = domo_client._get(url)
        return response.json()
    
    def add(self, user_id: str, queue_id: str):
        """Add user to queue permissions."""
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


class _WebInterface:
    """Web scraping utilities."""
    
    def scrape(self, url: str, selector: str = None, timeout: int = 10) -> Union[str, List[str], None]:
        """Scrape text content from webpage using CSS selectors."""
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if selector is None:
                return soup.get_text(strip=True)
            
            elements = soup.select(selector)
            if not elements:
                return None
            
            texts = [elem.get_text(strip=True) for elem in elements]
            return texts[0] if len(texts) == 1 else texts
            
        except Exception as e:
            print(f"Scraping error: {str(e)}")
            return None

        
class _AppsInterface:
    """AI-powered application generator."""
    
    def create(self, name: str, description: str) -> Optional[str]:
        """Create complete Domo custom app with AI-generated code."""
        try:
            print(f"Creating app: {name}")
            
            app_code = self._generate_app_code(description)
            if not app_code:
                print("Failed to generate app code")
                return None
            
            app_url = self._create_domo_app(name, app_code)
            if not app_url:
                print("Failed to create app in Domo")
                return None
                
            print("App created successfully")
            print(f"App URL: {app_url}")
            return app_url
            
        except Exception as e:
            print(f"App creation failed: {str(e)}")
            return None
    
    def _generate_app_code(self, description: str) -> Optional[dict]:
        """Generate HTML, CSS, and JS code using expert scaffold."""
        try:
            code_response = llm.generate(description, template="app")
            return self._parse_json_response(code_response)
        except Exception as e:
            print(f"Code generation error: {str(e)}")
            return None

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Parse JSON from LLM response with robust error handling."""
        import json
        import re
        
        cleaned_response = self._clean_json_string(response)
        
        try:
            result = json.loads(cleaned_response)
            if self._validate_app_code_structure(result):
                return result
        except json.JSONDecodeError:
            pass
        
        json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                if self._validate_app_code_structure(result):
                    return result
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Could not extract valid JSON from response. Preview: {response[:300]}")

    def _clean_json_string(self, json_str: str) -> str:
        """Clean JSON string by escaping control characters."""
        import re

        def escape_control_chars(match):
            content = match.group(1)
            content = content.replace('\n', '\\n')
            content = content.replace('\r', '\\r')
            content = content.replace('\t', '\\t')
            content = content.replace('\b', '\\b')
            content = content.replace('\f', '\\f')
            content = re.sub(r'[\x00-\x1f\x7f]', lambda m: f'\\u{ord(m.group()):04x}', content)
            return f'"{content}"'
        
        return re.sub(r'"((?:[^"\\]|\\.)*)"', escape_control_chars, json_str)

    def _validate_app_code_structure(self, app_code: dict) -> bool:
        """Validate app code has required structure."""
        required_keys = ['html', 'css', 'js']
        
        if not isinstance(app_code, dict):
            return False
        
        missing_keys = [key for key in required_keys if key not in app_code]
        if missing_keys:
            print(f"Missing required keys: {missing_keys}")
            return False
        
        for key in required_keys:
            if not isinstance(app_code[key], str):
                print(f"Key '{key}' is not a string")
                return False
        
        return True

    def _create_domo_app(self, name: str, app_code: dict) -> Optional[str]:
        """Create app in Domo using generated code."""
        try:
            domo_client = _get_domo_client()
            template_id = "cf1da7bf-db6c-4170-bd7b-96b2a3f98bd8"
            version = "0.0.1"
            
            design_id = self._create_app_design(domo_client, template_id, name, version)
            self._update_app_files(domo_client, design_id, version, app_code, name)
            context_id = self._create_app_context(domo_client, name, design_id)
            self._create_card_from_app(domo_client, name, design_id, context_id)
            
            return self._get_app_url(domo_client, design_id)
            
        except Exception as e:
            print(f"Domo app creation error: {str(e)}")
            return None
    
    def _create_app_design(self, domo_client, template_id: str, name: str, version: str) -> str:
        """Create app design from template."""
        url = f"{_config['hostname']}/api/apps/v1/templates/{template_id}/design"
        payload = {"version": version, "name": name, "description": "Generated Custom App"}
        
        response = domo_client._post(url, payload)
        if response.status_code != 200:
            raise Exception(f"Design creation failed: {response.status_code}")
        
        return response.json()['id']
    
    def _update_app_files(self, domo_client, design_id: str, version: str, app_code: dict, name: str):
        """Update app files with generated code."""
        manifest_content = self._generate_manifest(design_id, name)
        
        file_mappings = [
            ('index.html', app_code.get('html', '')),
            ('app.js', app_code.get('js', '')),
            ('app.css', app_code.get('css', '')),
            ('manifest.json', manifest_content)
        ]
        
        content_types = {
            '.html': 'text/html',
            '.css': 'text/css', 
            '.js': 'application/javascript',
            '.json': 'application/json'
        }
        
        for file_name, content in file_mappings:
            if content and content.strip():
                url = f"{_config['hostname']}/api/apps/v1/designs/{design_id}/versions/{version}/assets?path={file_name}"
                
                file_ext = '.' + file_name.split('.')[-1]
                content_type = content_types.get(file_ext, 'text/plain')
                
                headers = {'Content-Type': content_type, 'Accept': 'application/json'}
                response = domo_client._post_data(url, content, headers)
                
                if response.status_code not in [200, 201, 204]:
                    raise Exception(f"File upload failed for {file_name}: {response.status_code}")
                    
                print(f"Successfully uploaded {file_name}")

    def _generate_manifest(self, design_id: str, name: str) -> str:
        """Generate manifest.json content."""
        import json
        
        manifest = {
            "id": design_id,
            "name": name,
            "version": "0.0.1",
            "fullpage": True,
            "datasetsMapping": [],
            "size": {"width": 5, "height": 5}
        }
        
        return json.dumps(manifest, indent=2)
    
    def _create_app_context(self, domo_client, name: str, design_id: str) -> str:
        """Create app context."""
        payload = {
            "datasetsMapping": [],
            "designId": design_id,
            "name": name,
            "size": {"width": 1, "height": 1},
            "version": "0.0.1"
        }
        
        url = f"{_config['hostname']}/domoapps/apps/v2/contexts"
        response = domo_client._post(url, payload)
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Context creation failed: {response.status_code}")
        
        return response.json()[0]['id']
    
    def _create_card_from_app(self, domo_client, name: str, design_id: str, context_id: str):
        """Create card instance from app."""
        url = f"{_config['hostname']}/domoapps/apps/v2?cardTitle={name}&pageId=-100000"
        payload = {"contextId": context_id, "designId": design_id}
        
        response = domo_client._post(url, payload)
        if response.status_code not in [200, 201]:
            raise Exception(f"Card creation failed: {response.status_code}")
    
    def _get_app_url(self, domo_client, design_id: str) -> str:
        """Get final app URL."""
        url = f"{_config['hostname']}/api/apps/v1/designs/{design_id}?parts=owners%2Ccards%2Cversions%2Ccreator"
        response = domo_client._get(url)
        
        if response.status_code != 200:
            raise Exception(f"App URL retrieval failed: {response.status_code}")
        
        app_data = response.json()
        
        if 'referencingCards' not in app_data or not app_data['referencingCards']:
            raise Exception("No referencing cards found")
        
        card_id = app_data['referencingCards'][0]['urn']
        return f"{_config['hostname']}/kpis/details/{card_id}"
        
# Global interface instances
llm    = _LLMInterface()
emails = _EmailsInterface()
data   = _DataInterface()
groups = _GroupsInterface()
forms  = _FormsInterface()
tasks  = _TasksInterface()
queues = _QueuesInterface()
web    = _WebInterface()
apps   = _AppsInterface()