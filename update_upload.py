import re

with open('frontend/src/pages/Upload.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove background glows entirely
content = re.sub(r'<div className=\"absolute[^\"]*bg-blue-600/20[^\"]*\" />\n', '', content)
content = re.sub(r'<div className=\"absolute[^\"]*bg-teal-600/20[^\"]*\" />\n', '', content)
content = content.replace('      \n      <div className=\"max-w-4xl', '      <div className=\"max-w-4xl')

# Title gradient to solid slate
content = content.replace('bg-gradient-to-r from-blue-700 via-indigo-700 to-teal-700 bg-clip-text text-transparent', 'text-slate-900')

# Clouds
content = content.replace('text-blue-400/20', 'text-slate-900/10')
content = content.replace('text-teal-400/20', 'text-slate-900/10')
content = content.replace('text-indigo-400/20', 'text-slate-900/10')

# Drag states
content = content.replace('bg-blue-500/10 border border-blue-400/50 shadow-[0_0_50px_-10px_rgba(59,130,246,0.3)]', 'bg-white/50 border border-slate-900/20 shadow-[0_0_50px_-10px_rgba(0,0,0,0.15)]')
content = content.replace('bg-blue-500/30', 'bg-slate-900/10')
content = content.replace('text-blue-600 animate-bounce', 'text-slate-900 animate-bounce')
content = content.replace('group-hover:text-blue-600', 'group-hover:text-slate-900')

# File name
content = content.replace('text-transparent bg-clip-text bg-gradient-to-r from-blue-700 to-teal-700', 'text-slate-900')

# Main Button
content = content.replace('bg-gradient-to-r from-blue-600 to-indigo-600 text-white', 'bg-slate-900 text-white hover:bg-slate-800')
content = content.replace('shadow-[0_10px_30px_-10px_rgba(59,130,246,0.6)] hover:shadow-[0_10px_40px_-10px_rgba(79,70,229,0.8)]', 'shadow-xl shadow-slate-900/20 hover:shadow-2xl hover:shadow-slate-900/30')

# Progress bar
content = content.replace('text-blue-700 font-bold bg-blue-500/10', 'text-slate-900 font-bold bg-slate-900/10')
content = content.replace('bg-gradient-to-r from-blue-500 to-indigo-500', 'bg-slate-800')
content = content.replace('bg-gradient-to-r from-green-500 to-emerald-400', 'bg-slate-900')
content = content.replace('text-blue-600 animate-spin', 'text-slate-800 animate-spin')

# Status texts
content = content.replace(\"'text-blue-600'\", \"'text-slate-800'\")

# View knowledge graph button
content = content.replace('bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition-colors shadow-lg shadow-blue-500/20', 'bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-xl transition-colors shadow-lg shadow-slate-900/20')

# Instruction cards at bottom
content = content.replace('bg-blue-500/10', 'bg-slate-900/5')
content = content.replace('border-blue-500/20', 'border-slate-900/10')
content = content.replace('text-blue-600', 'text-slate-800')

content = content.replace('bg-indigo-500/10', 'bg-slate-900/5')
content = content.replace('border-indigo-500/20', 'border-slate-900/10')
content = content.replace('text-indigo-600', 'text-slate-800')

content = content.replace('bg-emerald-500/10', 'bg-slate-900/5')
content = content.replace('border-emerald-500/20', 'border-slate-900/10')
content = content.replace('text-emerald-600', 'text-slate-800')

with open('frontend/src/pages/Upload.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
