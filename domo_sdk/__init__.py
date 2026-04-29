"""
Domo Automation SDK

A unified automation toolkit for Domo operations, providing simple Python
interfaces for AI generation, email delivery, data management, user administration,
form creation, task management, web scraping, and custom app generation.

Example usage:
    from domo_sdk import auth, llm, email, data
    
    # Configure authentication
    auth(dev_token="your_token", 
         client_id="your_client_id", 
         client_secret="your_secret")
    
    # Generate AI content
    result = llm.prompt("Write a sales report summary")
    
    # Send email
    email.send("user@company.com", "Report", result)
    
    # Get dataset
    df = data.get("dataset_id_123")

"""

from .core import auth, get_config
from .clients import LLM, Email, Data, Groups, Forms, Tasks, Queues, Web, Apps, Users, Vector

from . import templates
from . import usage as _usage_module
from .usage import (
    get_usage,
    reset_usage,
    track,
    flush_to_dataset as flush_usage_to_dataset,
)

# Create global client instances
llm = LLM()
email = Email()  
data = Data()
groups = Groups()
forms = Forms()
tasks = Tasks()
queues = Queues()
web = Web()
apps = Apps()
users = Users()
vector = Vector()

__version__ = "0.2.0"

__all__ = [
    # Core functions
    "auth",
    "get_config",

    # Client instances
    "llm",
    "email",
    "data",
    "groups",
    "forms",
    "tasks",
    "queues",
    "web",
    "apps",
    "users",
    "vector",

    # Client classes
    "LLM",
    "Email",
    "Data",
    "Groups",
    "Forms",
    "Tasks",
    "Queues",
    "Web",
    "Apps",
    "Users",
    "Vector",

    # Templates module
    "templates",

    # Usage tracking (chat + embedding)
    "get_usage",
    "reset_usage",
    "track",
    "flush_usage_to_dataset",
]
