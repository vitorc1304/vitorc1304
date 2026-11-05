import json, os, urllib.request, datetime, struct, pathlib, math
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'; OUT.mkdir(exist_ok=True)
USER = os.environ.get('GITHUB_USERNAME', 'vitorc1304')
TOKEN = os.environ.get('GH_TOKEN', '')
query = '''query($login:String!) { user(login:$login) { contributionsCollection { contributionCalendar { weeks { contributionDays { date contributionCount } } } } } }'''
req = urllib.request.Request('https://api.github.com/graphql', data=json.dumps({'query':query,'variables':{'login':USER}}).encode(), headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json','User-Agent':'github-soundtrack'})
with urllib.request.urlopen(req, timeout=25) as response:
    result = json.load(response)
if result.get('errors') or not result.get('data',{}).get('user'):
    raise RuntimeError('Could not retrieve contributions: '+str(result.get('errors')))
weeks = result['data']['user']['contributionsCollection']['contributionCalendar']['weeks']
days = sorted((d for w in weeks for d in w['contributionDays']), key=lambda d:d['date'])
# Recent 64 days become a 64-step original melody. Zero-commit days are rests.
days = days[-64:]
scale = [0, 2, 3, 5, 7, 10]  # C minor pentatonic + sixth
notes = []
for i, d in enumerate(days):
    count = d['contributionCount']
    if count:
        pitch = 48 + scale[(i + count) % len(scale)] + (12 if count >= 4 else 0)
        velocity = min(115, 62 + 8 * count)
        notes.append((i, pitch, velocity, min(0.85, 0.38 + count*.08)))

def vlq(value):
    value = int(value); result = [value & 127]; value >>= 7
    while value:
        result.insert(0, (value & 127) | 128); value >>= 7
    return bytes(result)
# MIDI format 0, 480 ticks per beat, 120 BPM, eighth-note steps.
ticks_per_step = 240
events = [(0, 0, b'\xff\x51\x03\x07\xa1\x20'), (0, 1, b'\xc0\x0a')]
for step, pitch, velocity, duration in notes:
    start = step * ticks_per_step
    end = start + max(50, round(ticks_per_step * duration))
    events.extend([(start, 2, bytes([0x90,pitch,velocity])), (end, 0, bytes([0x80,pitch,0]))])
events.sort(key=lambda x:(x[0],x[1]))
track = bytearray(); previous = 0
for tick, _, event in events:
    track += vlq(tick-previous) + event; previous = tick
track += b'\x00\xff\x2f\x00'
(OUT/'commit-soundtrack.mid').write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(track))+track)
# SVG: music-note skyline (static, automatically refreshed). GitHub sanitizes SVG animations;
# keep SVG static and reliable rather than promising animation.
width=960; height=250; left=35; stepw=13.7
bars=[]
for i,d in enumerate(days):
    n=d['contributionCount']; x=left+i*stepw
    h=5 if n==0 else min(135, 18+n*17)
    color='#26273d' if n==0 else ('#38bdf8' if n>=4 else '#a78bfa')
    bars.append(f'<rect x="{x:.1f}" y="{198-h:.1f}" width="9" height="{h:.1f}" rx="3" fill="{color}"/>')
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub contributions represented as musical bars">
<rect width="960" height="250" rx="16" fill="#0d1117"/>
<text x="35" y="39" fill="#d8b4fe" font-family="monospace" font-size="19" font-weight="bold">♫ COMMIT SOUNDTRACK</text>
<text x="35" y="62" fill="#94a3b8" font-family="monospace" font-size="12">{USER} · last 64 days · 120 BPM · C minor</text>
<line x1="35" y1="200" x2="923" y2="200" stroke="#34364a"/>
{''.join(bars)}
<text x="35" y="230" fill="#94a3b8" font-family="monospace" font-size="12">{len(notes)} active days · {sum(d['contributionCount'] for d in days)} contributions · updated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')} UTC</text>
</svg>'''
(OUT/'commit-soundtrack.svg').write_text(svg,encoding='utf-8')
print('Created SVG and MIDI from',len(days),'days,',len(notes),'notes')
