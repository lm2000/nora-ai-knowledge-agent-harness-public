'use client';

import {useEffect, useState} from 'react';
import {CopilotKit, CopilotChat} from '@copilotkit/react-core/v2';
import '@copilotkit/react-core/v2/styles.css';

const ROLES = [
  {id: 'knowledge', label: 'Knowledge Assistant'},
  {id: 'research', label: 'Research Assistant'},
  {id: 'interview', label: 'Interview Analyst'},
] as const;
type Role = typeof ROLES[number]['id'];

type HistoryMessage = {id: string; role: 'user' | 'assistant'; content: string};

type ActiveTransfer = {role: Role; summary: string};

function storageKey(role: Role) {
  return `nora-thread-${role}`;
}

export default function Page() {
  const [role, setRole] = useState<Role | null>(null);
  const [thread, setThread] = useState('');
  const [coverage, setCoverage] = useState('Checking prepared knowledge…');
  const [ready, setReady] = useState<boolean | null>(null);
  const [transferOpen, setTransferOpen] = useState(false);
  const [historyMessages, setHistoryMessages] = useState<HistoryMessage[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [transferTarget, setTransferTarget] = useState<Role>('research');
  const [transferSummary, setTransferSummary] = useState('');
  const [activeTransfer, setActiveTransfer] = useState<ActiveTransfer | null>(null);

  function newConversation(selectedRole: Role) {
    const id = crypto.randomUUID();
    try { localStorage.setItem(storageKey(selectedRole), id); } catch { /* Session still works without browser storage. */ }
    setThread(id);
  }

  function switchRole(next: Role) {
    setRole(next);
    try {
      const saved = localStorage.getItem(storageKey(next));
      if (saved && /^[0-9a-f-]{36}$/i.test(saved)) {
        setThread(saved);
      } else {
        newConversation(next);
      }
    } catch {
      newConversation(next);
    }
    if (activeTransfer && activeTransfer.role !== next) {
      setActiveTransfer(null);
    }
  }

  useEffect(() => {
    let initial: Role = 'knowledge';
    try {
      const saved = localStorage.getItem('nora-role');
      if (saved && ROLES.some(r => r.id === saved)) initial = saved as Role;
    } catch { /* ignore */ }
    switchRole(initial);
    let active = true;
    const controller = new AbortController();
    async function checkStatus() {
      try {
        const response = await fetch('/api/status', {signal: controller.signal});
        const status = await response.json();
        if (active) { setCoverage(status.label); setReady(response.ok && status.ready); }
      } catch {
        if (active) { setCoverage('Nora is unavailable'); setReady(false); }
      }
    }
    void checkStatus();
    const timer = setInterval(checkStatus, 15000);
    return () => { active = false; controller.abort(); clearInterval(timer); };
  }, []);

  function onSelectRole(next: Role) {
    try { localStorage.setItem('nora-role', next); } catch { /* ignore */ }
    switchRole(next);
  }

  async function loadHistory() {
    if (!role || !thread) return;
    try {
      const response = await fetch(`/api/history/${role}/${thread}`);
      if (!response.ok) throw new Error('History unavailable');
      const data = await response.json() as {messages?: HistoryMessage[]};
      setHistoryMessages(data.messages || []);
      setSelectedIds(new Set());
    } catch {
      setHistoryMessages([]);
    }
  }

  function toggleSelected(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function previewTransfer() {
    if (!role || !thread || selectedIds.size === 0) return;
    const targetThread = crypto.randomUUID();
    try {
      const response = await fetch('/api/transfer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          source_role: role,
          source_thread_id: thread,
          target_role: transferTarget,
          target_thread_id: targetThread,
          message_ids: Array.from(selectedIds),
        }),
      });
      if (!response.ok) throw new Error(`Transfer preview failed: ${response.status}`);
      const data = await response.json() as {summary?: string};
      setTransferSummary(data.summary || '');
    } catch (error) {
      setTransferSummary(String(error));
    }
  }

  function openTargetChat() {
    if (!transferSummary || !transferTarget) return;
    setTransferOpen(false);
    setActiveTransfer({role: transferTarget, summary: transferSummary});
    onSelectRole(transferTarget);
  }

  if (!role) return null;

  return <main>
    <header>
      <div className="brand"><span className="mark">n</span><div><strong>Nora</strong><small>Your knowledge assistant</small></div></div>
      <span className="privacy">Personal workspace</span>
    </header>
    <section className="intro">
      <span className="eyebrow">Prepared knowledge, in conversation</span>
      <h1>Ask your knowledge.</h1>
      <p>Find an answer, connect ideas, or pick up where you left off.</p>
      <div className="toolbar">
        <select aria-label="Role" value={role} onChange={e => onSelectRole(e.target.value as Role)}>
          {ROLES.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
        </select>
        <span role="status">{coverage}</span>
        <button onClick={() => newConversation(role)}>New conversation</button>
        <button data-testid="transfer-toggle" onClick={() => setTransferOpen(o => !o)}>Transfer</button>
      </div>
      {ready === false && <p className="notice">The knowledge service is unavailable. Your conversation will remain here while it reconnects.</p>}
    </section>
    {transferOpen && <section className="transfer-panel" aria-label="Transfer conversation">
      <h2>Transfer selected context</h2>
      <button data-testid="transfer-load" onClick={loadHistory}>Load messages</button>
      <ul data-testid="transfer-message-list">
        {historyMessages.map(m => <li key={m.id}>
          <label>
            <input
              type="checkbox"
              data-testid={`transfer-select-${m.id}`}
              checked={selectedIds.has(m.id)}
              onChange={() => toggleSelected(m.id)}
            />
            {m.role}: {m.content.slice(0, 120)}{m.content.length > 120 ? '…' : ''}
          </label>
        </li>)}
      </ul>
      <select aria-label="Target role" value={transferTarget} onChange={e => setTransferTarget(e.target.value as Role)}>
        {ROLES.filter(r => r.id !== role).map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
      </select>
      <button data-testid="transfer-preview" onClick={previewTransfer} disabled={selectedIds.size === 0}>Preview transfer</button>
      {transferSummary && <>
        <textarea
          data-testid="transfer-summary"
          value={transferSummary}
          onChange={e => setTransferSummary(e.target.value)}
          rows={6}
          aria-label="Transfer summary"
        />
        <button data-testid="transfer-open-target" onClick={openTargetChat}>Open in {ROLES.find(r => r.id === transferTarget)?.label}</button>
      </>}
    </section>}
    {activeTransfer && activeTransfer.role === role && <div data-testid="transfer-banner" className="transfer-banner">
      <strong>Transferred context</strong>
      <pre>{activeTransfer.summary}</pre>
    </div>}
    <section className="chat" aria-label="Conversation">
      {thread && <CopilotKit key={`${role}-${thread}`} runtimeUrl={`/api/copilotkit/${role}`} agent={role} threadId={thread} useSingleEndpoint={false}>
        <CopilotChat agentId={role} threadId={thread} labels={{welcomeMessageText: 'What would you like to understand from your documents?'}} />
      </CopilotKit>}
    </section>
    <footer>Check important details against your documents. Prepared knowledge reflects the documents you imported.</footer>
  </main>;
}
