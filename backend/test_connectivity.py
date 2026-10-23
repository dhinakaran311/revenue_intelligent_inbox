import json
import os
from pathlib import Path


def load_env():
    """Load .env and strip inline comments from values."""
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        print('ERROR: .env file not found')
        return {}
    env = {}
    for raw in env_path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, val = line.split('=', 1)
            val = val.split('#')[0].strip()   # strip inline comments
            env[key.strip()] = val
    return env


# ── 1. Supabase ────────────────────────────────────────────────────────────────
def test_supabase(env):
    print('\n[Supabase] testing ...')
    try:
        from supabase import create_client
        url = env.get('SUPABASE_URL', '')
        key = env.get('SUPABASE_SERVICE_ROLE_KEY', '')
        if not url or not key:
            return {'status': 'error', 'detail': 'Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY'}
        client = create_client(url, key)
        try:
            resp = client.table('source_records').select('source_type').limit(1).execute()
            return {'status': 'ok', 'rows': len(resp.data)}
        except Exception as inner:
            msg = str(inner)
            if any(x in msg for x in ('does not exist', 'relation', '404', '400')):
                return {'status': 'ok (table not yet created)', 'detail': msg[:150]}
            raise
    except ImportError:
        return {'status': 'error', 'detail': 'supabase package not installed'}
    except Exception as e:
        return {'status': 'error', 'detail': str(e)[:200]}


# ── 2. Pinecone (v3+ API) ──────────────────────────────────────────────────────
def test_pinecone(env):
    print('[Pinecone] testing ...')
    try:
        from pinecone import Pinecone
        api_key = env.get('PINECONE_API_KEY', '')
        if not api_key or api_key.startswith('YOUR_'):
            return {'status': 'skip', 'detail': 'PINECONE_API_KEY placeholder not replaced'}
        pc = Pinecone(api_key=api_key)
        indexes = list(pc.list_indexes().names())
        return {'status': 'ok', 'indexes': indexes}
    except ImportError:
        return {'status': 'error', 'detail': 'pinecone package not installed'}
    except Exception as e:
        return {'status': 'error', 'detail': str(e)[:200]}


# ── 3. Groq (official SDK, latest model) ──────────────────────────────────────
def test_groq(env):
    print('[Groq] testing ...')
    try:
        from groq import Groq
        api_key = env.get('GROQ_API_KEY', '')
        if not api_key:
            return {'status': 'error', 'detail': 'Missing GROQ_API_KEY'}
        client = Groq(api_key=api_key)
        model = env.get('GROQ_MODEL', 'openai/gpt-oss-120b')
        resp = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': 'Reply with exactly: OK'}],
            max_tokens=10,
            temperature=0.0,
        )
        reply = resp.choices[0].message.content.strip()
        return {'status': 'ok', 'model': model, 'reply': reply}
    except ImportError:
        return {'status': 'error', 'detail': 'groq package not installed'}
    except Exception as e:
        return {'status': 'error', 'detail': str(e)[:200]}


# ── 4. HuggingFace Sentence-Transformers ─────────────────────────────────────
def test_embedding(env):
    print('[Embedding] testing ...')
    try:
        hf_token = env.get('HF_TOKEN', '')
        if hf_token:
            os.environ['HF_TOKEN'] = hf_token
            os.environ['HUGGING_FACE_HUB_TOKEN'] = hf_token
        from sentence_transformers import SentenceTransformer
        raw = env.get('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
        model_name = raw.split('#')[0].strip()   # strip any leaked comment
        print(f'  Loading: {model_name}')
        model = SentenceTransformer(model_name)
        vec = model.encode(['Hello, Volopay Revenue Inbox.'])
        return {'status': 'ok', 'model': model_name, 'embedding_dim': int(vec.shape[1])}
    except ImportError:
        return {'status': 'error', 'detail': 'sentence-transformers package not installed'}
    except Exception as e:
        return {'status': 'error', 'detail': str(e)[:200]}


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    env = load_env()
    print('=== Volopay Revenue Inbox — Connectivity Test ===')
    report = {
        'supabase':  test_supabase(env),
        'pinecone':  test_pinecone(env),
        'groq':      test_groq(env),
        'embedding': test_embedding(env),
    }
    out = Path(__file__).parent / 'connectivity_report.json'
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('\n=== Results ===')
    for svc, result in report.items():
        status = result.get('status', '')
        icon = 'OK' if status.startswith('ok') else ('SKIP' if status == 'skip' else 'FAIL')
        print(f'  [{icon}]  {svc:12s}: {result}')
    print(f'\nFull report saved -> {out}')


if __name__ == '__main__':
    main()
