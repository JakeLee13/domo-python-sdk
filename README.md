# Domo Automation SDK

AI-powered automation toolkit for Domo operations within Domo's Jupyter Workspaces for LLM content generation, email delivery, data management, and custom app creation.

## Installation

Install directly from the canonical repo (no clone needed):

```bash
pip install git+https://github.com/domo-domosapiens/domo-python-sdk.git
# or with uv:
uv add git+https://github.com/domo-domosapiens/domo-python-sdk.git
```

For local development:

```bash
git clone https://github.com/domo-domosapiens/domo-python-sdk
cd domo-python-sdk
pip install -e ".[dev]"
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

# Process prompts in parallel
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

# Send to Domo groups
email.send_to_group(group_id=123, subject="Update", body="<html>...</html>")
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

### User Management
```python
# List all users
users_df = users.list_all(as_dataframe=True)

# Get specific user
user = users.get("user-id")

# Find users by email or name
user = users.find_by_email("john@company.com")
user = users.find_by_name("John Doe")

# Create, update, delete users
users.create({"name": "Jane", "email": "jane@co.com", "role": "Participant"})
users.update("user-id", {"title": "Manager"})
users.delete("user-id")
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

### Vector & Embeddings
```python
# Generate embeddings
embeddings = vector.embed(["text 1", "text 2", "text 3"])
single_embedding = vector.embed_single("some text")

# Similarity search
results = vector.search("query text", corpus_embeddings, top_k=5)
score = vector.similarity(embedding1, embedding2)

# VectorDB index management
vector.create_index("my-index")
vector.list_indexes()
vector.delete_index("my-index")

# Upsert and query vectors
vector.upsert("my-index", [{"content": "doc text", "type": "TEXT"}])
results = vector.query("my-index", input_text="search query", top_k=10)

# RAG pipeline helper
prompt, docs = vector.rag_pipeline("my-index", "user question", top_k=3)
```

### Cost Tracking

Every `llm.prompt()`, `llm.parallel()`, and `vector.embed()` call automatically accumulates **token usage and USD cost** into a thread-safe global counter. Cost comes from a bundled per-model rate table sourced from [Domo's AI model pricing page](https://www.domo.com/consumption-terms/ai-model-pricing). Notebooks running on Domo Automation can answer "what did this run cost?" without any per-call instrumentation.

```python
from domo_sdk import get_usage, reset_usage, track, flush_usage_to_dataset

# Always-on global accumulator
reset_usage()                          # zero the counter at start of a run
llm.prompt("Summarize this transcript: ...")
llm.parallel(items, lambda x: llm.prompt(f"Classify: {x}"))
print(get_usage())
# {'input_tokens': 12044, 'output_tokens': 3201, 'reasoning_tokens': 0,
#  'embedding_tokens_estimated': 0, 'total_tokens': 15245,
#  'chat_calls': 47, 'embedding_calls': 0, 'elapsed_seconds': 38.2,
#  'cost_usd': 0.10937, 'unknown_model_calls': 0, ...}

# Scoped tracking for a specific block
with track() as phase:
    llm.prompt("Step one")
    llm.prompt("Step two")
print(phase.chat_calls, phase.total_tokens, f"${phase.cost_usd:.4f}")
# 2, 184, $0.0036

# Persist to a Domo dataset for cross-run analysis
flush_usage_to_dataset(
    "abc123-def4-5678-90ab-cdef12345678",
    notebook_id="customer-churn-analysis",
    run_id=os.environ.get("DOMO_AUTOMATION_RUN_ID"),
)
```

#### How it works

**Chat tokens are exact.** The Domo AI chat endpoint (`/api/ai/v1/messages/chat`) returns a `modelProviderUsage` block on every response with `inputTokens`, `outputTokens`, and `reasoningTokens`. The SDK's `llm._call_api()` extracts these and forwards them to the global counter. Numbers come straight from the model provider — no estimation.

**Embedding tokens are estimated.** The Domo embedding endpoint (`/api/ai/v1/embedding/text`) does *not* return token counts (`modelProviderUsage` is null). The SDK estimates as `chars / 4`, which is a coarse model-agnostic approximation. Treat embedding totals as ±20% accurate — useful for trends, not for billing.

**The counter is global and process-local.** A single module-level `_Counter` (in `domo_sdk/usage.py`) accumulates across every chat and embedding call in the current Python process. It's thread-safe via a `threading.Lock`, so `llm.parallel()` workers don't race. Each notebook kernel has its own counter — use `notebook_id` / `run_id` on flush to disambiguate runs.

**Scoped tracking via `track()` is a snapshot-and-diff.** The context manager records the global counter on entry, computes the delta on exit, and exposes it on the context object. Tokens used inside the block are still counted in the global accumulator — `get_usage()` after the block sees them too.

**Dataset flush is read-modify-write.** The Domo data client doesn't expose a true append, so `flush_usage_to_dataset()` does `data.get → concat → data.replace`. Fine for once-per-notebook cost logging; concurrent flushes can race and lose rows. Don't call from inside a parallel loop.

#### How cost is calculated

`cost_usd` is computed per-call from token counts × per-model USD rates. The rates live in [domo_sdk/pricing.py](domo_sdk/pricing.py) as a Python dict, sourced from <https://www.domo.com/consumption-terms/ai-model-pricing>. The math:

```
cost = (input_tokens  / 1M) × input_rate    +
       (output_tokens / 1M) × output_rate   +
       (reasoning_tokens / 1M) × output_rate    # billed at output rate
```

Embedding calls route `embedding_tokens_estimated` to the input side (embedding models are input-only).

**Naming gotcha — three formats for the same model.** The API request takes `domo.domo_ai.domogpt-medium-v2.1` (dots), the response returns the same string with a `:anthropic` (or other provider) suffix appended, and the pricing page calls it `ai-pro-...-medium-v2_1-input` (underscores). The SDK keys its table on the request format and strips the response suffix before lookup via `pricing.normalize_model_id()`.

**Default model & current rate.** The SDK defaults to `domo.domo_ai.domogpt-medium-v2.1` ($3.90 input / $19.50 output per 1M tokens). All Anthropic-backed `domogpt-medium` versions (v1, v1.1, v1.2, v2, v2.1, v2.2) share these rates. Override per call via `llm.prompt(model="...")` or globally by mutating `_config['llm_settings']['model']`.

**Pricing table maintenance.** The bundled table is a snapshot — refresh it when Domo updates the pricing page. The module docstring records the snapshot date. A non-zero `unknown_model_calls` in `get_usage()` is a signal the table is missing entries; those calls contribute 0 to `cost_usd` so the total is conservative rather than inflated.

```python
from domo_sdk import pricing
pricing.calculate_cost_usd("domo.domo_ai.domogpt-medium-v2.1", input_tokens=1000, output_tokens=500)
# 0.0136 — i.e. $0.0136 for 1k in / 500 out on medium-v2.1
```

#### What's not tracked

- `vector.query(input_text=...)` — triggers an embedding call inside Domo's recall backend that doesn't surface to the SDK. Pre-embed via `vector.embed()` then pass `embedding=` if you need the cost visible.
- JSON-mode chat calls (`response_format=`) burn ~600+ extra input tokens per call due to system prompt injection. The accumulator captures this faithfully — not a bug, just expect inflated input counts.

See [agent-docs/cost-tracking.md](agent-docs/cost-tracking.md) for the dataset schema, per-model breakdown caveats, and future-improvement notes. See [agent-docs/ai-response-shape.md](agent-docs/ai-response-shape.md) for the captured Domo AI response shapes that drive the tracking. See [domo_sdk/pricing.py](domo_sdk/pricing.py) for the bundled pricing table.

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

- **Python 3.11+**
- **Domo instance** with API access
- **Dependencies**: Automatically installed by `pip install`
