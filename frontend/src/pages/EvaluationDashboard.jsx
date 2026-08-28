import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Target, CheckCircle2, ShieldCheck, HelpCircle } from 'lucide-react';

const mockEvalData = [
  { question: 'Q1 (Term)', faithfulness: 0.95, context_precision: 0.92, answer_relevancy: 0.98 },
  { question: 'Q2 (Law)', faithfulness: 0.99, context_precision: 0.85, answer_relevancy: 0.95 },
  { question: 'Q3 (Party)', faithfulness: 0.88, context_precision: 0.90, answer_relevancy: 0.89 },
  { question: 'Q4 (Indemnity)', faithfulness: 0.82, context_precision: 0.75, answer_relevancy: 0.85 },
  { question: 'Q5 (Payment)', faithfulness: 0.91, context_precision: 0.88, answer_relevancy: 0.92 },
];

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
  const avgFaithfulness = mockEvalData.reduce((acc, curr) => acc + curr.faithfulness, 0) / mockEvalData.length;
  const avgPrecision = mockEvalData.reduce((acc, curr) => acc + curr.context_precision, 0) / mockEvalData.length;
  const avgRelevancy = mockEvalData.reduce((acc, curr) => acc + curr.answer_relevancy, 0) / mockEvalData.length;

  return (
    <div className="space-y-8">
      
      <div className="bg-slate-800 rounded-xl p-6 shadow-md border border-slate-700 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">RAG Evaluation Metrics</h1>
          <p className="text-slate-400">Continuous evaluation of generation quality based on Ragas metrics.</p>
        </div>
        <div className="text-sm text-slate-500 bg-slate-900 px-4 py-2 rounded-lg border border-slate-700 flex items-center">
          <HelpCircle className="w-4 h-4 mr-2" /> Note: Currently showing mock baseline data.
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
      <div className="bg-slate-800 rounded-xl p-6 shadow-md border border-slate-700">
        <h2 className="text-lg font-semibold text-white mb-6 border-b border-slate-700 pb-2">Per-Question Performance</h2>
        <div className="h-96 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={mockEvalData}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="question" stroke="#94a3b8" tick={{ fill: '#94a3b8' }} />
              <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8' }} domain={[0, 1]} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }}
                itemStyle={{ color: '#e2e8f0' }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Bar dataKey="faithfulness" name="Faithfulness" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="context_precision" name="Context Precision" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="answer_relevancy" name="Answer Relevancy" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
