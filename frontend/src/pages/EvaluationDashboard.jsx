import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Target, CheckCircle2, ShieldCheck, Info } from 'lucide-react';
import { getEvaluationResults } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';

const MetricCard = ({ title, score, icon, description }) => {
  let color = "text-green-500";
  let bg = "bg-green-500/10";
  let border = "border-green-500/20";
  
  if (score < 0.6) {
    color = "text-red-500";
    bg = "bg-red-500/10";
    border = "border-red-500/20";
  } else if (score < 0.8) {
    color = "text-yellow-500";
    bg = "bg-yellow-500/10";
    border = "border-yellow-500/20";
  }

  return (
    <div className={`rounded-xl p-6 border bg-slate-800 shadow-md ${border}`}>
      <div className="flex justify-between items-start mb-4">
        <div className={`p-3 rounded-lg ${bg}`}>
          {React.cloneElement(icon, { className: `w-6 h-6 ${color}` })}
        </div>
        <div className={`text-3xl font-bold ${color}`}>
          {(score * 100).toFixed(1)}%
        </div>
      </div>
      <h3 className="text-lg font-bold text-white mb-1">{title}</h3>
      <p className="text-sm text-slate-400">{description}</p>
    </div>
  );
};

export default function EvaluationDashboard() {
  const [evalData, setEvalData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const response = await getEvaluationResults();
        if (response && response.data) {
          setEvalData(response.data);
        } else {
          setEvalData([]);
        }
      } catch (err) {
        setError("Failed to load evaluation data.");
      } finally {
        setLoading(false);
      }
    };
    fetchResults();
  }, []);

  if (loading) {
    return <div className="flex justify-center items-center h-64"><LoadingSpinner text="Loading Evaluation Data..." /></div>;
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded-lg text-center">
        {error}
      </div>
    );
  }

  if (evalData.length === 0) {
    return (
      <div className="space-y-8">
        <div className="bg-slate-800 rounded-xl p-6 shadow-md border border-slate-700">
          <h1 className="text-2xl font-bold text-white mb-1">RAG Evaluation Metrics</h1>
          <p className="text-slate-400">Continuous evaluation of generation quality based on Ragas metrics.</p>
        </div>
        <div className="text-center py-20 bg-slate-800 rounded-xl border border-slate-700">
          <Info className="w-16 h-16 text-slate-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">No Evaluation Data Found</h2>
          <p className="text-slate-400 mb-6 max-w-lg mx-auto">
            You need to run the offline evaluation script to generate real ground-truth metrics.
          </p>
          <div className="bg-slate-900 border border-slate-700 p-4 rounded-lg max-w-md mx-auto text-left font-mono text-sm text-green-400">
            $ python scripts/05_run_evaluation.py
          </div>
        </div>
      </div>
    );
  }

  const avgFaithfulness = evalData.reduce((acc, curr) => acc + curr.faithfulness, 0) / evalData.length;
  const avgPrecision = evalData.reduce((acc, curr) => acc + curr.context_precision, 0) / evalData.length;
  const avgRelevancy = evalData.reduce((acc, curr) => acc + curr.answer_relevancy, 0) / evalData.length;

  return (
    <div className="space-y-8 pb-8">
      
      <div className="bg-slate-800 rounded-xl p-6 shadow-md border border-slate-700 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">RAG Evaluation Metrics</h1>
          <p className="text-slate-400">Continuous evaluation of generation quality based on Ragas metrics.</p>
        </div>
        <div className="text-sm text-green-400 bg-green-500/10 px-4 py-2 rounded-lg border border-green-500/20 flex items-center">
          <CheckCircle2 className="w-4 h-4 mr-2" /> Live Data
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard 
          title="Faithfulness" 
          score={avgFaithfulness} 
          icon={<ShieldCheck />}
          description="Measures factual consistency of the generated answer against the retrieved context."
        />
        <MetricCard 
          title="Context Precision" 
          score={avgPrecision} 
          icon={<Target />}
          description="Evaluates whether all ground-truth relevant items present in the contexts are ranked high."
        />
        <MetricCard 
          title="Answer Relevancy" 
          score={avgRelevancy} 
          icon={<CheckCircle2 />}
          description="Assesses how pertinent the generated answer is to the given prompt."
        />
      </div>

      {/* Chart Section */}
      <div className="bg-slate-800 rounded-xl p-6 shadow-xl border border-slate-700">
        <div className="flex items-center justify-between mb-8 border-b border-slate-700 pb-4">
          <h2 className="text-xl font-bold text-white">Performance Trends</h2>
          <span className="text-xs text-slate-400 bg-slate-900 px-3 py-1 rounded-full border border-slate-700">
            Evaluated on {evalData.length} Test Questions
          </span>
        </div>
        
        <div className="h-[450px] w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={evalData}
              margin={{ top: 10, right: 30, left: 0, bottom: 20 }}
            >
              <defs>
                <linearGradient id="colorFaithfulness" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorPrecision" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorRelevancy" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis 
                dataKey="question" 
                stroke="#64748b" 
                tick={{ fill: '#94a3b8', fontSize: 12 }} 
                tickMargin={12}
                axisLine={false}
                tickLine={false}
              />
              <YAxis 
                stroke="#64748b" 
                tick={{ fill: '#94a3b8', fontSize: 12 }} 
                domain={[0, 1]} 
                tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#f8fafc', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)' }}
                itemStyle={{ color: '#e2e8f0', fontWeight: '500', padding: '4px 0' }}
                labelStyle={{ color: '#94a3b8', marginBottom: '8px', borderBottom: '1px solid #334155', paddingBottom: '4px' }}
                formatter={(value) => [(value * 100).toFixed(1) + '%']}
                labelFormatter={(label) => {
                  const data = evalData.find(d => d.question === label);
                  return data ? data.full_question : label;
                }}
              />
              <Legend 
                verticalAlign="top" 
                height={36} 
                iconType="circle"
                wrapperStyle={{ paddingBottom: '20px', color: '#cbd5e1' }}
              />
              <Area 
                type="monotone" 
                dataKey="faithfulness" 
                name="Faithfulness" 
                stroke="#3b82f6" 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorFaithfulness)" 
                activeDot={{ r: 6, strokeWidth: 0, fill: '#3b82f6' }}
              />
              <Area 
                type="monotone" 
                dataKey="context_precision" 
                name="Context Precision" 
                stroke="#8b5cf6" 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorPrecision)" 
                activeDot={{ r: 6, strokeWidth: 0, fill: '#8b5cf6' }}
              />
              <Area 
                type="monotone" 
                dataKey="answer_relevancy" 
                name="Answer Relevancy" 
                stroke="#10b981" 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorRelevancy)" 
                activeDot={{ r: 6, strokeWidth: 0, fill: '#10b981' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
