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

Every `llm.prompt()`, `llm.parallel()`, and `vector.embed()` call automatically accumulates **token usage and USD cost** into a thread-safe global counter. Cost comes from hardcoded rates for the two models the SDK calls — sourced from [Domo's AI model pricing page](https://www.domo.com/consumption-terms/ai-model-pricing). Notebooks running on Domo Automation can answer "what did this run cost?" without any per-call instrumentation.

Two functions, one optional helper:

```python
from domo_sdk import auth, llm, cost

auth(...)
cost.start()                                         # reset counter at top of notebook

llm.prompt("Summarize this transcript: ...")
llm.parallel(items, lambda x: llm.prompt(f"Classify: {x}"))

cost.end(dataset_id="abc123-...", notebook_id="my-notebook")
# === my-notebook ===
#   47 chat calls, 0 embedding calls
#   12,044 input / 3,201 output tokens (15,245 total)
#   $0.10937 over 38.2s
#   flushed to dataset abc123-...
```

`cost.end()` always returns the row dict. Without `dataset_id` it just prints the summary — useful for local dev. With `dataset_id` it also appends a row to a Domo dataset for cross-run analysis. Pass `quiet=True` to suppress the print.

**Scoped per-phase cost** — when one notebook does multiple LLM passes (e.g. context-card pass + deal-scoring pass), wrap each in `cost.phase(...)`:

```python
cost.start()

with cost.phase("context cards"):
    llm.parallel(opps, build_context, max_workers=10)
# [phase: context cards] 47 chat / 0 embed, $0.0936, 12.4s

with cost.phase("deal scoring"):
    llm.parallel(deals, score, max_workers=10)
# [phase: deal scoring] 88 chat / 0 embed, $0.1742, 23.1s

cost.end(dataset_id="...", notebook_id="L2_deal_intelligence")  # cumulative across both
```

Phase blocks print on exit and expose the delta as a `Phase` object (`with cost.phase("...") as p: ...; print(p.cost_usd)`). Tokens inside still count toward the cumulative `cost.end()` total.

#### How it works

**Chat tokens are exact.** The Domo AI chat endpoint (`/api/ai/v1/messages/chat`) returns a `modelProviderUsage` block on every response with `inputTokens`, `outputTokens`, and `reasoningTokens`. The SDK's `llm._call_api()` extracts these and forwards them to a thread-safe global counter. Numbers come straight from the model provider — no estimation.

**Embedding tokens are estimated.** The Domo embedding endpoint (`/api/ai/v1/embedding/text`) does *not* return token counts (`modelProviderUsage` is null). The SDK estimates as `chars / 4`, which is a coarse model-agnostic approximation. Treat embedding totals as ±20% accurate — useful for trends, not for billing.

**Counter is global and process-local.** Each notebook kernel has its own counter; `llm.parallel()` workers don't race (the counter is locked). Use `notebook_id` / `run_id` on `cost.end()` to disambiguate runs in the cost dataset.

**Dataset flush is read-modify-write.** The Domo data client doesn't expose a true append, so `cost.end(dataset_id=...)` does `data.get → concat → data.replace`. Fine for once-per-notebook cost logging; concurrent flushes can race and lose rows. Don't call from inside a parallel loop.

#### How cost is calculated

The SDK only ever calls two models, so [domo_sdk/pricing.py](domo_sdk/pricing.py) hardcodes their rates as module-level constants — no lookup table, no model normalization. Sourced from <https://www.domo.com/consumption-terms/ai-model-pricing>; refresh the constants in `pricing.py` when Domo updates the page.

```python
CHAT_MODEL = "domo.domo_ai.domogpt-medium-v2.1"
CHAT_INPUT_USD_PER_M  = 3.90
CHAT_OUTPUT_USD_PER_M = 19.50    # also reasoning tokens

EMBEDDING_MODEL = "domo.domo_ai.domo-embed-text-multilingual-v1"
EMBEDDING_INPUT_USD_PER_M = 0.13
```

Per-call cost is `(input_tokens / 1M) × input_rate + (output_tokens / 1M) × output_rate`, dispatched on `surface == "chat"` vs `"embedding"` inside [usage.record_call](domo_sdk/usage.py).

```python
from domo_sdk import pricing
pricing.chat_cost_usd(input_tokens=1000, output_tokens=500)
# 0.013650 — $0.01365 for 1k in / 500 out
pricing.embedding_cost_usd(input_tokens=1000)
# 0.000130 — $0.000130 for 1k input tokens
```

**Defensive warning if the model changes.** Both `llm._call_api` and `vector.embed` check the response's `modelId` against the constants above. If something other than `medium-v2.1` (chat) or `domo-embed-text-multilingual-v1` (embedding) comes back, a `UserWarning` fires:

```
Unexpected chat model 'domo.domo_ai.domogpt-large-v2.2:anthropic' — cost calc
assumes domo.domo_ai.domogpt-medium-v2.1. Update domo_sdk/pricing.py if this is intentional.
```

This makes a config-side model switch fail loudly rather than silently miscount cost.

#### What's not tracked

- `vector.query(input_text=...)` — triggers an embedding call inside Domo's recall backend that doesn't surface to the SDK. Pre-embed via `vector.embed()` then pass `embedding=` if you need the cost visible.
- JSON-mode chat calls (`response_format=`) burn ~600+ extra input tokens per call due to system prompt injection. The accumulator captures this faithfully — not a bug, just expect inflated input counts.

See [agent-docs/cost-tracking.md](agent-docs/cost-tracking.md) for the dataset schema and limitations. See [agent-docs/ai-response-shape.md](agent-docs/ai-response-shape.md) for the captured Domo AI response shapes that drive the tracking. See [domo_sdk/pricing.py](domo_sdk/pricing.py) for the hardcoded rates.

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
