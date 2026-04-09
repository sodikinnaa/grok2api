# User Guide, Git Bash

## 1. Run the service on Windows

Use Git Bash to run the local server or to send API requests from Windows.

## 2. Test the API with curl

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-4",
    "messages": [{"role":"user","content":"Hello"}]
  }'
```

## 3. Notes

- Git Bash handles the line breaks above cleanly.
- If your shell does not expand environment variables, set `GROK2API_API_KEY` first.
