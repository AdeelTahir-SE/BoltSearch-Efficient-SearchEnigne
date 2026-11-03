"""OpenAI-compatible embeddings with independent provider configuration."""
import json
import os
import urllib.error
import urllib.request
from http.client import HTTPException
from urllib.parse import urlparse
from store import fingerprint, normalize


class TransientEmbeddingError(ValueError):
    """A temporary provider failure that an offline indexing job may retry."""


class Embeddings:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.provider = env.get('EMBEDDING_PROVIDER', 'openai').lower()
        if self.provider not in ('openai', 'ollama'):
            raise ValueError('EMBEDDING_PROVIDER must be openai or ollama.')
        self.key = '' if self.provider == 'ollama' else env.get('EMBEDDING_API_KEY') or env.get('FIREWORKS_API_KEY', '')
        self.base = env.get('EMBEDDING_BASE_URL') or ('http://127.0.0.1:11434' if self.provider == 'ollama' else 'https://api.fireworks.ai/inference/v1' if self.key and env.get('FIREWORKS_API_KEY') else '')
        self.base = self.base.rstrip('/')
        self.model = env.get('EMBEDDING_MODEL', '')
        self.query_prefix = env.get('EMBEDDING_QUERY_PREFIX', '')
        self.document_prefix = env.get('EMBEDDING_DOCUMENT_PREFIX', '')
        self.version = env.get('EMBEDDING_VERSION', '1')
        self.document_timeout = 120
        self.threads = int(env.get('OLLAMA_EMBEDDING_THREADS', '2')) if self.provider == 'ollama' else 2
        if not 1 <= self.threads <= 64:
            raise ValueError('OLLAMA_EMBEDDING_THREADS must be between 1 and 64.')
        self.configured = bool(self.base and self.model and (self.provider == 'ollama' or self.key))
        identity = [self.base, self.model, self.query_prefix, self.document_prefix, self.version]
        if self.provider == 'ollama':
            identity.insert(0, 'ollama')
        self.space = fingerprint(json.dumps(identity)) if self.configured else ''

    def embed(self, texts, query=False):
        if not self.configured:
            raise ValueError('Configure the embedding provider, endpoint, model and any required API key.')
        url = urlparse(self.base)
        if self.provider == 'ollama' and url.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('The local Ollama embedding provider must use a loopback address.')
        if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('Embedding endpoint must use HTTPS (HTTP is allowed on localhost).')
        prefix = self.query_prefix if query else self.document_prefix
        payload = {'model': self.model, 'input': [prefix + text for text in texts]}
        headers = {'Content-Type': 'application/json'}
        if self.provider == 'ollama':
            payload.update({'truncate': False, 'keep_alive': '10m', 'options': {'num_thread': self.threads}})
            endpoint = self.base + '/api/embed'
        else:
            payload['encoding_format'] = 'float'
            headers['Authorization'] = 'Bearer ' + self.key
            endpoint = self.base + '/embeddings'
        request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers=headers, method='POST')
        # Never forward credentials through a provider redirect.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=(60 if query else self.document_timeout) if self.provider == 'ollama' else 25) as response:
                body = response.read(8 * 1024 * 1024 + 1)
                if len(body) > 8 * 1024 * 1024:
                    raise ValueError('Embedding response is too large.')
                data = json.loads(body)
        except urllib.error.HTTPError as error:
            if error.code in (408, 429, 500, 502, 503, 504):
                raise TransientEmbeddingError(f'Embedding provider returned temporary HTTP {error.code}.') from None
            raise ValueError(f'Embedding provider returned HTTP {error.code}. Check model access and credentials.') from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, HTTPException):
            raise TransientEmbeddingError('Embedding provider is unavailable or timed out.') from None
        except json.JSONDecodeError:
            raise TransientEmbeddingError('Embedding provider returned malformed JSON; retry the request.') from None
        if self.provider == 'ollama':
            raw = data.get('embeddings') if isinstance(data, dict) else None
            if not isinstance(raw, list) or len(raw) != len(texts):
                raise ValueError('Ollama returned an invalid embedding count.')
            rows = [{'index': index, 'embedding': vector} for index, vector in enumerate(raw)]
        else:
            rows = data.get('data', []) if isinstance(data, dict) else []
        if not isinstance(rows, list) or any(not isinstance(row, dict) or type(row.get('index')) is not int for row in rows):
            raise ValueError('Embedding provider returned an invalid data array.')
        if len(rows) != len(texts) or sorted(row.get('index', -1) for row in rows) != list(range(len(texts))):
            raise ValueError('Embedding provider returned missing or invalid input indices.')
        vectors = [normalize(row.get('embedding')) for row in sorted(rows, key=lambda row: row['index'])]
        if len({len(vector) for vector in vectors}) != 1:
            raise ValueError('Embedding provider returned inconsistent dimensions.')
        return vectors
