# Domo Automation SDK

AI-powered automation toolkit for Domo operations with simple Python interfaces for content generation, email delivery, data management, and custom app creation.

## Installation

```bash
git clone https://github.com/JakeLee13/domo-automation-sdk
cd domo-automation-sdk
pip install .
```

## Quick Start

```python
from domo_sdk import auth, llm, email, data, apps

# Authenticate
auth("your_dev_token", "your_client_id", "your_client_secret")

# Generate content using AI
result = llm.prompt("What is cargo culting in the context of SaaS companies?")

# Simple variable substitution
transcript = "Agent: Good morning! This is Sarah..."
summary = llm.prompt(
    "Provide a recap of this call transcript: {transcript}", 
    transcript=transcript
)

# Process multiple prompts in parallel (3-5x faster)
prompts = ["What is Domo?", "What is PowerBI?", "What is Tableau?"]
results = llm.parallel(prompts, lambda prompt: llm.prompt(prompt))

# Create and send formatted emails with templates
email_body = llm.prompt(
    "Create a market analysis email about Domo and its competitors",
    template="email"  # Uses email template
)
email.send("team@company.com", "Market Analysis", email_body)

# Generate complete custom apps
apps.create(
    "Sales Dashboard",
    "Beautiful modern SaaS dashboard with sales metrics, graphs, and insights"
)

# Get and manipulate datasets
df = data.get("dataset_id_123")
```

## Setup Requirements

**Authentication Setup:**
- **Dev Token**: `your-instance.domo.com/admin/security/accesstokens` → Generate Access Token
- **API Client**: `your-instance.domo.com/admin/api-clients` → Create Client

**Environment Variables** (optional):
- `DOMO_HOSTNAME` - Your Domo instance hostname
- `DOMO_WORKSPACE_ID` - Default workspace ID  
- `DOMO_API_HOST` - API host (defaults to api.domo.com, use for dev/demo environments)

## API Reference

### AI Content Generation
```python
# Basic generation
result = llm.prompt("your prompt")

# With expert templates (email, app)
email_html = llm.prompt("Create a report summary", template="email")
app_code = llm.prompt("Build a sales dashboard", template="app")

# With variable substitution
result = llm.prompt("Analyze this: {data}", data=transcript)

# Parallel processing (3-5x faster for multiple prompts)
results = llm.parallel(prompts, lambda p: llm.prompt(p), max_workers=4)
```

**Available Templates:** `email`, `app`

### Email Automation
```python
email.send(
    email="user@domain.com",           # str or List[str] 
    subject="Subject Line",            # str
    body="<html>...</html>",           # str (HTML supported)
    attachments=[dataset_id]           # Optional List[int]
)
```

### Custom App Generation
```python
app_url = apps.create(
    name="Dashboard Name",             # str
    description="What the app does"    # str (detailed = better results)
)
# Returns URL to the created Domo app
```

### Data Management
```python
# Get dataset as DataFrame
df = data.get("dataset-id", use_schema=True)

# Create new dataset
dataset_id = data.create(dataframe, "Dataset Name", "Description")

# Replace existing dataset
data.replace("dataset-id", new_dataframe)

# Query dataset with SQL
results = data.query("dataset-id", "SELECT * FROM table WHERE...")
```

### User & Group Management
```python
# Create groups with users
group = groups.create("Team Name", users=["user1", "user2"], active=True)

# Manage group membership
groups.add("group-id", ["user3", "user4"])
groups.remove("group-id", "user1")
```

### Task & Form Automation
```python
# Create simple forms
form = forms.create("Feedback Form", "How was your experience?", 
                   placeholder="Enter feedback...", required=True)

# Create task queues
queue = queues.create("Review Queue", "Tasks for team review")

# Assign tasks to users
task = tasks.create("user-id", "form-id", "queue-id")

# Collect responses as DataFrame
responses_df = tasks.responses("queue-id")
```

### Web Scraping
```python
# Scrape full page content
content = web.scrape("https://example.com")

# Target specific elements with CSS selectors
titles = web.scrape("https://news.com", selector="h1.title")

# Custom configuration
content = web.scrape("https://example.com", 
                     selector=".content", 
                     timeout=30,
                     user_agent="Custom Bot 1.0")
```


## Requirements

- **Python 3.8+**
- **Domo instance** with API access
- **Dependencies**: Automatically installed via `pip install .`

## Advanced Usage

### Multiple Environments
```python
# Production
auth(prod_token, prod_id, prod_secret, hostname="prod.domo.com")

# Development  
auth(dev_token, dev_id, dev_secret, hostname="dev.domo.com")
```

### Configuration Debugging
```python
from domo_sdk import get_config
print(get_config())  # See current configuration
```

## License

MIT License
