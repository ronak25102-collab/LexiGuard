import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, MapPin, ShieldAlert, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';
import { getContractDetail } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';

export default function ContractDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [contract, setContract] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedClauses, setExpandedClauses] = useState({});
  const graphRef = useRef();

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        const data = await getContractDetail(id);
        
        // The API returns { contract: {...}, parties: [...], clauses: [...] }
        // We need to merge them for the component to use `contract.title`, etc.
        const mergedContract = {
          ...data.contract,
          parties: data.parties ? data.parties.map(p => p.name) : [],
          clauses: data.clauses,
          governingLaw: data.contract.governing_law,
          effectiveDate: data.contract.effective_date,
        };
        
        setContract(mergedContract);
        
        // Ensure all clauses are collapsed by default
        const initialExpanded = {};
        if (mergedContract.clauses) {
          mergedContract.clauses.forEach((_, idx) => initialExpanded[idx] = false);
        }
        setExpandedClauses(initialExpanded);
      } catch (err) {
        setError('Failed to load contract details.');
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

  const toggleClause = (idx) => {
    setExpandedClauses(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  // Build mock graph data based on contract details for visualization
  const getGraphData = () => {
    if (!contract) return { nodes: [], links: [] };

    const nodes = [];
    const links = [];

    // Contract Node
    const contractNodeId = `Contract_${contract.id}`;
    nodes.push({ id: contractNodeId, name: contract.title, group: 'Contract', color: '#3b82f6', val: 20 });

    // Location/Law Node
    if (contract.governingLaw) {
      const lawId = `Law_${contract.governingLaw}`;
      nodes.push({ id: lawId, name: contract.governingLaw, group: 'Law', color: '#a855f7', val: 10 });
      links.push({ source: contractNodeId, target: lawId, name: 'GOVERNED_BY', color: '#475569' });
    }

    // Party Nodes
    if (contract.parties) {
      contract.parties.forEach((party, i) => {
        const partyId = `Party_${i}_${party}`;
        nodes.push({ id: partyId, name: party, group: 'Party', color: '#22c55e', val: 15 });
        links.push({ source: contractNodeId, target: partyId, name: 'HAS_PARTY', color: '#475569' });
      });
    }

    // Clause Nodes
    if (contract.clauses) {
      contract.clauses.forEach((clause, i) => {
        const clauseId = `Clause_${i}`;
        nodes.push({ id: clauseId, name: clause.title || `Clause ${i+1}`, group: 'Clause', color: '#f97316', val: 8 });
        links.push({ source: contractNodeId, target: clauseId, name: 'CONTAINS_CLAUSE', color: '#475569' });
        
        // Mock cross-references
        if (i > 0 && Math.random() > 0.8) {
           links.push({ source: clauseId, target: `Clause_${i-1}`, name: 'REFERENCES', color: '#ef4444', dashed: true });
        }
      });
    }

    return { nodes, links };
  };

  if (loading) return <div className="h-96 flex items-center justify-center"><LoadingSpinner text="Loading Contract..." /></div>;
  if (error) return <div className="text-red-500 text-center p-8 bg-white/40 backdrop-blur-xl rounded-xl">{error}</div>;
  if (!contract) return null;

  const graphData = getGraphData();

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="bg-white/40 backdrop-blur-xl rounded-xl p-6 shadow-md border border-white/50 flex-shrink-0">
        <button onClick={() => navigate(-1)} className="flex items-center text-slate-600 hover:text-slate-900 mb-4 transition-colors">
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Dashboard
        </button>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">{contract.title}</h1>
        <div className="flex flex-wrap gap-4 text-sm text-slate-700">
          <div className="flex items-center bg-white/60 px-3 py-1 rounded-full border border-white/50">
            <FileText className="w-4 h-4 mr-2 text-slate-700" /> {contract.type || 'Standard Contract'}
          </div>
          <div className="flex items-center bg-white/60 px-3 py-1 rounded-full border border-white/50">
            <MapPin className="w-4 h-4 mr-2 text-slate-700" /> {contract.governingLaw || 'Unspecified Jurisdiction'}
          </div>
          {contract.effectiveDate && (
             <div className="flex items-center bg-white/60 px-3 py-1 rounded-full border border-white/50">
               <ShieldAlert className="w-4 h-4 mr-2 text-slate-700" /> Effective: {contract.effectiveDate}
             </div>
          )}
        </div>
      </div>

      {/* Main Content: Two Columns */}
      <div className="flex flex-col lg:flex-row gap-6 flex-grow overflow-hidden">
        
        {/* Left Column: Graph */}
        <div className="lg:w-1/2 bg-white/40 backdrop-blur-xl rounded-xl shadow-md border border-white/50 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-white/50 bg-white/40 backdrop-blur-xl z-10 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-slate-900">Knowledge Graph View</h2>
            <div className="flex space-x-3 text-xs">
               <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-slate-700 mr-1"></span>Contract</span>
               <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-slate-500 mr-1"></span>Party</span>
               <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-orange-500 mr-1"></span>Clause</span>
               <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-purple-500 mr-1"></span>Law</span>
            </div>
          </div>
          <div className="flex-grow relative bg-white/60/50">
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              nodeLabel="name"
              nodeColor="color"
              nodeVal="val"
              linkColor="color"
              linkLineDash={link => link.dashed ? [4, 4] : null}
              linkDirectionalArrowLength={3.5}
              linkDirectionalArrowRelPos={1}
              width={800} // ideally resize observer based
              height={600}
              onEngineStop={() => graphRef.current?.zoomToFit(400, 20)}
              backgroundColor="#0f172a"
            />
          </div>
        </div>

        {/* Right Column: Clauses */}
        <div className="lg:w-1/2 bg-white/40 backdrop-blur-xl rounded-xl shadow-md border border-white/50 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-white/50 flex-shrink-0">
             <h2 className="text-lg font-semibold text-slate-900">Clauses ({contract.clauses?.length || 0})</h2>
          </div>
          <div className="flex-grow overflow-y-auto p-4 space-y-4 custom-scrollbar">
            {(!contract.clauses || contract.clauses.length === 0) ? (
              <p className="text-slate-600 text-center italic mt-10">No clauses found in this contract.</p>
            ) : (
              contract.clauses.map((clause, idx) => (
                <div key={idx} className="bg-white/60 border border-white/50 rounded-lg overflow-hidden transition-all duration-200">
                  <button 
                    onClick={() => toggleClause(idx)}
                    className="w-full text-left px-4 py-3 flex justify-between items-center hover:bg-white/50 focus:outline-none"
                  >
                    <span className="font-medium text-slate-800">{clause.title || `Section ${idx + 1}`}</span>
                    {expandedClauses[idx] ? <ChevronUp className="w-5 h-5 text-slate-500" /> : <ChevronDown className="w-5 h-5 text-slate-500" />}
                  </button>
                  {expandedClauses[idx] && (
                    <div className="px-4 pb-4 pt-2 text-sm text-slate-600 border-t border-slate-800 whitespace-pre-wrap leading-relaxed">
                      {clause.text}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
