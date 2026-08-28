import re

with open('frontend/src/pages/ContractDetail.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace bg-slate-800 with glass
content = content.replace('bg-slate-800', 'bg-white/40 backdrop-blur-xl')
# Replace bg-slate-900 with glass
content = content.replace('bg-slate-900', 'bg-white/60')
# Replace border-slate-700 with border-white/50
content = content.replace('border-slate-700', 'border-white/50')
# Replace text colors
content = content.replace('text-white', 'text-slate-900')
content = content.replace('text-slate-200', 'text-slate-800')
content = content.replace('text-slate-300', 'text-slate-700')
content = content.replace('text-slate-400', 'text-slate-600')

# Remove purple
content = content.replace('text-purple-400', 'text-teal-600')
# Make other icons darker
content = content.replace('text-blue-400', 'text-blue-600')
content = content.replace('text-green-400', 'text-emerald-600')

# Node styling in ForceGraph2D
content = content.replace(\"color: '#a78bfa'\", \"color: '#0d9488'\")
content = content.replace(\"color: '#60a5fa'\", \"color: '#2563eb'\")
content = content.replace(\"color: '#34d399'\", \"color: '#059669'\")
content = content.replace(\"color: '#f472b6'\", \"color: '#e11d48'\")

# Link styling
content = content.replace(\"ctx.strokeStyle = '#475569';\", \"ctx.strokeStyle = '#94a3b8';\")
content = content.replace(\"ctx.fillStyle = '#94a3b8';\", \"ctx.fillStyle = '#475569';\")

with open('frontend/src/pages/ContractDetail.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
