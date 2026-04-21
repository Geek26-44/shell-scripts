#!/usr/bin/env python3
"""
Obsidian hourly log — reads memory files, summarizes via Gemma 9B, writes to Obsidian vault.
No OpenClaw dependency.
"""
import os, json, requests, glob, datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
OBSIDIAN_LOG_DIR = "/Users/geek2026/Documents/Obsidian-Vault/05_WORKING_MEMORY"
MEMORY_DIR = "/Users/geek2026/.openclaw/workspace/memory"
MODEL = "gemma2:9b-32k"

def get_recent_memory():
    """Read last 2 days of memory files."""
    files = sorted(glob.glob(os.path.join(MEMORY_DIR, "2026-*.md")), reverse=True)[:2]
    content = ""
    for f in files:
        try:
            with open(f) as fh:
                content += fh.read()[:3000]
        except:
            pass
    return content[:6000]

def summarize(content):
    """Ask Gemma to summarize recent activity."""
    prompt = f"""Summarize the following activity log into a brief Q&A format for Obsidian.
Keep it factual, concise. Use format:
### HH:MM — Topic
**Summary:** brief description

Activity log:
{content}

Summary:"""
    
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": 4096}
        }, timeout=60)
        if r.ok:
            return r.json().get("response", "").strip()
    except:
        pass
    return None

def main():
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    log_file = os.path.join(OBSIDIAN_LOG_DIR, f"DAILY_LOG_{date_str}.md")
    
    os.makedirs(OBSIDIAN_LOG_DIR, exist_ok=True)
    
    # Header if new file
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write(f"# {date_str} — Daily Log\n\n## Q&A\n\n")
    
    # Get summary
    memory = get_recent_memory()
    if not memory.strip():
        return
    
    summary = summarize(memory)
    if not summary:
        return
    
    # Append
    timestamp = now.strftime("%H:%M")
    with open(log_file, "a") as f:
        f.write(f"\n### {timestamp} — Auto Log\n")
        f.write(f"{summary}\n")
    
    print(f"Obsidian log updated: {timestamp}")

if __name__ == "__main__":
    main()
