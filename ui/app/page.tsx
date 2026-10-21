'use client';

import {useEffect, useState} from 'react';
import {CopilotKit, CopilotChat} from '@copilotkit/react-core/v2';
import '@copilotkit/react-core/v2/styles.css';

const storageKey = 'nis-assistant-thread';
const conversationId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function Page() {
  const [thread, setThread] = useState('');
  const [coverage, setCoverage] = useState('Checking prepared knowledge…');
  const [ready, setReady] = useState<boolean | null>(null);
  function newConversation() {
    const id = crypto.randomUUID();
    try { localStorage.setItem(storageKey, id); } catch { /* The session still works without storage. */ }
    setThread(id);
  }

  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved && conversationId.test(saved)) setThread(saved);
      else newConversation();
    } catch { newConversation(); }
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

  return <main>
    <header>
      <div className="brand"><span className="mark">n</span><div><strong>Nora Intelligence System</strong><small>Your knowledge assistant</small></div></div>
      <span className="privacy">Personal workspace</span>
    </header>
    <section className="intro">
      <span className="eyebrow">Prepared knowledge, in conversation</span>
      <h1>Ask your knowledge.</h1>
      <p>Find an answer, connect ideas, or pick up where you left off.</p>
      <div className="toolbar">
        <span role="status">{coverage}</span>
        <button onClick={newConversation}>New conversation</button>
      </div>
      {ready === false && <p className="notice">The knowledge service is unavailable. Your conversation will remain here while it reconnects.</p>}
    </section>
    <section className="chat" aria-label="Conversation">
      {thread && <CopilotKit key={thread} runtimeUrl="/api/copilotkit" agent="assistant" threadId={thread} useSingleEndpoint={false}>
        <CopilotChat agentId="assistant" threadId={thread} labels={{welcomeMessageText: 'What would you like to understand from your documents?'}} />
      </CopilotKit>}
    </section>
    <footer>Prepared knowledge reflects the documents you imported.</footer>
  </main>;
}
