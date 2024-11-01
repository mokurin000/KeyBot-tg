# KeyBot-tg


forked from [v2ex](https://www.v2ex.com/t/1069084)

## Setup

```bash
# Install micromamba
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)

# Create & activate environment
micromamba create -n keybot "python>=3.12,<3.13"
micromamba activate keybot

# Clone repo
git clone https://github.com/mokurin000/KeyBot-tg.git KeyBot-tg

# Fill ADMIN_IDS, BOT_TOKEN, modify customer service account...
${EDITOR:-nano} KeyBot-tg/src/keybot_tg/__main__.py

# Install keybot_tg
python -m pip install -e KeyBot-tg
```

## Run

```bash
micromamba activate keybot
python -m keybot_tg
```
