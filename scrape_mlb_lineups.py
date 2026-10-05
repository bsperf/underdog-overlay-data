#!/usr/bin/env python3
"""Extract RotoGrinders MLB batting orders; fail closed if layout changes."""
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URL = 'https://rotogrinders.com/lineups/mlb'
OUT = Path('mlb_batting_orders.json')
TEAMS = {
 'Arizona Diamondbacks':'AZ','Atlanta Braves':'ATL','Baltimore Orioles':'BAL',
 'Boston Red Sox':'BOS','Chicago Cubs':'CHC','Chicago White Sox':'CWS',
 'Cincinnati Reds':'CIN','Cleveland Guardians':'CLE','Colorado Rockies':'COL',
 'Detroit Tigers':'DET','Houston Astros':'HOU','Kansas City Royals':'KC',
 'Los Angeles Angels':'LAA','LA Angels':'LAA','Los Angeles Dodgers':'LAD',
 'LA Dodgers':'LAD','Miami Marlins':'MIA','Milwaukee Brewers':'MIL',
 'Minnesota Twins':'MIN','New York Mets':'NYM','New York Yankees':'NYY',
 'Athletics':'ATH','Oakland Athletics':'ATH','Philadelphia Phillies':'PHI',
 'Pittsburgh Pirates':'PIT','San Diego Padres':'SD','San Francisco Giants':'SF',
 'Seattle Mariners':'SEA','St. Louis Cardinals':'STL','Tampa Bay Rays':'TB',
 'Texas Rangers':'TEX','Toronto Blue Jays':'TOR','Washington Nationals':'WSH'
}
# Extract the human-visible text. Avoid scripts and styling.
def get_lines(html):
 soup=BeautifulSoup(html,'html.parser')
 for tag in soup(['script','style','noscript','svg']):tag.decompose()
 return [re.sub(r'\s+',' ',s).strip() for s in soup.stripped_strings if s.strip()]

def parse(lines):
 # RotoGrinders displays away/home team headings followed by two 1-9 lists.
 # Identify each matchup from adjacent full team names, then identify ordered
 # lists. If the structure changes, refuse to overwrite the last valid JSON.
 headings=[]
 names=sorted(TEAMS,key=len,reverse=True)
 for i,s in enumerate(lines):
  if s in TEAMS and (not headings or headings[-1][0]!=i):headings.append((i,TEAMS[s]))
 if len(headings)<2:raise ValueError('No full team-name headings found; layout may have changed')
 blocks=[]
 for j in range(0,len(headings)-1,2):
  (start,away),(homeidx,home)=headings[j:j+2]
  end=headings[j+2][0] if j+2<len(headings) else len(lines)
  segment=lines[homeidx+1:end]
  # Detect exactly nine numbered slots, each followed by a player name.
  # Player names appear as text adjacent to 1..9, optionally with hand/position/salary.
  slots=[]; current=[]; last=0
  for k,value in enumerate(segment):
   if re.fullmatch('[1-9]',value):
    n=int(value)
    if n==1:
     if current:slots.append(current)
     current=[];last=0
    if n==last+1:
     # RotoGrinders hitter name is next nonempty text, before handedness.
     candidate=segment[k+1] if k+1<len(segment) else ''
     if re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .’'\-]+",candidate) and len(candidate)>3:
      current.append(candidate);last=n
   if last==9 and len(current)==9:
    slots.append(current);current=[];last=0
  if current:slots.append(current)
  valid=[s for s in slots if len(s)==9 and len(set(s))==9]
  if len(valid)!=2:raise ValueError(f'{away}@{home}: expected two complete lineups; found {len(valid)}')
  # Confirmed status is not inferred: RG's explicit 'lineup not released'
  # indicates projected. Unknown indicators are conservatively projected.
  indicators=[v.lower() for v in segment if 'lineup not released' in v.lower() or 'lineup confirmed' in v.lower()]
  for idx,code in enumerate((away,home)):
   confirmed=idx<len(indicators) and 'confirmed' in indicators[idx]
   blocks.append((code,{'confirmed':confirmed,'lineup':valid[idx]}))
 if not blocks:raise ValueError('No lineups parsed')
 return dict(blocks)

def diagnostics(html, lines):
 soup = BeautifulSoup(html, 'html.parser')
 print('DIAGNOSTICS: response bytes:', len(html), flush=True)
 print('DIAGNOSTICS: title:', soup.title.get_text(' ', strip=True) if soup.title else '(none)', flush=True)
 print('DIAGNOSTICS: text count:', len(lines), flush=True)
 print('DIAGNOSTICS: first 65 visible text tokens:', repr(lines[:65]), flush=True)
 for term in ('Chicago White Sox','Cleveland Guardians','Sam Antonacci','lineup not released'):
  hits = [(i, v) for i,v in enumerate(lines) if term.lower() in v.lower()]
  print('DIAGNOSTICS: term', repr(term), 'hits', hits[:4], flush=True)
  tag = soup.find(string=lambda v: bool(v and term.lower() in str(v).lower()))
  if tag:
   for level in range(1,4):
    parent=tag
    for _ in range(level):
     parent=parent.parent if parent else None
    if parent:
     print('DIAGNOSTICS: ancestor', term, level, str(parent)[:1600], flush=True)
 # Detect likely bot/captcha pages without overwriting good data.
 for term in ('captcha','access denied','cloudflare','enable javascript'):
  if term in soup.get_text(' ',strip=True).lower():
   print('DIAGNOSTICS: possible challenge:', term, flush=True)

def main():
 r=requests.get(URL,headers={'User-Agent':'Mozilla/5.0 (compatible; lineup-updater/1.0)'},timeout=25)
 r.raise_for_status()
 lines=get_lines(r.text)
 try:
  data=parse(lines)
 except Exception:
  diagnostics(r.text,lines)
  raise
 print('Parsed teams:',', '.join(data))
 payload={'updated_at':datetime.now(timezone.utc).isoformat(),'source':URL,'teams':data}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
