# Domo Automation SDK [In-Progress]

AI-powered automation toolkit for Domo.

## Installation

```bash
git clone https://github.com/JakeLee13/domo-automation-sdk
cd domo-automation-sdk
pip install -r requirements.txt
pip install -e .
```

## Quick Start

```python
from domo_sdk import *

# Authenticate
auth("your_dev_token", "your_client_id", "your_client_secret")

# Generate content using LLM
llm.prompt("What is cargo culting in the context of SaaS companies?")

# Simple variable subsitution
transcript = "Agent: Good morning! This is Sarah..."
llm.prompt(
    "Provide a recap of this call transcript: {transcript}", 
    transcript=transcript
)

# Process multiple prompts in parallel
prompts = ["What is Domo?",
           "What is PowerBI?",
           "What is Tableau?"]

results = llm.parallel(prompts, lambda prompt: llm.prompt(prompt))

# Create and send formatted emails
email_body = llm.prompt(
    "Create a market analysis email about Domo and its competitors",
    template="email"
)
emails.send(
    "team@company.com",        # recipient email
    "Market Analysis",         # subject
    email_body)                # body    

# Generate 
apps.create(
    "Sales Dashboard",
    "Beautiful modern SAAS dashboard with sales metrics, graphs, and insights"
)
```

**Setup Requirements:**
- Dev Token: `your-instance.domo.com/admin/security/accesstokens` -> Generate Access Token
- API Client: `your-instance.domo.com/admin/api-clients` -> Create

## API Reference

### AI Content Generation
```python
# Basic generation
result = llm.prompt("your prompt")

# With templates
email_html = llm.prompt("prompt", template="email")

# With variable substitution
result = llm.prompt("Analyze this: {data}", data=transcript)

# Parallel processing (3-5x faster)
results = llm.parallel(prompts, lambda p: llm.prompt(p), max_workers=4)
```

**Templates:** `email`, `app`

### Email Automation
```python
emails.send(
    email="user@domain.com",           # str or List[str]
    subject="Subject Line",            # str
    body="<html>...</html>",           # str (HTML)
)
```

### App Creation
```python
apps.create(
    name="Dashboard Name",             # str
    description="What the app does"    # str (detailed = better results)
)
```

### Data Management
```python
# Get dataset
df = data.get("dataset-id")

# Create dataset
dataset_id = data.create(dataframe, "Dataset Name")

# Replace/update dataset
data.replace("dataset-id", new_dataframe)
```

### User & Group Management
```python
# Groups
group = groups.create("Team Name", users=["user1", "user2"])
groups.add("group-id", ["user3", "user4"])
groups.remove("group-id", "user1")
```

### Tasks Automation
```python
# Create form
form = forms.create("Form Name", "Question?", placeholder="...")

# Create queue and tasks
queue = queues.create("Queue Name", "Description")
task = tasks.create("user-id", "form-id", "queue-id")

# Get responses
responses_df = tasks.responses("queue-id")
```

### Web Scraping
```python
# Scrape content
content = web.scrape("https://example.com")
```

## Requirements

- Python 3.7+
- Domo instance with API access
- Dependencies: `requests`, `beautifulsoup4`, `pandas`, `domojupyter`, `pydomo`
