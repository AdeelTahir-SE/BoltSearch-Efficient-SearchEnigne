import { useCallback, useEffect, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { FaArrowRight, FaBolt, FaChevronDown, FaSearch, FaTimes, FaUpload } from 'react-icons/fa';
import './App.css';

const API = import.meta.env.VITE_API_URL || '/api';
const suggestions = ['machine learning', 'binary search', 'neural networks', 'data structures'];
function markup(body) {
  return `<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src https: data:;"><style>html{background:#121711;color-scheme:dark}body{background:#121711;font:15px/1.8 system-ui;color:#c5c9d3;margin:16px;overflow-wrap:anywhere}a{color:#b8f76b}pre,code{background:#20252a;border-radius:5px;white-space:pre-wrap}pre{padding:16px}img{max-width:100%}hr{border:0;border-top:1px solid #343b40}</style></head><body>${body}</body></html>`;
}
export default function App() {
  const [query, setQuery] = useState('');
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [limit, setLimit] = useState(10);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [resultLimit, setResultLimit] = useState(10);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [secret, setSecret] = useState(false);
  const [mode, setMode] = useState('search');
  const [answer, setAnswer] = useState(null);
  const [ragStatus, setRagStatus] = useState(null);
  const [statusError, setStatusError] = useState('');
  const [indexing, setIndexing] = useState(false);
  const input = useRef(null);
  const controller = useRef(null);
  const clicks = useRef(0);
  const closeUpload = useRef(null);
  const refreshStatus = useCallback(async (signal) => {
    try {
      const response = await fetch(`${API}/rag/status`, { signal });
      const status = await response.json();
      if (!response.ok) throw new Error(status.error || 'Could not connect to the knowledge index.');
      setRagStatus(status); setStatusError('');
    } catch (err) { if (err.name !== 'AbortError') setStatusError(err.message); }
  }, []);
  useEffect(() => {
    const request = new AbortController();
    refreshStatus(request.signal);
    return () => request.abort();
  }, [refreshStatus]);
  useEffect(() => {
    if (!ragStatus?.backgroundIndexing) return;
    const interval = setInterval(() => refreshStatus(), 15000);
    return () => clearInterval(interval);
  }, [ragStatus?.backgroundIndexing, refreshStatus]);
  useEffect(() => {
    let sequence = '';
    const handleKey = event => {
      const editing = /INPUT|TEXTAREA|SELECT/.test(event.target.tagName) || event.target.isContentEditable;
      if ((event.key === '/' && !editing) || ((event.metaKey || event.ctrlKey) && event.key === 'k')) { event.preventDefault(); input.current?.focus(); }
      if (event.key === 'Escape') setUploadOpen(false);
      if (!editing) { sequence = (sequence + event.key.toLowerCase()).slice(-35); if (sequence.endsWith('bolt') || sequence.endsWith('arrowuparrowuparrowdownarrowdown')) setSecret(value => !value); }
    };
    window.addEventListener('keydown', handleKey);
    return () => { window.removeEventListener('keydown', handleKey); controller.current?.abort(); };
  }, []);
  useEffect(() => {
    if (!uploadOpen) return;
    const previous = document.activeElement;
    closeUpload.current?.focus();
    const trap = event => {
      if (event.key !== 'Tab') return;
      const nodes = Array.from(document.querySelectorAll('.upload-modal button:not(:disabled), .upload-modal [tabindex="0"], .upload-modal input:not([tabindex="-1"])'));
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', trap);
    return () => { document.removeEventListener('keydown', trap); previous?.focus(); };
  }, [uploadOpen]);
  async function search(event, suggested, requestedPage = 1, requestedLimit = limit) {
    event?.preventDefault();
    const term = (suggested ?? query).trim();
    if (!term) { input.current?.focus(); return; }
    setQuery(term);
    if (term.toLowerCase() === '42') { setSecret(true); setNotice('The answer to life, the universe, and everything. Now find the question.'); }
    controller.current?.abort();
    const request = new AbortController(); controller.current = request;
    setLoading(true); setError(''); setExpanded(null); setAnswer(null); setDocuments([]);
    const start = performance.now();
    try {
      const response = mode === 'ask'
        ? await fetch(`${API}/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: term, limit: 6 }), signal: request.signal })
        : await fetch(`${API}/documents?${new URLSearchParams({ args: term, limit: requestedLimit, page: requestedPage })}`, { signal: request.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Search is unavailable. Please try again.');
      if (mode === 'ask') {
        if (typeof data.answer !== 'string' || !Array.isArray(data.sources)) throw new Error('The answer service returned an unexpected response.');
        setAnswer(data);
      } else {
        if (!Array.isArray(data)) throw new Error('The search service returned an unexpected response.');
        setDocuments(data); setPage(requestedPage); setResultLimit(requestedLimit); setHasMore(response.headers.get('X-Has-More') === 'true');
      }
      setSearched(term); setElapsed(performance.now() - start);
    } catch (err) { if (err.name !== 'AbortError') { setError(err.message); setDocuments([]); } }
    finally { if (!request.signal.aborted) setLoading(false); }
  }
  function changeMode(next) {
    if (next === mode) return;
    controller.current?.abort(); setLoading(false); setError('');
    setMode(next); setAnswer(null); setSearched(''); setDocuments([]); setExpanded(null);
  }
  async function buildSemanticIndex() {
    setIndexing(true); setError('');
    try {
      const response = await fetch(`${API}/rag/index`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Semantic indexing failed.');
      setNotice(data.pendingChunks ? `${data.embeddedChunks} of ${data.chunks} chunks ready. Continue indexing to finish.` : 'Your hybrid index is ready. Ask away.');
    } catch (err) { setError(err.message); } finally { await refreshStatus(); setIndexing(false); }
  }
  async function openSource(documentId) {
    try {
      const response = await fetch(`${API}/documents/${documentId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not open source document.');
      setDocuments([data]); setExpanded(0);
    } catch (err) { setError(err.message); }
  }
  const onDrop = useCallback((accepted, rejected) => {
    if (rejected.length) { setNotice('Choose one JSON file, up to 10 MB.'); return; }
    if (accepted[0]) { setFile(accepted[0]); setNotice(''); }
  }, []);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: { 'application/json': ['.json'] }, maxFiles: 1, maxSize: 10 * 1024 * 1024, disabled: uploading });
  async function upload() {
    if (!file || uploading) return;
    setUploading(true); setNotice('');
    try {
      const parsed = JSON.parse(await file.text());
      if (!Array.isArray(parsed) || !parsed.length || parsed.some(doc => !doc || !Number.isSafeInteger(doc.id) || doc.id < 0 || typeof doc.Title !== 'string')) throw new Error('Use a nonempty array of documents with a numeric id and a Title.');
      const body = new FormData(); body.append('file', file);
      const response = await fetch(`${API}/documents`, { method: 'POST', body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Upload failed. Please try again.');
      setNotice(`${data.indexed ?? 0} documents indexed; ${data.skipped ?? 0} existing documents skipped.`); setFile(null); setUploadOpen(false);
      await refreshStatus();
    } catch (err) { setNotice(err.message); } finally { setUploading(false); }
  }
  return <div className={`app ${secret ? 'supernova' : ''}`}>
    <div className="ambient" aria-hidden="true" />
    <header className="topbar"><a className="brand" href="#" aria-label="Bolt Search home" onClick={event => { event.preventDefault(); clicks.current += 1; if (clicks.current % 5 === 0) setSecret(value => !value); }}><span className="brand-mark"><FaBolt /></span>bolt<span className="brand-light">search</span><span className="beta">BETA</span></a><nav aria-label="Main navigation"><span className="nav-label">A little curiosity goes a long way.</span><button className="button secondary" onClick={() => setUploadOpen(true)}><FaUpload /> Add documents</button></nav></header>
    <main><section className={`hero ${searched ? 'compact' : ''}`} aria-labelledby="hero-title">
      <div className="eyebrow"><span className="status-dot" /> YOUR KNOWLEDGE. CONNECTED.</div>
      <h1 id="hero-title">Follow your curiosity.<br /><span>Find your next spark.</span><span className="spark" aria-hidden="true">✳</span></h1>
      <p className="hero-description">Big questions. Small details. That thing you almost remember.<br className="desktop-break" /> Search your documents and bring the right ideas to light.</p>
      <div className="mode-switch" role="group" aria-label="Search mode"><button aria-pressed={mode === 'search'} onClick={() => changeMode('search')}><FaSearch /> Search</button><button aria-pressed={mode === 'ask'} onClick={() => changeMode('ask')}><span aria-hidden="true">✳</span> Ask your knowledge</button></div>
      <form className="search-form" onSubmit={search} role="search"><div className="search-box"><FaSearch aria-hidden="true" /><input ref={input} aria-label={mode === 'ask' ? 'Ask your documents' : 'Search your documents'} value={query} maxLength={mode === 'ask' ? 2000 : 500} onChange={event => setQuery(event.target.value)} placeholder={mode === 'ask' ? 'Ask a question. Follow the sources.' : 'What are you curious about?'} /><kbd>/</kbd><button className="search-submit" type="submit" disabled={loading || !query.trim()}>{loading ? <span className="spinner" /> : <><span>{mode === 'ask' ? 'Ask' : 'Search'}</span><FaArrowRight /></>}</button></div><div className="search-options"><span><span className="tiny-bolt">ϟ</span> {mode === 'ask' ? 'Answers grounded in your documents' : 'Powered by your documents'}</span>{mode === 'search' && <label>Show <select value={limit} onChange={event => { const next = Number(event.target.value); setLimit(next); if (searched) search(null, searched, 1, next); }} aria-label="Result limit">{[5, 10, 20, 50, 100].map(value => <option key={value} value={value}>{value} results</option>)}</select></label>}</div></form>
      {mode === 'ask' && <div className="knowledge-status"><div className="knowledge-status-heading"><span className="status-dot" /><strong>{ragStatus?.chunks ? `${ragStatus.documents} documents in your orbit` : 'Build your knowledge orbit'}</strong>{ragStatus && <span className="retrieval-badge">{ragStatus.semanticConfigured && ragStatus.embeddedChunks > 0 ? ragStatus.pendingChunks ? 'HYBRID · PARTIAL' : 'HYBRID READY' : 'BM25 ONLY'}</span>}</div>{statusError ? <p role="status">{statusError} <button className="text-button" onClick={() => refreshStatus()}>Retry connection</button></p> : <p>{!ragStatus ? 'Connecting to your knowledge index…' : !ragStatus.answerConfigured ? 'Connect your Fireworks or Grok answer model in the server settings to start asking.' : !ragStatus.semanticConfigured ? 'Answer model connected. Configure an embedding model to add semantic retrieval alongside keyword search.' : ragStatus.pendingChunks ? `${ragStatus.embeddedChunks} of ${ragStatus.chunks} passages have semantic embeddings. Keyword search already covers all passages.` : ragStatus.chunks ? 'Keyword precision meets semantic understanding. Every answer links back to its sources.' : 'Add documents to give your questions somewhere to land.'}</p>}{ragStatus?.backgroundIndexing && <p role="status"><span className="spinner" /> Local indexing is running: {ragStatus.embeddedChunks.toLocaleString()} / {ragStatus.chunks.toLocaleString()} passages ready. Progress is saved automatically.</p>}{ragStatus?.semanticConfigured && ragStatus.pendingChunks > 0 && !ragStatus.backgroundIndexing && <button className="button secondary" disabled={indexing} onClick={buildSemanticIndex}>{indexing ? <><span className="spinner" /> Preparing passages…</> : <><FaBolt /> {ragStatus.embeddedChunks ? 'Continue semantic indexing' : 'Build semantic index'}</>}</button>}<span className="privacy-note">{ragStatus?.embeddingProvider === 'ollama' ? 'Passage embeddings stay on this computer with Ollama. Questions and selected excerpts go to your configured answer provider when you use Ask.' : 'Your question and retrieved excerpts go to the answer provider. Building the semantic index sends passages to your embedding provider.'}</span></div>}
      {!searched && mode === 'search' && <div className="suggestions"><span>A place to start</span>{suggestions.map(term => <button key={term} onClick={event => search(event, term)}>{term}<span>↗</span></button>)}</div>}
    </section>
    {error && <div className="message error" role="alert">{error}<span>Check that the search server and model settings are available.</span></div>}
    {notice && <div className="message" role="status">{notice}<button aria-label="Dismiss notification" onClick={() => setNotice('')}><FaTimes /></button></div>}
    {loading && <div className="results loading" role="status"><span className="spinner" /> {mode === 'ask' ? 'Connecting the dots and checking the sources…' : 'Looking for a spark in your documents…'}</div>}
    {!loading && searched && <section className="results" aria-label={mode === 'ask' ? 'Answer and sources' : 'Search results'} aria-live="polite"><div className="results-heading"><h2>{mode === 'ask' ? 'A spark of understanding' : documents.length ? 'Your discoveries' : 'Uncharted territory'}</h2><span>{mode === 'search' && `${documents.length} results · `}{(elapsed / 1000).toFixed(2)} seconds</span></div>
      {answer && <article className="answer-card"><div className="answer-heading"><span className="answer-spark" aria-hidden="true">✳</span><span>FROM YOUR KNOWLEDGE</span><span className="retrieval-badge">{answer.retrieval.mode === 'hybrid' ? 'BM25 + SEMANTIC' : 'BM25 ONLY'}</span></div><h3>{searched}</h3><div className="answer-text">{answer.answer.split(/(\[\d+\])/g).map((part, index) => { const source = answer.sources.find(item => `[${item.id}]` === part); return source ? <a className="citation" href={`#source-${source.id}`} aria-label={`Source ${source.id}: ${source.title}`} key={index}>{part}</a> : <span key={index}>{part}</span>; })}</div>{answer.status === 'answered' && <p className="answer-caveat">AI-generated with citations and matching source quotes. Check the evidence for context and correctness.</p>}{answer.retrieval.warnings.map((warning, index) => <p className="retrieval-warning" key={index}>{warning}</p>)}{answer.sources.length > 0 && <div className="source-list"><h4>{answer.status === 'answered' ? 'Follow the evidence' : 'Retrieved passages'}</h4>{answer.sources.map(source => <details className="source-card" id={`source-${source.id}`} key={source.id}><summary><span className="source-number">{source.id}</span><span>{source.title}<small>{source.section} · {source.methods.join(' + ')}</small></span><FaChevronDown /></summary><p>{source.text}</p>{answer.claims?.filter(claim => claim.source_id === source.id).map((claim, index) => <blockquote className="evidence-quote" key={index}><strong>Quoted evidence</strong><p>{claim.quote}</p></blockquote>)}<button className="text-button" onClick={() => openSource(source.documentId)}>Read full document <FaArrowRight /></button></details>)}</div>}</article>}
      {!documents.length && mode === 'search' && <div className="empty-state"><FaSearch /><h3>No matches for “{searched}”</h3><p>Try fewer words, a different phrase, or add documents to explore.</p><button className="button secondary" onClick={() => setUploadOpen(true)}>Add documents <FaArrowRight /></button></div>}
      {documents.map((doc, index) => <article className="result-card" key={doc.Id ?? index}><div className="result-meta"><span>DOCUMENT / {String((page - 1) * resultLimit + index + 1).padStart(2, '0')}</span>{doc.Score != null && <span>Score {doc.Score}</span>}</div><button className="result-title" aria-expanded={expanded === index} aria-controls={`document-${index}`} onClick={() => setExpanded(expanded === index ? null : index)}><h3>{doc.Title || 'Untitled document'}</h3><FaChevronDown className={expanded === index ? 'rotated' : ''} /></button>{doc.Tag && <p className="tags">{String(doc.Tag).replace(/></g, ' · ').replace(/[<>]/g, '')}</p>}{expanded === index && <div className="document-detail" id={`document-${index}`}><h4>Question</h4><iframe sandbox="" title={`Question: ${doc.Title || index + 1}`} srcDoc={markup(doc.Body || '<p>No question available.</p>')} />{doc.Answer?.trim() ? <><h4>Source answers</h4><iframe sandbox="" title={`Answers: ${doc.Title || index + 1}`} srcDoc={markup(String(doc.Answer).split(',,,,,').join('<hr>'))} /></> : <p className="source-answer-note">This source contains a question only. No answer was included in the imported dataset.</p>}</div>}</article>)}
      {mode === 'search' && (documents.length > 0 || page > 1) && <nav className="pagination" aria-label="Search results pages"><button className="button secondary" disabled={loading || page === 1} onClick={() => search(null, searched, page - 1, resultLimit)}>Previous</button><span aria-current="page">Page {page}</span><button className="button secondary" disabled={loading || !hasMore} onClick={() => search(null, searched, page + 1, resultLimit)}>Next <FaArrowRight /></button></nav>}
    </section>}
    {!searched && <section className="explore-section" aria-labelledby="explore-title"><div className="section-heading"><h2 id="explore-title">Less searching. More discovering.</h2><span>BUILT FOR THE CURIOUS</span></div><div className="feature-grid"><article className="feature"><div className="feature-icon">⌕</div><span className="feature-number">01 / DISCOVER</span><h3>Go straight to the good stuff.</h3><p>A dedicated document index connects your search to relevant questions and answers.</p><div className="mini-index" aria-hidden="true"><span /><span /><span /><i>↗</i></div></article><article className="feature"><div className="feature-icon">↗</div><span className="feature-number">02 / COLLECT</span><h3>Your knowledge, in one orbit.</h3><p>Bring your own JSON documents. Turn a collection of information into a place to explore.</p><button className="text-button" onClick={() => setUploadOpen(true)}>Add your first documents <FaArrowRight /></button></article><article className="feature feature-secret"><div className="feature-icon">✳</div><span className="feature-number">03 / WANDER</span><h3>Stay a little curious.</h3><p>The best discoveries aren’t always in the results. Some are hiding in plain sight.</p><span className="secret-caption">There’s more here than meets the eye.</span></article></div></section>}
    </main><footer><span className="footer-brand"><FaBolt /> Small spark. Big possibilities.</span><span>Made for curious minds <span className="footer-star" onDoubleClick={() => setSecret(value => !value)}>✳</span></span><span>© {new Date().getFullYear()} Bolt Search</span></footer>
    {secret && <div className="secret-toast" role="status"><FaBolt /> You found the current. Stay electric.<button aria-label="Close Easter egg" onClick={() => setSecret(false)}><FaTimes /></button></div>}
    {uploadOpen && <div className="modal-backdrop" onClick={event => { if (event.target === event.currentTarget && !uploading) setUploadOpen(false); }}><section className="upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title"><button ref={closeUpload} className="close-modal" aria-label="Close upload" onClick={() => setUploadOpen(false)}><FaTimes /></button><span className="eyebrow">EXPAND YOUR ORBIT</span><h2 id="upload-title">A new source of sparks.</h2><p>Add a JSON collection to your searchable knowledge.</p><div {...getRootProps({ className: `dropzone ${isDragActive ? 'dragging' : ''}` })}><input {...getInputProps()} aria-label="Choose JSON documents" /><FaUpload /><strong>{file ? file.name : isDragActive ? 'Drop it like it’s knowledge.' : 'Drop your JSON file here'}</strong><span>or click to browse · up to 10 MB</span></div><p className="file-hint">A JSON array with an integer <code>id</code> and <code>Title</code> for each document. Optional: Body, Answer, Tag, Score, CreationDate.</p>{notice && <p role="status" className="upload-notice">{notice}</p>}<button className="button primary upload-action" disabled={!file || uploading} onClick={upload}>{uploading ? <><span className="spinner" /> Indexing documents…</> : <>Add to my knowledge <FaArrowRight /></>}</button></section></div>}
  </div>;
}
