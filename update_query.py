import re

with open('frontend/src/pages/QueryInterface.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Filter badges
content = content.replace('bg-teal-500/15 border border-teal-500/30 text-teal-800', 'bg-slate-900/10 border border-slate-900/20 text-slate-800')
content = content.replace('hover:bg-teal-500/30', 'hover:bg-slate-900/20')

# Source toggles
content = content.replace(\"'bg-blue-500/10 text-blue-800'\", \"'bg-slate-900/10 text-slate-900'\")
content = content.replace(\"'bg-teal-500/15 text-teal-800'\", \"'bg-slate-900/10 text-slate-900'\")

# Search icon
content = content.replace('text-blue-600', 'text-slate-800')

# Hero subtitle
content = content.replace('text-teal-700 font-bold', 'text-slate-900 font-bold')

# User message bubble
content = content.replace(\"'bg-blue-600 text-white rounded-br-none border border-blue-500'\", \"'bg-slate-900 text-white rounded-br-none shadow-md'\")
content = content.replace('text-blue-200', 'text-slate-300')

# AI message badges
content = content.replace('text-teal-800', 'text-slate-800')
content = content.replace('text-emerald-700 bg-emerald-500/15', 'text-slate-700 bg-slate-900/10')
content = content.replace('border-emerald-500/20', 'border-slate-900/20')

# Submit button
content = content.replace('bg-blue-600 hover:bg-blue-500 disabled:bg-slate-400 text-white', 'bg-slate-900 hover:bg-slate-800 disabled:bg-slate-400 text-white')

with open('frontend/src/pages/QueryInterface.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
