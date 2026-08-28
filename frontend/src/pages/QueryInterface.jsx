import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Send, Search, Info, CheckCircle, Database, Server, RefreshCw, FileText, Filter, X } from 'lucide-react';
import { queryContract, getContracts } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';

const sampleQuestions = [
  "What are the termination conditions?",
  "What is the governing law?",
  "Who are the parties involved?",
  "Are there any indemnification clauses?",
  "What are the payment terms?"
];

export default function QueryInterface() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  // Contract filter state
  const [contracts, setContracts] = useState([]);
  const [selectedContract, setSelectedContract] = useState(
    searchParams.get('contractTitle') || null
  );
  const [showContractPicker, setShowContractPicker] = useState(false);

  // Fetch contracts for the selector
  useEffect(() => {
    getContracts()
      .then(data => {
        // Deduplicate by title
        const seen = new Map();
        data.forEach(c => {
          if (!seen.has(c.title)) seen.set(c.title, c);
        });
        setContracts(Array.from(seen.values()));
      })
      .catch(() => {});
  }, []);

  // Sync URL param → state on mount
  useEffect(() => {
    const title = searchParams.get('contractTitle');
    if (title) {
      setSelectedContract(title);
    }
  }, [searchParams]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSelectContract = (title) => {
    setSelectedContract(title);
    setShowContractPicker(false);
    // Update URL without navigation
    if (title) {
      setSearchParams({ contractTitle: title }, { replace: true });
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

    // Add user message
    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: textToSend,
      contract: selectedContract, // record which contract was queried
    };
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
        score: response.relevance_score === 'relevant' ? 0.95 : response.relevance_score === 'irrelevant' ? 0.3 : (typeof response.relevance_score === 'number' ? response.relevance_score : 0.5)
      };
      
      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      const errorMsg = {
        id: Date.now() + 1,
        role: 'error',
        content: error.message || "Failed to process query. Please try again."
      };
      setMessages(prev => [...prev, errorMsg]);
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
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-white/40 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/50 overflow-hidden">

      {/* Contract Filter Bar */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-white/50 bg-white/50 flex items-center gap-3">
        <Filter className="w-4 h-4 text-slate-500 flex-shrink-0" />
        {selectedContract ? (
          <div className="flex items-center gap-2 bg-slate-900/10 border border-slate-900/20 text-slate-800 text-sm px-3 py-1.5 rounded-lg font-medium">
            <FileText className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="truncate max-w-[300px]">{selectedContract}</span>
            <button
              onClick={handleClearContract}
              className="ml-1 p-0.5 hover:bg-slate-900/20 rounded transition-colors"
              title="Clear filter"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <span className="text-sm font-medium text-slate-600">All contracts</span>
        )}
        <div className="relative ml-auto">
          <button
            onClick={() => setShowContractPicker(!showContractPicker)}
            className="text-sm font-medium text-slate-700 hover:text-slate-900 bg-white/60 hover:bg-white/80 border border-white/60 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 shadow-sm"
          >
            <FileText className="w-3.5 h-3.5" />
            {selectedContract ? 'Change' : 'Select contract'}
          </button>

          {/* Dropdown */}
          {showContractPicker && (
            <div className="absolute right-0 top-full mt-2 w-80 max-h-72 overflow-y-auto bg-white/95 backdrop-blur-2xl border border-white/80 rounded-xl shadow-2xl z-50">
              {/* All Contracts option */}
              <button
                onClick={() => handleSelectContract(null)}
                className={`w-full text-left px-4 py-3 text-sm transition-colors border-b border-black/5 ${
                  !selectedContract
                    ? 'bg-slate-900/10 text-slate-900'
                    : 'text-slate-700 hover:bg-slate-50'
                }`}
              >
                <div className="font-semibold">All Contracts</div>
                <div className="text-xs text-slate-500 mt-0.5">Query across the entire knowledge graph</div>
              </button>

              {contracts.length === 0 ? (
                <div className="px-4 py-6 text-sm text-slate-500 text-center font-medium">
                  No contracts uploaded yet
                </div>
              ) : (
                contracts.map(c => (
                  <button
                    key={c.contract_id}
                    onClick={() => handleSelectContract(c.title)}
                    className={`w-full text-left px-4 py-3 text-sm transition-colors border-b border-black/5 last:border-0 ${
                      selectedContract === c.title
                        ? 'bg-slate-900/10 text-slate-900'
                        : 'text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    <div className="font-semibold truncate">{c.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5 flex gap-3">
                      {c.contract_type && <span>{c.contract_type}</span>}
                      {c.governing_law && <span>• {c.governing_law}</span>}
                      <span>• {c.clause_count || 0} clauses</span>
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Chat History */}
      <div className="flex-grow overflow-y-auto p-6 space-y-6 custom-scrollbar" onClick={() => setShowContractPicker(false)}>
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-6">
            <div className="bg-white/60 p-6 rounded-full border border-white/80 shadow-md">
               <Search className="w-12 h-12 text-slate-800" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2 drop-shadow-sm">LexiGuard Query Interface</h2>
              <p className="text-slate-700 font-medium max-w-md mx-auto">
                {selectedContract
                  ? <>Ask questions about <span className="text-slate-900 font-bold">{selectedContract}</span></>
                  : 'Ask complex legal questions across your entire contract repository using GraphRAG.'
                }
              </p>
            </div>
            
            <div className="flex flex-wrap justify-center gap-2 max-w-2xl mt-4">
              {sampleQuestions.map((sq, i) => (
                <button
                  key={i}
                  onClick={() => setInput(sq)}
                  className="bg-white/60 hover:bg-white/80 text-slate-800 font-medium text-sm py-2 px-4 rounded-full border border-white/80 hover:border-blue-400 shadow-sm transition-all"
                >
                  {sq}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-2xl p-5 shadow-lg ${
                msg.role === 'user' 
                  ? 'bg-slate-900 text-white rounded-br-none shadow-md' 
                  : msg.role === 'error'
                    ? 'bg-red-50 border border-red-200 text-red-800 rounded-bl-none'
                    : 'bg-white/70 border border-white/80 text-slate-900 rounded-bl-none backdrop-blur-md'
              }`}>
                
                {/* Contract context badge on user messages */}
                {msg.role === 'user' && msg.contract && (
                  <div className="text-xs text-slate-300 font-medium mb-2 flex items-center gap-1">
                    <Filter className="w-3 h-3" /> {msg.contract}
                  </div>
                )}

                {/* Message Content */}
                <div className="whitespace-pre-wrap leading-relaxed font-medium">
                  {msg.content}
                </div>

                {/* Assistant Extra Details */}
                {msg.role === 'assistant' && (
                  <div className="mt-4 pt-4 border-t border-black/10 space-y-4">
                    
                    {/* Sources */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div>
                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center">
                          <Database className="w-3 h-3 mr-1" /> Sources Cited
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {msg.sources.map((src, i) => (
                            <span key={i} className="text-xs font-medium bg-white/60 text-slate-800 px-2 py-1 rounded border border-black/5 flex items-center shadow-sm">
                              <FileText className="w-3 h-3 mr-1" /> {src.clause_number || 'N/A'}: {(src.clause_text || '').substring(0, 80)}...
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Metadata Badges */}
                    <div className="flex items-center space-x-3 text-xs font-semibold">
                       <span className="flex items-center text-slate-700 bg-slate-900/10 px-2 py-1 rounded border border-slate-900/20">
                         <CheckCircle className="w-3 h-3 mr-1" /> Relevance: {(msg.score * 100).toFixed(0)}%
                       </span>
                    </div>

                    {/* Cypher Toggle */}
                    {msg.cypher && (
                      <details className="group">
                        <summary className="text-xs font-bold text-slate-500 cursor-pointer hover:text-slate-700 flex items-center outline-none">
                          <Server className="w-3 h-3 mr-1" /> View Cypher Query
                        </summary>
                        <div className="mt-2 bg-slate-900/90 p-3 rounded-lg border border-slate-700 shadow-inner overflow-x-auto text-xs text-green-400 font-mono">
                          {msg.cypher}
                        </div>
                      </details>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-white/70 backdrop-blur-md border border-white/80 text-slate-600 rounded-2xl rounded-bl-none p-4 shadow-lg flex items-center space-x-3">
              <RefreshCw className="w-5 h-5 animate-spin text-slate-800" />
              <span className="text-sm font-semibold animate-pulse">
                Searching knowledge graph{selectedContract ? ` (${selectedContract})` : ''} & generating response...
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white/50 border-t border-white/50 backdrop-blur-md">
        <div className="relative flex items-center max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={
              selectedContract
                ? `Ask about "${selectedContract}"...`
                : "Ask a question about your contracts..."
            }
            className="w-full font-medium bg-white/70 text-slate-900 placeholder-slate-500 rounded-xl py-3 pl-4 pr-12 border border-white/80 focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 resize-none h-14 min-h-[56px] max-h-32 shadow-inner transition-all"
            rows="1"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isTyping}
            className="absolute right-2 p-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-400 text-white rounded-lg transition-colors shadow-sm"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
        <div className="text-center mt-2">
          <p className="text-xs font-medium text-slate-600 flex items-center justify-center">
            <Info className="w-3 h-3 mr-1" /> LexiGuard can make mistakes. Verify important legal information.
          </p>
        </div>
      </div>
    </div>
  );
}
