import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, FileText, Users, FileSignature, Share2, Sparkles, MessageSquare } from 'lucide-react';
import { getContracts, getGraphStats } from '../api/client';
import StatsCard from '../components/StatsCard';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Dashboard() {
  const [stats, setStats] = useState({ total_contracts: 0, total_parties: 0, total_clauses: 0, total_relationships: 0 });
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, contractsData] = await Promise.all([
          getGraphStats(),
          getContracts()
        ]);
        setStats(statsData);
        setContracts(contractsData);
      } catch (err) {
        setError('Failed to load dashboard data. Please make sure the backend is running.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Deduplicate contracts by title — keep the one with the most clauses
  const uniqueContracts = useMemo(() => {
    const seen = new Map();
    contracts.forEach(contract => {
      const title = contract.title;
      const existing = seen.get(title);
      if (!existing || (contract.clause_count || 0) > (existing.clause_count || 0)) {
        seen.set(title, contract);
      }
    });
    return Array.from(seen.values());
  }, [contracts]);

  if (loading) return <div className="flex justify-center items-center h-64"><LoadingSpinner text="Loading Dashboard..." /></div>;

  return (
    <div className="dashboard-page space-y-8">
      {/* Hero Section */}
      <section className="dashboard-hero text-center">
        <span className="hero-kicker"><Sparkles className="w-3.5 h-3.5" /> Legal intelligence, made clear</span>
        <h1>Understand every contract.<br /><span>Miss nothing important.</span></h1>
        <p>Search your complete legal knowledge graph and turn complex contract language into confident decisions.</p>
        <Link to="/query" className="hero-button">Ask a legal question <ArrowRight className="w-4 h-4" /></Link>
      </section>

      {error && (
        <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded-lg text-center">
          {error}
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard icon={<FileText className="w-6 h-6 text-blue-400" />} label="Unique Contracts" value={uniqueContracts.length} />
        <StatsCard icon={<Users className="w-6 h-6 text-green-400" />} label="Total Parties" value={stats.total_parties || 0} />
        <StatsCard icon={<FileSignature className="w-6 h-6 text-orange-400" />} label="Total Clauses" value={stats.total_clauses || 0} />
        <StatsCard icon={<Share2 className="w-6 h-6 text-purple-400" />} label="Total Relationships" value={stats.total_relationships || 0} />
      </div>

      {/* Contracts Grid */}
      <div className="repository-section">
        <div className="section-heading">
          <div>
            <span>Repository</span>
            <h2>Contracts at a glance</h2>
          </div>
          <Link to="/query" className="section-action">Explore knowledge graph <ArrowRight className="w-4 h-4" /></Link>
        </div>
        {uniqueContracts.length === 0 ? (
          <div className="empty-state">No contracts have been added to the repository yet.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {uniqueContracts.map(contract => (
              <div key={contract.contract_id} className="contract-card block h-full">
                <div className="h-full flex flex-col">
                  <span className="contract-eyebrow">{contract.contract_type || 'Contract'}</span>
                  <h3 className="text-lg font-semibold text-white mb-3 truncate" title={contract.title}>{contract.title}</h3>
                  <div className="text-sm text-slate-400 mb-5 space-y-2 flex-grow">
                    <p><span>Governing law</span> {contract.governing_law || 'Unknown'}</p>
                    {contract.parties && (
                       <p className="truncate"><span>Parties</span> {contract.parties.join(', ')}</p>
                    )}
                  </div>
                  <div className="mt-auto flex justify-between items-center text-xs text-slate-500 contract-footer">
                    <span>{contract.clause_count || 0} Clauses</span>
                    <div className="flex items-center gap-4">
                      <Link
                        to={`/query?contractTitle=${encodeURIComponent(contract.title)}`}
                        className="contract-link !text-purple-400 hover:!text-purple-300 transition-colors"
                      >
                        <MessageSquare className="w-3.5 h-3.5" /> Chat
                      </Link>
                      <Link
                        to={`/contract/${contract.contract_id}`}
                        className="contract-link"
                      >
                        Open contract <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
