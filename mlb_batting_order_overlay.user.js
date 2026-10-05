// ==UserScript==
// @name         MLB Batting Order Overlay
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Projected/confirmed MLB batting order beside Underdog names
// @match        https://app.underdogsports.com/*
// @match        https://app.underdogfantasy.com/*
// @grant        GM_xmlhttpRequest
// @connect      raw.githubusercontent.com
// @run-at       document-idle
// ==/UserScript==
(() => {
  'use strict';
  const URL='https://raw.githubusercontent.com/bsperf/underdog-overlay-data/main/mlb_batting_orders.json';
  const alias={ARI:'AZ',OAK:'ATH',KCR:'KC',SDP:'SD',SFG:'SF',TBR:'TB',WAS:'WSH'};
  const normTeam=s=>alias[String(s||'').trim().toUpperCase()]||String(s||'').trim().toUpperCase();
  const normName=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[.’']/g,'').replace(/\b(jr|sr|ii|iii|iv)\.?$/i,'').replace(/[^a-z\d]/gi,'').toLowerCase();
  let orders={},busy=false;
  function fetchOrders(){
    if(busy)return;busy=true;
    GM_xmlhttpRequest({method:'GET',url:URL+'?t='+Date.now(),timeout:15000,
      onload:r=>{busy=false;try{
        if(r.status!==200)throw Error('HTTP '+r.status);
        const data=JSON.parse(r.responseText),teams=data.teams||{};
        const next={};
        Object.entries(teams).forEach(([team,info])=>{
          if(!Array.isArray(info.lineup)||info.lineup.length!==9)return;
          next[normTeam(team)]={confirmed:info.confirmed===true,
            names:info.lineup.map(normName)};
        });
        orders=next;console.log('[MLB Order] Loaded',Object.keys(orders).length,'teams');scan();
      }catch(e){console.warn('[MLB Order] JSON problem:',e);}},
      onerror:()=>{busy=false;console.warn('[MLB Order] Fetch failed');},
      ontimeout:()=>{busy=false;console.warn('[MLB Order] Fetch timed out');}
    });
  }
  function scan(){
    document.querySelectorAll('[data-testid="player-cell-wrapper"]').forEach(cell=>{
      const nameEl=cell.querySelector('[class*="playerName"]');
      const matchEl=cell.querySelector('[class*="matchText"]');
      if(!nameEl||!matchEl)return;
      const team=normTeam(matchEl.querySelector('strong')?.textContent);
      const entry=orders[team];
      let tag=nameEl.querySelector('.mlbBattingOrder');
      const index=entry?.names.indexOf(normName(nameEl.childNodes[0]?.textContent||nameEl.textContent))??-1;
      if(index<0){if(tag)tag.remove();return;}
      if(!tag){tag=document.createElement('span');tag.className='mlbBattingOrder';
        Object.assign(tag.style,{display:'inline-block',marginLeft:'6px',padding:'1px 5px',borderRadius:'4px',fontWeight:'bold',fontSize:'12px',color:'#fff'});
        nameEl.appendChild(tag);
      }
      tag.textContent='#'+(index+1);
      tag.style.background=entry.confirmed?'#22863a':'#707070';
      tag.title=entry.confirmed?'Confirmed lineup':'Projected lineup';
    });
  }
  fetchOrders();setInterval(scan,1500);setInterval(fetchOrders,60000);
})();
