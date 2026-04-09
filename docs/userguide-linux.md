# User Guide, Linux

## 1. Run the service

```bash
uv sync
uv run granian --interface asgi --host 0.0.0.0 --port 8000 --workers 1 main:app
```

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

## 3. If curl is not installed

```bash
sudo apt install curl
```
