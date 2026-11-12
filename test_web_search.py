import asyncio, logging, sys
sys.path.insert(0, '.')

class FakeLogger:
    def info(self, *a, **k): print('[INFO]', *a)
    def warning(self, *a, **k): print('[WARN]', *a)
    def error(self, *a, **k): print('[ERR]', *a)
    def debug(self, *a, **k): pass

class FakeConfig:
    def get(self, key, default=None): return default

async def main():
    from src.tools.builtin.web_search_tool import WebSearchTool
    tool = WebSearchTool(FakeLogger(), FakeConfig())
    print('=== VALIDACAO ===')
    print('query vazia:', tool.validate({'query': ''}))
    print('query ok:', tool.validate({'query': 'Python asyncio'}))
    print()
    print('=== PESQUISA REAL ===')
    result = await tool.execute({'query': 'familia lenco fernandes', 'max_results': 3})
    print('success:', result.get('success'))
    print('count:', result.get('count'))
    print('provider:', result.get('provider'))
    print('fetched_at:', result.get('fetched_at'))
    for i, r in enumerate(result.get('results', []), 1):
        print(f'  [{i}] {r.get("title")}')
        print(f'      {r.get("url")}')
        print(f'      {r.get("snippet")[:120]}')
    if result.get('error'):
        print('ERRO:', result['error'])

asyncio.run(main())
