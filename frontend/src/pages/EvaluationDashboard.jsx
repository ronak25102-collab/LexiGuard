import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Target, CheckCircle2, ShieldCheck, Info } from 'lucide-react';
import { getEvaluationResults } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';

const MetricCard = ({ title, score, icon, description }) => {
  let color = "text-slate-800";
  let bg = "bg-slate-900/10";
  let border = "border-slate-900/20";
  
  if (score < 0.6) {
    color = "text-red-600";
    bg = "bg-red-500/15";
    border = "border-red-500/30";
  } else if (score < 0.8) {
    color = "text-slate-700";
    bg = "bg-slate-900/5";
    border = "border-amber-500/30";
  }

  return (
    <div className={`rounded-2xl p-6 border bg-white/40 backdrop-blur-xl shadow-lg border-white/60 transition-transform hover:-translate-y-1`}>
      <div className="flex justify-between items-start mb-4">
        <div className={`p-3 rounded-xl border ${bg} ${border}`}>
          {React.cloneElement(icon, { className: `w-6 h-6 ${color}` })}
        </div>
        <div className={`text-3xl font-extrabold ${color} drop-shadow-sm`}>
          {(score * 100).toFixed(1)}%
        </div>
      </div>
      <h3 className="text-lg font-bold text-slate-900 mb-1">{title}</h3>
      <p className="text-sm font-medium text-slate-600">{description}</p>
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
      <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl text-center shadow-sm font-medium">
        {error}
      </div>
    );
  }

  if (evalData.length === 0) {
    return (
      <div className="space-y-8">
        <div className="bg-white/40 backdrop-blur-xl rounded-2xl p-6 shadow-lg border border-white/60">
          <h1 className="text-2xl font-extrabold text-slate-900 mb-1 drop-shadow-sm">RAG Evaluation Metrics</h1>
          <p className="text-slate-700 font-medium">Continuous evaluation of generation quality based on Ragas metrics.</p>
        </div>
        <div className="text-center py-20 bg-white/40 backdrop-blur-xl rounded-2xl shadow-lg border border-white/60">
          <Info className="w-16 h-16 text-slate-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">No Evaluation Data Found</h2>
          <p className="text-slate-600 font-medium mb-6 max-w-lg mx-auto">
            You need to run the offline evaluation script to generate real ground-truth metrics.
          </p>
          <div className="bg-white/50 border border-slate-900/10 p-4 rounded-xl max-w-md mx-auto text-left font-mono text-sm text-slate-700 shadow-inner">
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
      
      <div className="bg-white/40 backdrop-blur-xl rounded-2xl p-6 shadow-lg border border-white/60 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 mb-1 drop-shadow-sm">RAG Evaluation Metrics</h1>
          <p className="text-slate-700 font-medium">Continuous evaluation of generation quality based on Ragas metrics.</p>
        </div>
        <div className="text-sm font-bold text-slate-800 bg-slate-900/10 px-4 py-2 rounded-xl border border-slate-900/20 flex items-center shadow-sm">
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
      <div className="bg-white/50 backdrop-blur-2xl rounded-2xl p-6 shadow-2xl border border-white/80">
        <div className="flex items-center justify-between mb-8 border-b border-white/50 pb-4">
          <h2 className="text-xl font-extrabold text-slate-900 drop-shadow-sm">Performance Trends</h2>
          <span className="text-xs font-bold text-slate-700 bg-white/70 px-4 py-1.5 rounded-full border border-white/80 shadow-sm">
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
                  <stop offset="5%" stopColor="#334155" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#334155" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorPrecision" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563eb" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorRelevancy" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0d9488" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#0d9488" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" vertical={false} />
              <XAxis 
                dataKey="question" 
                stroke="#64748b" 
                tickFormatter={(val) => `Q${val.split('-')[1]}`} 
                tick={{ fontSize: 12, fill: '#64748b' }} 
                tickMargin={12}
              />
              <YAxis 
                stroke="#64748b" 
                tickFormatter={(val) => `${val * 100}%`}
                domain={[0, 1]} 
                tick={{ fontSize: 12, fill: '#64748b' }}
                tickMargin={12}
                axisLine={false}
                tickLine={false}
              />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'rgba(255, 255, 255, 0.95)', backdropFilter: 'blur(12px)', borderColor: '#e2e8f0', borderRadius: '12px', color: '#0f172a', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)' }}
                  itemStyle={{ color: '#0f172a', fontWeight: '700', padding: '6px 0' }}
                  labelStyle={{ color: '#475569', fontWeight: '600', marginBottom: '8px', borderBottom: '1px solid #cbd5e1', paddingBottom: '6px' }}
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
                wrapperStyle={{ paddingBottom: '20px', color: '#334155', fontWeight: '600' }}
              />
              <Area 
                type="monotone" 
                dataKey="faithfulness" 
                name="Faithfulness" 
                stroke="#334155" 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorFaithfulness)" 
                activeDot={{ r: 6, strokeWidth: 0, fill: '#334155' }}
              />
              <Area 
                type="monotone" 
                dataKey="context_precision" 
                name="Context Precision" 
                stroke="#2563eb" 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorPrecision)" 
                activeDot={{ r: 6, strokeWidth: 0, fill: '#2563eb' }}
              />
              <Area 
                type="monotone" 
                dataKey="answer_relevancy" 
                name="Answer Relevancy" 
                stroke="#0d9488" 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorRelevancy)" 
                activeDot={{ r: 6, strokeWidth: 0, fill: '#0d9488' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
