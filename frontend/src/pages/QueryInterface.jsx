import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ArrowUp, ChevronDown, FileText, Info, Server, X } from 'lucide-react';
import { queryContract, getContracts } from '../api/client';
import PageHeader from '../components/PageHeader';
import Reveal from '../components/Reveal';
import BrandMark from '../components/BrandMark';

const sampleQuestions = [
  'What are the termination conditions?',
  'What is the governing law?',
  'Who are the parties involved?',
  'Are there any indemnification clauses?',
  'What are the payment terms?',
];

const cleanTitle = title => String(title || '').replace(/^#+\s*/, '').trim();

export default function QueryInterface() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const pickerRef = useRef(null);

  // Contract filter state
  const [contracts, setContracts] = useState([]);
  const [selectedContract, setSelectedContract] = useState(
    searchParams.get('contractId') || searchParams.get('contractTitle') || null
  );
  const [showContractPicker, setShowContractPicker] = useState(false);

  useEffect(() => {
    getContracts().then(data => setContracts(data)).catch(() => {});
  }, []);

  // Sync URL param → state
  useEffect(() => {
    setSelectedContract(searchParams.get('contractId') || searchParams.get('contractTitle') || null);
  }, [searchParams]);

  // Scroll the chat panel itself, never the page.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [messages, isTyping]);

  // Close the picker on outside click or Escape.
  useEffect(() => {
    if (!showContractPicker) return undefined;
    const onDown = event => { if (!pickerRef.current?.contains(event.target)) setShowContractPicker(false); };
    const onKey = event => { if (event.key === 'Escape') setShowContractPicker(false); };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [showContractPicker]);

  // Grow the textarea with its content, up to the CSS max-height.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);

  const selectedTitle = cleanTitle(contracts.find(c => c.contract_id === selectedContract)?.title)
    || (selectedContract && /^[a-f0-9]{64}$/.test(selectedContract) ? 'Selected contract' : selectedContract);

  const handleSelectContract = (contractId) => {
    setSelectedContract(contractId);
    setShowContractPicker(false);
    if (contractId) {
      setSearchParams({ contractId }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  };

  const handleClearContract = () => {
    setSelectedContract(null);
    setShowContractPicker(false);
    setSearchParams({}, { replace: true });
  };

  const handleSend = async (question) => {
    const textToSend = question || input;
    if (!textToSend.trim()) return;

    const userMsg = { id: Date.now(), role: 'user', content: textToSend, contract: selectedTitle };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await queryContract(textToSend, selectedContract);
      const aiMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.answer,
        sources: response.sources || [],
        cypher: response.cypher_query || '',
        evidence: response.relevance_score === 'relevant' ? 'Passed'
          : response.relevance_score === 'irrelevant' ? 'Insufficient' : 'Not assessed',
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'error',
        content: error.message || 'Failed to process query. Please try again.',
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="page">
      <PageHeader
        index="01"
        eyebrow="Ask"
        title="Ask the graph anything."
        description="Questions run across graph and semantic evidence. Every answer passes a relevance check and lists the clauses it used."
      />

      <section className="container-x pb-24 pt-8">
        <Reveal self y={40}>
          <div className="panel chat">
            {/* Contract scope */}
            <div className="panel__head">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="text-sm text-[var(--muted)]">Scope</span>
                {selectedContract ? (
                  <span className="chip chip--solid max-w-[min(26rem,70vw)]">
                    <FileText size={13} aria-hidden="true" className="flex-none" />
                    <span className="truncate">{selectedTitle}</span>
                    <button type="button" onClick={handleClearContract} className="-mr-1 grid place-items-center rounded p-0.5 hover:bg-white/15" aria-label="Clear contract filter">
                      <X size={13} aria-hidden="true" />
                    </button>
                  </span>
                ) : (
                  <span className="chip">All contracts</span>
                )}
              </div>
              <div ref={pickerRef} className="relative">
                <button
                  type="button"
                  className="chip"
                  aria-haspopup="listbox"
                  aria-expanded={showContractPicker}
                  onClick={() => setShowContractPicker(value => !value)}
                >
                  {selectedContract ? 'Change contract' : 'Choose a contract'}
                  <ChevronDown size={14} aria-hidden="true" className={`transition-transform duration-500 ${showContractPicker ? 'rotate-180' : ''}`} />
                </button>
                {showContractPicker && (
                  <div className="picker" role="listbox">
                    <button type="button" role="option" aria-selected={!selectedContract} onClick={() => handleSelectContract(null)}>
                      <div className="font-medium">All contracts</div>
                      <div className="mt-0.5 text-xs text-[var(--muted)]">Query across the whole knowledge graph</div>
                    </button>
                    {contracts.length === 0 ? (
                      <div className="px-4 py-6 text-center text-sm text-[var(--muted)]">No contracts uploaded yet</div>
                    ) : contracts.map(c => (
                      <button
                        type="button"
                        role="option"
                        key={c.contract_id}
                        aria-selected={selectedContract === c.contract_id}
                        onClick={() => handleSelectContract(c.contract_id)}
                      >
                        <div className="truncate font-medium">{cleanTitle(c.title)}</div>
                        {c.parties?.length > 0 && <div className="truncate text-xs text-[var(--muted)]">{c.parties.join(', ')}</div>}
                        <div className="mt-0.5 flex gap-3 text-xs text-[var(--muted)]">
                          {c.contract_type && <span>{c.contract_type}</span>}
                          {c.governing_law && <span>· {c.governing_law}</span>}
                          <span>· {c.clause_count || 0} clauses</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Conversation */}
            <div ref={scrollRef} className="chat__scroll" aria-live="polite">
              {messages.length === 0 ? (
                <div className="flex h-full flex-col items-start justify-end gap-8">
                  <BrandMark className="w-16 text-[var(--color-mint)]" strokeWidth={3} />
                  <div>
                    <h2 className="display-m max-w-[18ch]">
                      {selectedContract ? <>Ask about <span className="text-white">{selectedTitle}</span>.</> : 'Where would you like to start?'}
                    </h2>
                    <p className="text-body mt-4 max-w-xl">Pick a starting question or write your own. Shift + Enter adds a new line.</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {sampleQuestions.map(sq => (
                      <button key={sq} type="button" className="chip" onClick={() => { setInput(sq); inputRef.current?.focus(); }}>
                        {sq}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map(msg => (
                  <div key={msg.id} className={`chat__msg chat__msg--${msg.role}`}>
                    <div className="chat__bubble">
                      {msg.role === 'user' && msg.contract && (
                        <div className="mb-2 flex items-center gap-1.5 text-xs opacity-70">
                          <FileText size={12} aria-hidden="true" /> {msg.contract}
                        </div>
                      )}
                      <div className="whitespace-pre-wrap">{msg.content}</div>

                      {msg.role === 'assistant' && (
                        <div className="mt-5 space-y-4 border-t border-[var(--line)] pt-4">
                          {msg.sources?.length > 0 && (
                            <div>
                              <p className="eyebrow mb-3 mt-0">Sources cited</p>
                              <div className="grid gap-2">
                                {msg.sources.map((src, i) => (
                                  <div key={i} className="source">
                                    <span className="source__num">{src.clause_number || 'N/A'}</span>
                                    <span>{(src.clause_text || '').substring(0, 220)}{(src.clause_text || '').length > 220 ? '…' : ''}</span>
                                    {src.contract_title && <span className="source__title">{cleanTitle(src.contract_title)}</span>}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`chip ${msg.evidence === 'Passed' ? 'chip--solid' : 'chip--outline'}`}>Relevance check: {msg.evidence}</span>
                          </div>
                          {msg.cypher && (
                            <details className="group">
                              <summary className="inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-[var(--muted)] hover:text-[var(--fg)]">
                                <Server size={12} aria-hidden="true" /> View Cypher query
                              </summary>
                              <pre className="mono mt-2 overflow-x-auto bg-[var(--color-green-dark)] p-3 text-[var(--color-mint)]">{msg.cypher}</pre>
                            </details>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}

              {isTyping && (
                <div className="chat__msg chat__msg--assistant">
                  <div className="chat__bubble flex items-center gap-3 text-sm text-[var(--muted)]">
                    <span className="typing" aria-hidden="true"><i /><i /><i /></span>
                    Searching the graph{selectedContract ? ` in ${selectedTitle}` : ''} and checking evidence…
                  </div>
                </div>
              )}
            </div>

            {/* Composer */}
            <div className="chat__input">
              <label htmlFor="question" className="sr-only">Your question</label>
              <textarea
                id="question"
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder={selectedContract ? `Ask about "${selectedTitle}"…` : 'Ask a question about your contracts…'}
                className="chat__textarea"
                rows="1"
              />
              <button
                type="button"
                onClick={() => handleSend()}
                disabled={!input.trim() || isTyping}
                className="btn btn--icon-only"
                aria-label="Send question"
              >
                <span className="btn__bg" aria-hidden="true" />
                <ArrowUp size={18} aria-hidden="true" />
              </button>
            </div>
          </div>
        </Reveal>
        <p className="mt-4 flex items-center gap-2 text-sm text-[var(--muted)]">
          <Info size={14} aria-hidden="true" /> LexiGuard can make mistakes. Verify important legal information.
        </p>
      </section>
    </div>
  );
}
