"""
AI-powered application generator client for Domo SDK.
"""

import json
import re
from typing import Optional

from ..core import _get_domo_client, _config


class Apps:
    """AI-powered application generator client."""
    
    def create(self, name: str, description: str, template_id: str = None, use_default_template: bool = True) -> Optional[str]:
        """
        Create complete Domo custom app with AI-generated code.
        
        Args:
            name: Application name
            description: Description of what the app should do (or complete template with instructions)
            template_id: Optional custom template ID (uses default if not provided)
            use_default_template: If False, bypasses the default app template and uses description as-is
            
        Returns:
            App URL if successful, None if failed
        """
        try:
            print(f"Creating app: {name}")
            
            app_code = self._generate_app_code(description, use_default_template)
            if not app_code:
                print("Failed to generate app code")
                return None
            
            app_url = self._create_domo_app(name, app_code, template_id)
            if not app_url:
                print("Failed to create app in Domo")
                return None
                
            print("App created successfully")
            print(f"App URL: {app_url}")
            return app_url
            
        except Exception as e:
            print(f"App creation failed: {str(e)}")
            return None
    
    def _generate_app_code(self, description: str, use_default_template: bool = True) -> Optional[dict]:
        """Generate HTML, CSS, and JS code using expert scaffold or custom template."""
        try:
            # Import here to avoid circular imports
            from .llm import LLM
            llm = LLM()
            
            if use_default_template:
                # Use the built-in app template
                code_response = llm.prompt(description, template="app")
            else:
                # Use description as-is (for custom templates like NEWS_FEED_TEMPLATE)
                code_response = llm.prompt(description)
                
            return self._parse_json_response(code_response)
        except Exception as e:
            print(f"Code generation error: {str(e)}")
            return None

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Parse JSON from LLM response with robust error handling."""
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

    def _create_domo_app(self, name: str, app_code: dict, template_id: str = None) -> Optional[str]:
        """Create app in Domo using generated code."""
        try:
            domo_client = _get_domo_client()
            # Allow custom template ID or use default
            template_id = template_id or "cf1da7bf-db6c-4170-bd7b-96b2a3f98bd8"
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
        manifest = {
            "id": design_id,
            "name": name,
            "version": "0.0.1",
            "fullpage": True,
            "datasetsMapping": [],
            "size": {"width": 10, "height": 10}
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