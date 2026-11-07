import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getEvaluationResults } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import PageHeader from '../components/PageHeader';
import Reveal from '../components/Reveal';
import Button from '../components/Button';
import { gsap, EASE, prefersReducedMotion } from '../lib/motion';

const MINT = '#b1f9e1';
const MUTED = 'rgba(177,249,225,0.6)';
const SERIES = {
  faithfulness: { name: 'Faithfulness', color: MINT },
  context_precision: { name: 'Context precision', color: '#ffffff' },
  answer_relevancy: { name: 'Answer relevancy', color: '#4fd1a9' },
};

function Metric({ index, title, score, color, description }) {
  const barRef = useRef(null);
  useLayoutEffect(() => {
    if (score == null || !barRef.current || prefersReducedMotion()) return undefined;
    const ctx = gsap.context(() => {
      gsap.from(barRef.current, {
        scaleX: 0, duration: 1.6, ease: EASE,
        scrollTrigger: { trigger: barRef.current, start: 'top 95%', once: true },
      });
    });
    return () => ctx.revert();
  }, [score]);

  const tone = score == null ? '' : score < 0.6 ? 'Needs work' : score < 0.8 ? 'Fair' : 'Strong';
  return (
    <div className="metric">
      <div className="metric__label"><span>{title}</span><span>0{index}</span></div>
      <div>
        <div className="metric__value">{score == null ? '—' : `${(score * 100).toFixed(1)}%`}</div>
        <div className="mt-3 text-[0.875rem] text-[var(--muted)]">{score == null ? 'Not measured in this run' : tone}</div>
      </div>
      <div>
        <div className="metric__bar" style={{ '--metric-color': color }}>
          <span ref={barRef} style={{ transform: `scaleX(${score ?? 0})` }} />
        </div>
        <p className="text-body mt-4 max-w-[34ch]">{description}</p>
      </div>
    </div>
  );
}

export default function EvaluationDashboard() {
  const [evalData, setEvalData] = useState([]);
  const [metadata, setMetadata] = useState(null);
  const [availableMetrics, setAvailableMetrics] = useState(['faithfulness', 'context_precision']);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const response = await getEvaluationResults();
        if (response && response.data) {
          setEvalData(response.data);
          setAvailableMetrics(response.available_metrics || ['faithfulness', 'context_precision']);
          setMetadata(response.metadata || null);
        } else {
          setEvalData([]);
        }
      } catch {
        setError('Failed to load evaluation data.');
      } finally {
        setLoading(false);
      }
    };
    fetchResults();
  }, []);

  const header = (
    <PageHeader
      index="03"
      eyebrow="Evaluation"
      title="Measured, not promised."
      description="Ragas scores for saved runs: how faithful answers are to the retrieved clauses, and how precisely the right evidence is ranked."
    >
      {metadata && (
        <p className="mt-6 text-[0.875rem] text-[var(--muted)]">
          {metadata.variant_label} · {metadata.cases} questions across {metadata.contracts} CUAD contracts
          {metadata.live_aura ? ' · Live Aura retrieval' : ''}
        </p>
      )}
    </PageHeader>
  );

  if (loading) {
    return <div className="page grid place-items-center"><LoadingSpinner text="Loading evaluation data…" /></div>;
  }

  if (error || evalData.length === 0) {
    return (
      <div className="page">
        {header}
        <section className="container-x pb-24 pt-8">
          <Reveal self className="panel flex flex-col items-start gap-6 p-8">
            <h2 className="display-m">{error ? 'Evaluation data could not be loaded.' : 'No evaluation data yet.'}</h2>
            <p className="text-body max-w-xl">
              {error || 'No measured results have been saved for this deployment. Run the evaluation script to populate this page.'}
            </p>
            <Button to="/query" variant="outline">Try a question instead</Button>
          </Reveal>
        </section>
      </div>
    );
  }

  const avg = key => evalData.reduce((acc, row) => acc + (row[key] ?? 0), 0) / evalData.length;
  const hasRelevancy = availableMetrics.includes('answer_relevancy');
  const axisTick = { fontSize: 12, fill: MUTED, fontFamily: 'Satoshi, sans-serif' };

  return (
    <div className="page">
      {header}

      <section className="container-x pb-16 pt-4">
        <Reveal className="metrics">
          <Metric index={1} title="Faithfulness" score={avg('faithfulness')} color={SERIES.faithfulness.color}
            description="Factual consistency of each answer against the context it retrieved." />
          <Metric index={2} title="Context precision" score={avg('context_precision')} color={SERIES.context_precision.color}
            description="Whether the relevant ground-truth evidence is ranked near the top." />
          <Metric index={3} title="Answer relevancy" score={hasRelevancy ? avg('answer_relevancy') : null} color={SERIES.answer_relevancy.color}
            description="How directly each answer addresses the question asked." />
        </Reveal>
      </section>

      <section className="container-x pb-24">
        <Reveal self className="panel">
          <div className="panel__head">
            <h2 className="panel__title">Performance across questions</h2>
            <span className="chip">{evalData.length} test questions</span>
          </div>
          <div className="h-[28rem] w-full p-4 pt-6">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={evalData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                <defs>
                  {Object.entries(SERIES).map(([key, { color }]) => (
                    <linearGradient key={key} id={`fill-${key}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={color} stopOpacity={0.18} />
                      <stop offset="95%" stopColor={color} stopOpacity={0} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid stroke="rgba(177,249,225,0.12)" vertical={false} />
                <XAxis
                  dataKey="question"
                  tickFormatter={val => (String(val).includes('-') ? `Q${String(val).split('-')[1]}` : val)}
                  tick={axisTick}
                  tickMargin={12}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={val => `${Math.round(val * 100)}%`}
                  domain={[0, 1]}
                  tick={axisTick}
                  tickMargin={12}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ stroke: 'rgba(177,249,225,0.3)' }}
                  contentStyle={{ backgroundColor: '#021d1a', border: '1px solid rgba(177,249,225,0.3)', borderRadius: 0, color: MINT, maxWidth: 360, whiteSpace: 'normal' }}
                  itemStyle={{ color: MINT, fontWeight: 500, padding: '3px 0' }}
                  labelStyle={{ color: '#fff', marginBottom: 8, paddingBottom: 6, borderBottom: '1px solid rgba(177,249,225,0.2)' }}
                  formatter={value => [`${(value * 100).toFixed(1)}%`]}
                  labelFormatter={label => evalData.find(d => d.question === label)?.full_question || label}
                />
                <Legend verticalAlign="top" height={36} iconType="square" wrapperStyle={{ paddingBottom: 16, color: MINT, fontWeight: 500 }} />
                {Object.entries(SERIES)
                  .filter(([key]) => key !== 'answer_relevancy' || hasRelevancy)
                  .map(([key, { name, color }]) => (
                    <Area
                      key={key}
                      type="monotone"
                      dataKey={key}
                      name={name}
                      stroke={color}
                      strokeWidth={2}
                      fill={`url(#fill-${key})`}
                      activeDot={{ r: 5, strokeWidth: 0, fill: color }}
                    />
                  ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Reveal>
      </section>
    </div>
  );
}
