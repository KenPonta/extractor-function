import os
from pathlib import Path

from openai import OpenAI

# Load OPENAI_API_KEY from .env if it isn't already in the environment.
env = Path(__file__).parent / ".env"
if env.exists() and not os.environ.get("OPENAI_API_KEY"):
    for line in env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

client = OpenAI()
resp = client.responses.create(
    model="gpt-4.1",
    input="Reply with exactly: OpenAI connection works.",
)
print(resp.output_text)
