# KeyBot-tg


forked from [v2ex](https://www.v2ex.com/t/1069084)

## Setup

First, [install uv](https://docs.astral.sh/uv/getting-started/installation/)

Once installed uv, run:

```bash
# Clone repo
git clone https://github.com/mokurin000/KeyBot-tg.git KeyBot-tg
cd KeyBot-tg
# Fill ADMIN_IDS, BOT_TOKEN, modify customer service account...
${EDITOR:-nano} src/keybot_tg/__main__.py

uv sync
uv pip install -e .
```

## Run

```bash
uv run python -m keybot_tg
```
