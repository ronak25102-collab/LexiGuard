import React from 'react';

export default function StatsCard({ icon, label, value }) {
  return (
    <div className="stat-card flex items-center space-x-4">
      <div className="stat-icon p-3 rounded-lg">
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium text-slate-600">{label}</p>
        <p className="text-2xl font-bold text-slate-900 drop-shadow-sm">{value}</p>
      </div>
    </div>
  );
}
