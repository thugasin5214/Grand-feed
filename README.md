# IntelFeed

A generic, pipeline-based intelligence feed system. Think of it as a configurable "daily briefing engine" — each pipeline is defined in YAML and runs independently.

## Features

- **Multiple Data Sources**: Reddit, Hacker News, NewsAPI (more coming)
- **Smart Processing**: Keyword filtering, deduplication, AI classification
- **Flexible Outputs**: Email digests, database storage
- **Pipeline-Based**: Define multiple independent pipelines with different configurations
- **AI-Powered**: Uses OpenRouter API for intelligent content classification
- **Automated**: GitHub Actions for daily runs

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Secrets

Copy the example secrets file and add your API keys:

```bash
cp config/secrets.yaml.example config/secrets.yaml
# Edit config/secrets.yaml with your API keys
```

Required API keys:
- **OpenRouter**: For AI classification (get from https://openrouter.ai)
- **Email**: Gmail app password for sending digests
- **NewsAPI** (optional): For news articles (get from https://newsapi.org)

### 3. Run a Pipeline

Run a specific pipeline:
```bash
python scripts/run_pipeline.py side-projects
```

Run all enabled pipelines:
```bash
python scripts/run_all.py
```

## Pipeline Configuration

Pipelines are defined in YAML files in the `pipelines/` directory. Each pipeline specifies:
- **Sources**: Where to collect data from
- **Processors**: How to filter and enrich the data
- **Outputs**: Where to send the results

### Example Pipeline

```yaml
name: "Side Project Radar"
enabled: true
schedule: "0 12 * * *"

sources:
  - type: reddit
    subreddits: [SideProject, startups]
    min_score: 5
    time_window_hours: 24
    
  - type: hackernews
    feeds: [askstories, showstories]
    max_items_per_feed: 100

processors:
  keyword_filter:
    enabled: true
    include: [pain point, launched, built]
    exclude: [hiring, resume]
    
  ai_classifier:
    enabled: true
    focus: "side projects and startup ideas"
    categories:
      pain_point: "User expressing frustration"
      idea: "Startup or side project idea"
      noise: "Off-topic"

outputs:
  - type: email
    to: "you@email.com"
    subject_template: "{name} - {date}"
    min_items: 1
```

## Available Components

### Collectors
- **reddit**: Reddit JSON API (no auth required)
- **hackernews**: HN Firebase API
- **newsapi**: NewsAPI.org (requires API key)
- **blind**: Professional network (stub, not implemented)

### Processors
- **keyword_filter**: Include/exclude by keywords
- **dedup**: Remove duplicates using SQLite
- **ai_classifier**: Classify with AI (OpenRouter)
- **sentiment**: Sentiment analysis (stub)

### Outputs
- **email**: HTML email digest via SMTP
- **database**: SQLite storage

## GitHub Actions

The project includes a GitHub Actions workflow for automated daily runs:

1. Fork this repository
2. Add secrets in GitHub Settings → Secrets:
   - `OPENROUTER_API_KEY`
   - `GMAIL_SENDER`
   - `GMAIL_PASSWORD`
   - `NEWSAPI_KEY` (optional)
3. Enable Actions in your fork
4. Pipelines will run daily at noon UTC

You can also trigger manually from the Actions tab.

## Project Structure

```
intel_feed/
├── core/              # Core pipeline framework
├── collectors/        # Data source collectors
├── processors/        # Data processors
├── outputs/          # Output handlers
├── templates/        # Email templates
├── models.py         # Data models
├── db.py            # Database operations
└── config.py        # Configuration loader

pipelines/            # Pipeline YAML configs
scripts/              # Runner scripts
config/               # Secrets configuration
data/                # SQLite database
```

## Development

### Adding a New Collector

1. Create a new file in `intel_feed/collectors/`
2. Inherit from `BaseCollector`
3. Implement the `collect()` method
4. Register with `@register_collector("name")`

### Adding a New Processor

1. Create a new file in `intel_feed/processors/`
2. Inherit from `BaseProcessor`
3. Implement the `process()` method
4. Register with `@register_processor("name")`

### Adding a New Output

1. Create a new file in `intel_feed/outputs/`
2. Inherit from `BaseOutput`
3. Implement the `send()` method
4. Register with `@register_output("name")`

## Environment Variables

As an alternative to `secrets.yaml`, you can use environment variables:

- `OPENROUTER_API_KEY`
- `GMAIL_SENDER`
- `GMAIL_PASSWORD`
- `NEWSAPI_KEY`
- `SMTP_HOST` (default: smtp.gmail.com)
- `SMTP_PORT` (default: 587)

## License

MIT

## Contributing

Pull requests are welcome! Please check existing issues or create a new one to discuss major changes.

## Roadmap

- [ ] More data sources (Twitter/X, RSS, LinkedIn)
- [ ] Slack/Discord outputs
- [ ] Web dashboard
- [ ] More AI processors (summarization, entity extraction)
- [ ] Scheduling improvements
- [ ] Multi-language support