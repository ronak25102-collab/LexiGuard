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
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-slate-800 rounded-xl shadow-lg border border-slate-700 overflow-hidden">

      {/* Contract Filter Bar */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-slate-700 bg-slate-900/60 flex items-center gap-3">
        <Filter className="w-4 h-4 text-slate-400 flex-shrink-0" />
        {selectedContract ? (
          <div className="flex items-center gap-2 bg-purple-500/15 border border-purple-500/30 text-purple-300 text-sm px-3 py-1.5 rounded-lg">
            <FileText className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="truncate max-w-[300px]">{selectedContract}</span>
            <button
              onClick={handleClearContract}
              className="ml-1 p-0.5 hover:bg-purple-500/30 rounded transition-colors"
              title="Clear filter"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <span className="text-sm text-slate-400">All contracts</span>
        )}
        <div className="relative ml-auto">
          <button
            onClick={() => setShowContractPicker(!showContractPicker)}
            className="text-sm text-slate-300 hover:text-white bg-slate-700/60 hover:bg-slate-700 border border-slate-600 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
          >
            <FileText className="w-3.5 h-3.5" />
            {selectedContract ? 'Change' : 'Select contract'}
          </button>

          {/* Dropdown */}
          {showContractPicker && (
            <div className="absolute right-0 top-full mt-2 w-80 max-h-72 overflow-y-auto bg-slate-800 border border-slate-600 rounded-xl shadow-2xl z-50">
              {/* All Contracts option */}
              <button
                onClick={() => handleSelectContract(null)}
                className={`w-full text-left px-4 py-3 text-sm transition-colors border-b border-slate-700 ${
                  !selectedContract
                    ? 'bg-blue-500/15 text-blue-300'
                    : 'text-slate-300 hover:bg-slate-700/60'
                }`}
              >
                <div className="font-medium">All Contracts</div>
                <div className="text-xs text-slate-500 mt-0.5">Query across the entire knowledge graph</div>
              </button>

              {contracts.length === 0 ? (
                <div className="px-4 py-6 text-sm text-slate-500 text-center">
                  No contracts uploaded yet
                </div>
              ) : (
                contracts.map(c => (
                  <button
                    key={c.contract_id}
                    onClick={() => handleSelectContract(c.title)}
                    className={`w-full text-left px-4 py-3 text-sm transition-colors border-b border-slate-700/50 last:border-0 ${
                      selectedContract === c.title
                        ? 'bg-purple-500/15 text-purple-300'
                        : 'text-slate-300 hover:bg-slate-700/60'
                    }`}
                  >
                    <div className="font-medium truncate">{c.title}</div>
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
            <div className="bg-slate-900 p-6 rounded-full border border-slate-700 shadow-inner">
               <Search className="w-12 h-12 text-blue-500" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white mb-2">LexiGuard Query Interface</h2>
              <p className="text-slate-400 max-w-md mx-auto">
                {selectedContract
                  ? <>Ask questions about <span className="text-purple-400 font-medium">{selectedContract}</span></>
                  : 'Ask complex legal questions across your entire contract repository using GraphRAG.'
                }
              </p>
            </div>
            
            <div className="flex flex-wrap justify-center gap-2 max-w-2xl mt-4">
              {sampleQuestions.map((sq, i) => (
                <button
                  key={i}
                  onClick={() => setInput(sq)}
                  className="bg-slate-700/50 hover:bg-blue-600/30 text-slate-300 hover:text-blue-300 text-sm py-2 px-4 rounded-full border border-slate-600 hover:border-blue-500/50 transition-colors"
                >
                  {sq}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-2xl p-5 ${
                msg.role === 'user' 
                  ? 'bg-blue-600 text-white rounded-br-none shadow-md' 
                  : msg.role === 'error'
                    ? 'bg-red-900/50 border border-red-500/50 text-red-200 rounded-bl-none'
                    : 'bg-slate-900 border border-slate-700 text-slate-200 rounded-bl-none shadow-md'
              }`}>
                
                {/* Contract context badge on user messages */}
                {msg.role === 'user' && msg.contract && (
                  <div className="text-xs text-blue-200/60 mb-2 flex items-center gap-1">
                    <Filter className="w-3 h-3" /> {msg.contract}
                  </div>
                )}

                {/* Message Content */}
                <div className="whitespace-pre-wrap leading-relaxed">
                  {msg.content}
                </div>

                {/* Assistant Extra Details */}
                {msg.role === 'assistant' && (
                  <div className="mt-4 pt-4 border-t border-slate-700 space-y-4">
                    
                    {/* Sources */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center">
                          <Database className="w-3 h-3 mr-1" /> Sources Cited
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {msg.sources.map((src, i) => (
                            <span key={i} className="text-xs bg-slate-800 text-blue-300 px-2 py-1 rounded border border-slate-700 flex items-center">
                              <FileText className="w-3 h-3 mr-1" /> {src.clause_number || 'N/A'}: {(src.clause_text || '').substring(0, 80)}...
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Metadata Badges */}
                    <div className="flex items-center space-x-3 text-xs">
                       <span className="flex items-center text-green-400 bg-green-400/10 px-2 py-1 rounded">
                         <CheckCircle className="w-3 h-3 mr-1" /> Relevance: {(msg.score * 100).toFixed(0)}%
                       </span>
                    </div>

                    {/* Cypher Toggle */}
                    {msg.cypher && (
                      <details className="group">
                        <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-300 flex items-center outline-none">
                          <Server className="w-3 h-3 mr-1" /> View Cypher Query
                        </summary>
                        <div className="mt-2 bg-black/50 p-3 rounded border border-slate-700 overflow-x-auto text-xs text-green-400 font-mono">
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
            <div className="bg-slate-900 border border-slate-700 text-slate-400 rounded-2xl rounded-bl-none p-4 shadow-md flex items-center space-x-3">
              <RefreshCw className="w-5 h-5 animate-spin text-blue-500" />
              <span className="text-sm font-medium animate-pulse">
                Searching knowledge graph{selectedContract ? ` (${selectedContract})` : ''} & generating response...
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-slate-900 border-t border-slate-700">
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
            className="w-full bg-slate-800 text-white placeholder-slate-500 rounded-xl py-3 pl-4 pr-12 border border-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none h-14 min-h-[56px] max-h-32 shadow-inner"
            rows="1"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isTyping}
            className="absolute right-2 p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white rounded-lg transition-colors shadow-sm"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
        <div className="text-center mt-2">
          <p className="text-xs text-slate-500 flex items-center justify-center">
            <Info className="w-3 h-3 mr-1" /> LexiGuard can make mistakes. Verify important legal information.
          </p>
        </div>
      </div>
    </div>
  );
}
