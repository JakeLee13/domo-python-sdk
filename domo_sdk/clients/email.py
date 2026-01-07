"""
Email delivery client for Domo SDK.
"""

from typing import Union, List, Optional
from ..core import _get_domo_client, _config
class Email:
    """Email delivery client through Domo's Code Engine."""

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
        """
        Send email through Domo's Code Engine.

        Args:
            email: Recipient email address or list of addresses
            subject: Email subject line
            body: Email body content (HTML supported)
            attachments: Optional list of dataset IDs to attach

        Returns:
            True if email sent successfully, False otherwise
        """
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

    def send_to_group(self, group_id: Union[int, List[int]], subject: str, body: str,
                   attachments: Optional[List[int]] = None) -> bool:
        """
        Send email to a Domo group or groups.
        Args:
            group_id: Group ID or list of group IDs
            subject: Email subject line
            body: Email body content (HTML supported)
            attachments: Optional list of dataset IDs to attach
        Returns:
            True if email sent successfully, False otherwise
        """
        group_ids = [group_id] if isinstance(group_id, int) else group_id
        return self._call_function(
            "sendEmail",
            recipientEmails="", 
            subject=subject,
            body=body,
            personRecipients=[],
            groupRecipients=group_ids,  
            attachments=attachments or [],
            attachment=None,
            includeReplyAll=False
        )