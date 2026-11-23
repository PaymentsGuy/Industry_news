"""One tool-free call through the installed Hermes native Codex transport.

Run only through the Hermes bootstrap (not a general agent session). No prompt
builder, plugins, MCP, tools, memory, fallback chain or agent retry loop exists.
"""
import json
import sys
from urllib.parse import urlsplit

MODELS = {'gpt-6-luna', 'gpt-6.1-sol'}


def infer(model, messages, *, resolver=None, adapter=None):
    if model not in MODELS:
        raise ValueError('unapproved model')
    if resolver is None:
        from agent.auxiliary_client import resolve_provider_client, CodexAuxiliaryClient
        resolver, adapter = resolve_provider_client, CodexAuxiliaryClient
    raw, resolved = resolver('openai-codex', model=model, raw_codex=True)
    if raw is None or resolved != model:
        raise ValueError('Codex OAuth unavailable or model identity changed')
    # Never send subscription credentials to a configured relay or paid endpoint.
    endpoint = urlsplit(str(raw.base_url))
    if endpoint.scheme != 'https' or endpoint.netloc != 'chatgpt.com' or endpoint.path.rstrip('/') != '/backend-api/codex':
        raw.close()
        raise ValueError('non-subscription endpoint forbidden')
    client = adapter(raw.with_options(max_retries=0), model)
    try:
        response = client.chat.completions.create(
            model=model, messages=messages, tools=[], timeout=270,
            extra_body={'reasoning': {'effort': 'low'}},
        )
        if response.model != model or len(response.choices) != 1:
            raise ValueError('ambiguous model response')
        choice = response.choices[0]
        if choice.finish_reason != 'stop' or choice.message.tool_calls or not isinstance(choice.message.content, str):
            raise ValueError('tool call or incomplete response forbidden')
        return {'provider':'openai-codex', 'model':model, 'text':choice.message.content}
    finally:
        client.close()


def main():
    try:
        request = json.loads(sys.stdin.read(2_000_001))
        result = infer(request['model'], request['messages'])
    except Exception:
        # Never expose provider response, credentials, prompt or subprocess stderr.
        print('{"error":"codex_inference_failed"}')
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
