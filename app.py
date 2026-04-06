import streamlit as st
import pandas as pd
import re
from datetime import datetime
from collections import defaultdict

st.set_page_config(page_title="Kanban Quality Watch", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 1100px; }
    .main-header { background: #1a2332; color: white; padding: 14px 20px; border-radius: 8px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
    .main-header h1 { font-size: 20px; font-weight: 700; margin: 0; color: white; }
    .main-header .sub { font-size: 12px; color: #94a3b8; }
    .metric-row { display: flex; gap: 10px; margin-bottom: 16px; }
    .metric-box { flex: 1; background: #f4f4f4; border-radius: 8px; padding: 12px 16px; }
    .metric-box .label { font-size: 11px; color: #666; margin-bottom: 2px; }
    .metric-box .val { font-size: 22px; font-weight: 700; }
    .metric-box .msub { font-size: 10px; color: #999; margin-top: 2px; }
    .val-red { color: #c0392b; }
    .val-orange { color: #d4730b; }
    .val-green { color: #1D9E75; }
    .section-red { background: #c0392b; color: white; padding: 8px 14px; border-radius: 6px; font-weight: 700; font-size: 13px; margin: 18px 0 10px; }
    .section-orange { background: #d4730b; color: white; padding: 8px 14px; border-radius: 6px; font-weight: 700; font-size: 13px; margin: 18px 0 10px; }
    .stage-hdr { background: #1a2332; color: white; padding: 7px 14px; border-radius: 5px; font-weight: 600; font-size: 13px; margin: 12px 0 8px; display: flex; justify-content: space-between; }
    .alert-card { border-radius: 6px; padding: 12px 14px 10px 18px; margin-bottom: 8px; border-left: 4px solid; }
    .card-red { background: #fdf0ef; border-color: #c0392b; }
    .card-orange { background: #fef6ed; border-color: #d4730b; }
    .card-yellow { background: #fefbed; border-color: #b8960a; }
    .sev-badge { display: inline-block; padding: 1px 10px; border-radius: 3px; font-size: 10px; font-weight: 700; color: white; margin-right: 8px; }
    .badge-red { background: #c0392b; }
    .badge-orange { background: #d4730b; }
    .badge-yellow { background: #b8960a; }
    .part-name { font-weight: 700; font-size: 14px; color: #1a1a1a; display: inline; }
    .part-meta { font-size: 11px; color: #666; margin-top: 2px; }
    .history-label { font-size: 10px; font-weight: 700; color: #888; margin-top: 6px; letter-spacing: 0.5px; }
    .history-line { font-size: 12px; color: #444; padding: 1px 0; line-height: 1.5; }
    .disp-scrap { background: #c0392b; color: white; padding: 0 6px; border-radius: 8px; font-size: 10px; font-weight: 600; }
    .disp-rework { background: #2471a3; color: white; padding: 0 6px; border-radius: 8px; font-size: 10px; font-weight: 600; }
    .disp-pending { background: #d4920b; color: white; padding: 0 6px; border-radius: 8px; font-size: 10px; font-weight: 600; }
    .disp-uai { background: #1D9E75; color: white; padding: 0 6px; border-radius: 8px; font-size: 10px; font-weight: 600; }
    .disp-void { background: #888; color: white; padding: 0 6px; border-radius: 8px; font-size: 10px; font-weight: 600; }
    .cell-tag { display: inline-block; background: #2471a3; color: white; padding: 2px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-left: 8px; }
    .yellow-summary { background: #fefbed; border-left: 4px solid #b8960a; border-radius: 4px; padding: 10px 14px; margin: 8px 0; font-size: 12px; color: #444; }
    .yellow-summary strong { color: #b8960a; }
    .priority-box { background: #fdf0ef; border-left: 4px solid #c0392b; border-radius: 4px; padding: 12px 16px; margin-top: 16px; }
    .priority-box .title { font-weight: 700; font-size: 13px; color: #c0392b; margin-bottom: 6px; }
    .priority-box .item { font-size: 12px; color: #333; line-height: 1.6; }
    .summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 12px 0; }
    .summary-cell { background: #f4f4f4; border-radius: 6px; padding: 10px 14px; }
    .summary-cell .s-label { font-size: 10px; color: #666; }
    .summary-cell .s-val { font-size: 20px; font-weight: 700; }
    .stDeployButton { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

def normalize_pn(pn):
    if not pn or not isinstance(pn, str) or pn == 'nan': return ""
    pn = pn.strip()
    pn = re.sub(r'-X\d+-L\d+', '', pn)
    pn = re.sub(r'-X\d+$', '', pn)
    pn = re.sub(r'-S\d+$', '', pn)
    pn = re.sub(r'-L\d+$', '', pn)
    pn = re.sub(r'-TPDT$', '', pn)
    return pn.strip()

def get_codes(s):
    if not s or not isinstance(s, str): return []
    return re.findall(r'(?:COF|AFA|BLD)-(\w+)-', s)

def dbadge(d):
    d = str(d).strip()
    if d == 'Scrap': return '<span class="disp-scrap">SCRAP</span>'
    elif d == 'Rework': return '<span class="disp-rework">REWORK</span>'
    elif d == 'Use As Is': return '<span class="disp-uai">USE AS IS</span>'
    elif d == 'Void': return '<span class="disp-void">VOID</span>'
    elif not d or d == 'nan': return '<span class="disp-pending">PENDING</span>'
    return f'<span style="font-size:10px;color:#666;">{d}</span>'

def score(issues):
    sc = sum(1 for i in issues if str(i.get('disp','')).strip() == 'Scrap')
    wk = sum(1 for i in issues if 'WNK' in str(i.get('defect','')))
    pn = sum(1 for i in issues if not str(i.get('disp','')).strip() or str(i.get('disp','')) == 'nan')
    t = len(issues)
    s = sc*10 + wk*3 + pn + t
    if sc >= 2: sv = "RED"
    elif sc >= 1 or t >= 3: sv = "ORANGE"
    elif t >= 1: sv = "YELLOW"
    else: sv = "CLEAN"
    return sv, s, {'total': t, 'scraps': sc, 'wrinkles': wk, 'pending': pn}

def load_ion(files, sf=None):
    seen, out = set(), []
    for f in list(files) + ([sf] if sf else []):
        if not f: continue
        try:
            df = pd.read_csv(f)
            for _, r in df.iterrows():
                iid = str(r.get('Issue ID',''))
                if iid in seen: continue
                seen.add(iid)
                out.append({'id': iid, 'title': str(r.get('Title','')).strip(), 'desc': str(r.get('Description','')).strip(),
                    'pn': normalize_pn(str(r.get('Part Number',''))), 'pn_raw': str(r.get('Part Number','')).strip(),
                    'defect': str(r.get('Defect Code','')), 'disp': str(r.get('Issue Disposition Type','')).strip(),
                    'status': str(r.get('Status','')).strip(), 'date': str(r.get('Day of Created','')).strip(),
                    'created_by': str(r.get('Created By','')).strip()})
        except Exception as e: st.error(f"Error: {e}")
    return out

def load_jira(f):
    sm = {'Open':'Ready to Schedule','Scheduled':'Scheduled','Kit':'Material Cutting',
          'Ready to Laminate':'Ready to Layup','Laminate':'Layup','Ready to Cure':'Ready to Cure'}
    out = []
    try:
        df = pd.read_csv(f)
        for _, r in df.iterrows():
            js = str(r.get('Status','')).strip()
            if js not in sm: continue
            summary = str(r.get('Summary','')).strip()
            name = summary.split(' SN:')[0].strip() if ' SN:' in summary else summary
            sn = summary.split('SN:')[1].strip() if 'SN:' in summary else ''
            pn = str(r.get('Custom field (Part Number)','')).strip()
            out.append({'me': str(r.get('Issue key','')).strip(), 'name': name, 'sn': sn,
                'pn': normalize_pn(pn), 'pn_raw': pn, 'stage': sm[js]})
    except Exception as e: st.error(f"Error: {e}")
    return out

def crossref(parts, issues):
    idx = defaultdict(list)
    for i in issues:
        if i['pn']: idx[i['pn']].append(i)
    results = []
    for p in parts:
        matched = list(idx.get(p['pn'], []))
        if not matched and p['pn']:
            for qpn, qi in idx.items():
                if p['pn'] in qpn or qpn in p['pn']: matched.extend(qi)
        seen, uniq = set(), []
        for i in matched:
            if i['id'] not in seen: seen.add(i['id']); uniq.append(i)
        sv, sc, st2 = score(uniq)
        results.append({**p, 'sev': sv, 'score': sc, 'stats': st2, 'issues': uniq})
    results.sort(key=lambda x: -x['score'])
    return results

def render_card(p):
    sev = p['sev']
    s = p['stats']
    parts_s = []
    if s['scraps']: parts_s.append(f"<span style='color:#c0392b;font-weight:600;'>{s['scraps']} scraps</span>")
    if s['wrinkles']: parts_s.append(f"{s['wrinkles']} wrinkles")
    if s['pending']: parts_s.append(f"<span style='color:#d4920b;'>{s['pending']} pending</span>")
    stats_str = f"{s['total']} issues" + (": " + ", ".join(parts_s) if parts_s else "")
    ck = f"cell_{p['me']}"
    cv = st.session_state.get(ck, '')
    cell_html = f'<span class="cell-tag">{cv}</span>' if cv else ''
    hist = ""
    for i in sorted(p['issues'], key=lambda x: x.get('date',''))[-6:]:
        codes = get_codes(i.get('defect',''))
        cs = f" ({', '.join(codes)})" if codes else ""
        hist += f'<div class="history-line">{i["date"]} | {i["title"]} | {dbadge(i["disp"])}{cs}</div>'
    return f"""<div class="alert-card card-{sev.lower()}">
        <span class="sev-badge badge-{sev.lower()}">{sev}</span>
        <span class="part-name">{p['name']}</span>{cell_html}
        <div class="part-meta">{p['me']} | {p['stage']} | {stats_str}</div>
        <div class="history-label">HISTORY:</div>{hist}</div>"""

STAGES = ['Layup','Ready to Cure','Ready to Layup','Material Cutting','Scheduled','Ready to Schedule']

with st.sidebar:
    st.header("Data Upload")
    ion_files = st.file_uploader("Quality Issues (Ion CSV)", type="csv", accept_multiple_files=True, key="ion")
    scrap_file = st.file_uploader("Scrap Data (optional)", type="csv", key="scrap")
    jira_file = st.file_uploader("Production Schedule (Jira CSV)", type="csv", key="jira")
    st.divider()

if ion_files and jira_file:
    issues = load_ion(ion_files, scrap_file)
    parts = load_jira(jira_file)
    results = crossref(parts, issues)
    flagged = [r for r in results if r['sev'] != 'CLEAN']
    reds = [r for r in flagged if r['sev'] == 'RED']
    oranges = [r for r in flagged if r['sev'] == 'ORANGE']
    yellows = [r for r in flagged if r['sev'] == 'YELLOW']
    cleans = [r for r in results if r['sev'] == 'CLEAN']

    # Sidebar cell assignments for layup parts
    layup_f = [r for r in flagged if r['stage'] == 'Layup']
    with st.sidebar:
        if layup_f:
            st.subheader("Cell Assignments (Layup)")
            for lp in layup_f:
                st.text_input(f"{lp['name'][:35]}", key=f"cell_{lp['me']}", placeholder="Cell...")

    st.markdown(f"""<div class="main-header"><div><h1>Kanban Quality Watch</h1>
        <div class="sub">Hand Layup | Ion + Jira cross-reference</div></div>
        <div style="text-align:right;"><div class="sub">Generated: {datetime.now().strftime('%m/%d/%Y %I:%M %p')}</div></div></div>""", unsafe_allow_html=True)

    st.markdown(f"""<div class="metric-row">
        <div class="metric-box"><div class="label">Pipeline parts</div><div class="val">{len(results)}</div><div class="msub">All stages</div></div>
        <div class="metric-box"><div class="label">Quality issues</div><div class="val">{len(issues)}</div><div class="msub">From Ion</div></div>
        <div class="metric-box"><div class="label">RED</div><div class="val val-red">{len(reds)}</div><div class="msub">Stop and plan</div></div>
        <div class="metric-box"><div class="label">ORANGE</div><div class="val val-orange">{len(oranges)}</div><div class="msub">Extra eyes</div></div>
        <div class="metric-box"><div class="label">Flagged / Clean</div><div class="val">{len(flagged)} <span style="font-size:14px;color:#999;">/ {len(cleans)}</span></div>
        <div class="msub">{round(len(flagged)/max(len(results),1)*100)}% have history</div></div></div>""", unsafe_allow_html=True)

    tab_floor, tab_ready, tab_up, tab_sum, tab_find = st.tabs(["On the Floor", "Ready to Layup", "Upstream", "Summary", "Search"])

    with tab_floor:
        st.markdown('<div class="section-red">PARTS ON THE FLOOR RIGHT NOW: Check these during your walk</div>', unsafe_allow_html=True)
        for stg in ['Layup', 'Ready to Cure']:
            sf = [r for r in flagged if r['stage'] == stg]
            sa = len([r for r in results if r['stage'] == stg])
            lbl = "IN LAYUP" if stg == 'Layup' else "READY TO CURE (about to go in autoclave)"
            st.markdown(f'<div class="stage-hdr"><span>{lbl}</span><span>{len(sf)} flagged / {sa} total</span></div>', unsafe_allow_html=True)
            if sf:
                for p in sf: st.markdown(render_card(p), unsafe_allow_html=True)
            else: st.success(f"All {stg.lower()} parts clean.")

    with tab_ready:
        rtl = [r for r in results if r['stage'] == 'Ready to Layup']
        rtlf = [r for r in rtl if r['sev'] != 'CLEAN']
        st.markdown('<div class="section-orange">READY TO LAYUP: Plan before these go to the tool</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stage-hdr"><span>READY TO LAYUP</span><span>{len(rtlf)} flagged / {len(rtl)} total</span></div>', unsafe_allow_html=True)
        for p in [r for r in rtlf if r['sev'] in ('RED','ORANGE')]:
            st.markdown(render_card(p), unsafe_allow_html=True)
        yw = [r for r in rtlf if r['sev'] == 'YELLOW']
        if yw:
            with st.expander(f"YELLOW WATCH ({len(yw)} more in Ready to Layup)"):
                for p in yw: st.markdown(render_card(p), unsafe_allow_html=True)

    with tab_up:
        for stg in ['Material Cutting','Scheduled','Ready to Schedule']:
            sa = [r for r in results if r['stage'] == stg]
            sf = [r for r in sa if r['sev'] != 'CLEAN']
            if not sa: continue
            st.markdown(f'<div class="stage-hdr"><span>{stg.upper()}</span><span>{len(sf)} flagged / {len(sa)} total</span></div>', unsafe_allow_html=True)
            ro = [p for p in sf if p['sev'] in ('RED','ORANGE')]
            yw = [p for p in sf if p['sev'] == 'YELLOW']
            for p in ro: st.markdown(render_card(p), unsafe_allow_html=True)
            if yw:
                names = ", ".join([f"{p['name'][:35]} ({p['stats']['total']})" for p in yw[:6]])
                extra = f", +{len(yw)-6} more" if len(yw) > 6 else ""
                st.markdown(f'<div class="yellow-summary"><strong>YELLOW WATCH ({len(yw)}):</strong> {names}{extra}</div>', unsafe_allow_html=True)
                with st.expander(f"Show all {len(yw)} yellow in {stg}"):
                    for p in yw: st.markdown(render_card(p), unsafe_allow_html=True)
            if not sf: st.markdown("*All clean.*")

    with tab_sum:
        st.markdown(f'<div class="stage-hdr"><span>PIPELINE QUALITY SUMMARY</span><span></span></div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="summary-grid">
            <div class="summary-cell"><div class="s-label">Total pipeline</div><div class="s-val">{len(results)}</div></div>
            <div class="summary-cell"><div class="s-label">With quality history</div><div class="s-val val-red">{len(flagged)} ({round(len(flagged)/max(len(results),1)*100)}%)</div></div>
            <div class="summary-cell"><div class="s-label">Clean</div><div class="s-val val-green">{len(cleans)} ({round(len(cleans)/max(len(results),1)*100)}%)</div></div></div>""", unsafe_allow_html=True)
        td = []
        for stg in STAGES:
            sp = [r for r in flagged if r['stage'] == stg]
            td.append({'Stage': stg, 'RED': len([p for p in sp if p['sev']=='RED']), 'ORANGE': len([p for p in sp if p['sev']=='ORANGE']),
                'YELLOW': len([p for p in sp if p['sev']=='YELLOW']), 'Total': len(sp)})
        st.dataframe(pd.DataFrame(td), use_container_width=True, hide_index=True)
        with st.expander("Full flagged parts table"):
            rows = [{'Severity': r['sev'], 'Stage': r['stage'], 'ME Key': r['me'], 'Part Name': r['name'][:50],
                'PN': r.get('pn_raw',''), 'Issues': r['stats']['total'], 'Scraps': r['stats']['scraps'],
                'Wrinkles': r['stats']['wrinkles'], 'Pending': r['stats']['pending']} for r in flagged]
            if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_find:
        q = st.text_input("Search by part name, part number, or ME key", placeholder="e.g. FORWARD FLOOR, 210029, ME-45588")
        if q:
            qu = q.upper()
            hits = [r for r in results if qu in r['name'].upper() or qu in r.get('pn','').upper() or qu in r.get('pn_raw','').upper() or qu in r['me'].upper()]
            if hits:
                st.markdown(f"**{len(hits)} results:**")
                for p in sorted(hits, key=lambda x: -x['score']):
                    if p['sev'] != 'CLEAN': st.markdown(render_card(p), unsafe_allow_html=True)
                    else: st.markdown(f"✅ **{p['name'][:55]}** | {p['me']} | {p['stage']} | No quality history")
            else: st.info("No matches.")
else:
    st.markdown("""<div class="main-header"><div><h1>Kanban Quality Watch</h1>
        <div class="sub">Hand Layup | Upload data to get started</div></div></div>""", unsafe_allow_html=True)
    st.markdown("""**How to use:**
1. Export quality issues from Ion (CSV). Upload multiple files if needed.
2. Export your Jira Kanban board (CSV).
3. Upload both in the sidebar. Dashboard builds automatically.

**Severity:** 🔴 RED = 2+ scraps (stop and plan) | 🟠 ORANGE = 1 scrap or 3+ issues (extra eyes) | 🟡 YELLOW = 1-2 issues (watch list) | ✅ CLEAN

**Tabs:** On the Floor (layup + cure) → Ready to Layup → Upstream → Summary → Search
    """)
