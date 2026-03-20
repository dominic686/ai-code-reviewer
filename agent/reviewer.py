"""
AI Code Reviewer Agent
Fetches PR diff, sends to Claude API, posts review comment on GitHub.
"""
import os
import sys
import subprocess
import requests
import anthropic


# ── Config from environment variables (set by GitHub Actions) ──────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BOT_TOKEN         = os.environ.get("BOT_TOKEN")
PR_NUMBER         = os.environ.get("PR_NUMBER")
REPO_NAME         = os.environ.get("REPO_NAME")
BASE_SHA          = os.environ.get("BASE_SHA")
HEAD_SHA          = os.environ.get("HEAD_SHA")


# ── Step 1: Get the PR diff ─────────────────────────────────────────────────
def get_diff():
    """Get the code changes in this PR using git."""
    print("📂 Fetching PR diff...")
    result = subprocess.run(
        ["git", "diff", f"{BASE_SHA}..{HEAD_SHA}"],
        capture_output=True,
        text=True
    )
    diff = result.stdout

    if not diff:
        print("No diff found — nothing to review.")
        sys.exit(0)

    if len(diff) > 10000:
        diff = diff[:10000] + "\n... (diff truncated)"

    print(f"✅ Got diff ({len(diff)} characters)")
    return diff


# ── Step 2: Read policy and prompt files ────────────────────────────────────
def read_file(path):
    """Read a file and return its contents."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"⚠️  File not found: {path}")
        return ""


# ── Step 3: Call Claude API ─────────────────────────────────────────────────
def call_claude(diff, policy, prompt_template):
    """Send diff + policy + prompt to Claude and get review."""
    print("🤖 Calling Claude API...")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    full_prompt = f"""
{prompt_template}

## Policy Rules to Enforce:
{policy}

## Code Changes to Review (Git Diff):
```diff
{diff}
```

Please review the above code changes following the instructions
and policy rules. Provide your response in the exact format specified.
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[
            {"role": "user", "content": full_prompt}
        ]
    )

    review = response.content[0].text
    print("✅ Got review from Claude")
    return review


# ── Step 4: Parse verdict from Claude's response ────────────────────────────
def parse_verdict(review):
    """Extract PASS or FAIL from Claude's review."""
    if "### VERDICT" in review:
        verdict_section = review.split("### VERDICT")[1].strip()
        first_line = verdict_section.split("\n")[0].strip()
        if "FAIL" in first_line.upper():
            return "FAIL"
    return "PASS"


def parse_risk(review):
    """Extract risk level from Claude's review."""
    if "### RISK_LEVEL" in review:
        risk_section = review.split("### RISK_LEVEL")[1].strip()
        first_line = risk_section.split("\n")[0].strip()
        if "HIGH" in first_line.upper():
            return "HIGH"
        elif "MEDIUM" in first_line.upper():
            return "MEDIUM"
    return "LOW"


# ── Step 5: Post comment on GitHub PR ───────────────────────────────────────
def post_github_comment(review, verdict, risk):
    """Post the review as a comment on the GitHub PR."""
    print("💬 Posting comment to GitHub PR...")

    status_emoji = "✅" if verdict == "PASS" else "❌"
    status_text  = "PASSED" if verdict == "PASS" else "FAILED"
    risk_emoji   = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "🟢")

    comment = f"""## {status_emoji} AI Code Review — {status_text}

**Risk Level:** {risk_emoji} {risk}

---

{review}

---
*🤖 Reviewed by Claude AI | Policy: `.agent/policy.yml`*
"""

    url = f"https://api.github.com/repos/{REPO_NAME}/issues/{PR_NUMBER}/comments"
    headers = {
        "Authorization": f"token {BOT_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.post(url, headers=headers, json={"body": comment})

    if response.status_code == 201:
        print("✅ Comment posted successfully")
    else:
        print(f"⚠️  Failed to post comment: {response.status_code}")
        print(response.text)


# ── Step 6: Set GitHub check status ─────────────────────────────────────────
def set_check_status(verdict):
    """Set the PR check to pass or fail — this blocks/allows merge."""
    print(f"🚦 Setting check status to: {verdict}")

    state       = "success" if verdict == "PASS" else "failure"
    description = "AI review passed" if verdict == "PASS" \
        else "AI review failed — fix issues before merging"

    url = f"https://api.github.com/repos/{REPO_NAME}/statuses/{HEAD_SHA}"
    headers = {
        "Authorization": f"token {BOT_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "state":       state,
        "description": description,
        "context":     "AI Review Gate"
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 201:
        print(f"✅ Check status set to: {state}")
    else:
        print(f"⚠️  Failed to set status: {response.status_code}")
        print(response.text)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("🚀 AI Code Reviewer starting...")
    print(f"   Repo:      {REPO_NAME}")
    print(f"   PR Number: #{PR_NUMBER}")
    print(f"   Base SHA:  {BASE_SHA[:7] if BASE_SHA else 'N/A'}")
    print(f"   Head SHA:  {HEAD_SHA[:7] if HEAD_SHA else 'N/A'}")
    print()

    diff            = get_diff()
    policy          = read_file(".agent/policy.yml")
    prompt_template = read_file(".agent/reviewer_prompt.md")

    review  = call_claude(diff, policy, prompt_template)
    verdict = parse_verdict(review)
    risk    = parse_risk(review)

    print(f"\n📊 Results:")
    print(f"   Verdict: {verdict}")
    print(f"   Risk:    {risk}")

    post_github_comment(review, verdict, risk)
    set_check_status(verdict)

    if verdict == "FAIL":
        print("\n❌ Review FAILED — PR should be blocked")
        sys.exit(1)
    else:
        print("\n✅ Review PASSED — PR can be merged")
        sys.exit(0)


if __name__ == "__main__":
    main()