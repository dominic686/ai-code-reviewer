# AI Code Reviewer 🤖

An automated PR reviewer powered by Claude API that:
- Reviews code diffs and flags issues
- Detects unsafe patterns (hardcoded secrets, SQL injection, etc.)
- Blocks merges when policy is violated
- Posts structured review comments on PRs

## Setup

### Prerequisites
- Python 3.9+
- GitHub account
- Anthropic API key

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run lint
flake8 src/ tests/
```

## How It Works

1. A PR is opened or updated
2. GitHub Actions triggers the AI reviewer
3. The reviewer script fetches the diff and calls Claude API
4. Claude analyzes the diff against the policy rules
5. The bot posts a comment with findings
6. If issues are found, the PR check fails and merge is blocked

## Policy

Review rules are defined in `.agent/policy.yml`.

## Project Structure

```
├── .agent/          # Agent config (policy + prompt)
├── .github/         # GitHub Actions workflows
├── agent/           # Python reviewer script
├── src/             # Sample application code
└── tests/           # Test suite
```
