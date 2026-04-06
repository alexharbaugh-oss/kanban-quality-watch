import streamlit as st
import pandas as pd
import re
import json
from datetime import datetime, timedelta
from collections import defaultdict

st.set_page_config(
    page_title="Kanban Quality Watch",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# STYLING
# ============================================================
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .metric-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 8px;
    }
    .metric-label { font-size: 13px; color: #666; margin-bottom: 2px; }
    .metric-value { font-size: 26px; font-weight: 600; }
    .red-text { color: #c0392b; }
    .orange-text { color: #d4730b; }
    .yellow-text { color: #b8960a; }
    .green-text { color: #1D9E75; }
    .alert-card {
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-left: 4px solid;
    }
    .alert-red { background: #fdf0ef; border-color: #c0392b; }
    .alert-orange { background: #fef6ed; border-color: #d4730b; }
    .alert-yellow { background: #fefbed; border-color: #b8960a; }
    .alert-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
    .alert-meta { font-size: 12px; color: #666; margin-bottom: 6px; }
    .alert-detail { font-size: 12px; color: #444; line-height: 1.6; }
    .issue-line { font-size: 12px; padding: 2px 0; }
    .scrap-badge {
        background: #c0392b; color: white; padding: 1px 8px;
        border-radius: 10px; font-size: 11px; font-weight: 600;
    }
    .rework-badge {
        background: #2471a3; color: white; padding: 1px 8px;
        border-radius: 10px; font-size: 11px; font-weight: 600;
    }
    .pending-badge {
        background: #d4920b; color: white; padding: 1px 8px;
        border-radius: 10px; font-size: 11px; font-weight: 600;
    }
    .stage-header {
        background: #1a2332; color: white; padding: 8px 14px;
        border-radius: 6px; margin: 16px 0 10px 0;
        font-weight: 600; font-size: 14px;
    }
    div[data-testid="stExpander"] { border: none; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_part_number(pn):
    """Strip suffixes to get base part number for matching."""
    if not pn or not isinstance(pn, str):
        return ""
    pn = pn.strip()
    # Remove common suffixes: -X000-L00000, -S10, -X01, -X000, -L00000, etc.
    pn = re.sub(r'-X\d+-L\d+', '', pn)
    pn = re.sub(r'-X\d+$', '', pn)
    pn = re.sub(r'-S\d+$', '', pn)
    pn = re.sub(r'-L\d+$', '', pn)
    pn = re.sub(r'-TPDT$', '', pn)
    return pn.strip()


def extract_defect_codes(defect_str):
    """Parse defect code string to extract individual codes."""
    if not defect_str or not isinstance(defect_str, str):
        return []
    codes = re.findall(r'(?:COF|AFA|BLD)-(\w+)-', defect_str)
    return codes


def score_part(issues):
    """Score a part based on its quality history. Returns (severity, score)."""
    scrap_count = sum(1 for i in issues if i.get('Issue Disposition Type', '') == 'Scrap')
    wrinkle_count = sum(1 for i in issues if 'WNK' in str(i.get('Defect Code', '')))
    pending_count = sum(1 for i in issues if not i.get('Issue Disposition Type', '').strip())
    total = len(issues)

    # Scoring
    score = 0
    score += scrap_count * 10
    score += wrinkle_count * 3
    score += pending_count * 1
    score += total * 1

    if scrap_count >= 2:
        severity = "RED"
    elif scrap_count >= 1 or total >= 3:
        severity = "ORANGE"
    elif total >= 1:
        severity = "YELLOW"
    else:
        severity = "CLEAN"

    return severity, score, {
        'total': total,
        'scraps': scrap_count,
        'wrinkles': wrinkle_count,
        'pending': pending_count,
    }


def parse_ion_data(df):
    """Parse Ion quality issue data."""
    issues = []
    seen_ids = set()
    for _, row in df.iterrows():
        iid = str(row.get('Issue ID', ''))
        if iid in seen_ids:
            continue
        seen_ids.add(iid)
        issues.append({
            'Issue ID': iid,
            'Title': str(row.get('Title', '')).strip(),
            'Description': str(row.get('Description', '')).strip(),
            'Part Number': normalize_part_number(str(row.get('Part Number', ''))),
            'Part Number Raw': str(row.get('Part Number', '')).strip(),
            'Defect Code': str(row.get('Defect Code', '')),
            'Issue Disposition Type': str(row.get('Issue Disposition Type', '')).strip(),
            'Status': str(row.get('Status', '')).strip(),
            'Day of Created': str(row.get('Day of Created', '')).strip(),
            'Created By': str(row.get('Created By', '')).strip(),
            'Serial Number': str(row.get('Serial Number', '')).strip(),
        })
    return issues


def parse_jira_data(df):
    """Parse Jira Kanban data."""
    status_map = {
        'Open': 'Ready to Schedule',
        'Scheduled': 'Scheduled',
        'Kit': 'Material Cutting',
        'Ready to Laminate': 'Ready to Layup',
        'Laminate': 'Layup',
        'Ready to Cure': 'Ready to Cure',
    }

    parts = []
    for _, row in df.iterrows():
        jira_status = str(row.get('Status', '')).strip()
        if jira_status not in status_map:
            continue

        summary = str(row.get('Summary', '')).strip()
        part_desc = summary.split(' SN:')[0].strip() if ' SN:' in summary else summary
        pn_raw = str(row.get('Custom field (Part Number)', '')).strip()

        parts.append({
            'ME Key': str(row.get('Issue key', '')).strip(),
            'Summary': summary,
            'Part Description': part_desc,
            'Part Number': normalize_part_number(pn_raw),
            'Part Number Raw': pn_raw,
            'Pipeline Stage': status_map[jira_status],
            'Jira Status': jira_status,
        })
    return parts


def cross_reference(kanban_parts, quality_issues):
    """Cross-reference Kanban parts against quality issues by part number."""
    # Build index of quality issues by normalized part number
    pn_index = defaultdict(list)
    for issue in quality_issues:
        pn = issue['Part Number']
        if pn:
            pn_index[pn].append(issue)

    results = []
    for part in kanban_parts:
        pn = part['Part Number']
        matched_issues = []

        # Direct match
        if pn and pn in pn_index:
            matched_issues = pn_index[pn]

        # Partial match (check if part number is contained in or contains quality PN)
        if not matched_issues and pn:
            for qpn, qissues in pn_index.items():
                if pn in qpn or qpn in pn:
                    matched_issues.extend(qissues)

        # Deduplicate
        seen = set()
        unique_issues = []
        for i in matched_issues:
            if i['Issue ID'] not in seen:
                seen.add(i['Issue ID'])
                unique_issues.append(i)

        severity, score, stats = score_part(unique_issues)

        results.append({
            **part,
            'Severity': severity,
            'Score': score,
            'Stats': stats,
            'Issues': unique_issues,
        })

    # Sort by score descending within each stage
    results.sort(key=lambda x: -x['Score'])
    return results


def render_issue_line(issue):
    """Render a single quality issue as HTML."""
    date = issue.get('Day of Created', '')
    title = issue.get('Title', '')
    disp = issue.get('Issue Disposition Type', '').strip()

    if disp == 'Scrap':
        badge = '<span class="scrap-badge">SCRAP</span>'
    elif disp == 'Rework':
        badge = '<span class="rework-badge">REWORK</span>'
    elif not disp or disp == 'nan':
        badge = '<span class="pending-badge">PENDING</span>'
    else:
        badge = f'<span style="font-size:11px;color:#666;">{disp}</span>'

    defect_codes = extract_defect_codes(issue.get('Defect Code', ''))
    codes_str = ', '.join(defect_codes) if defect_codes else ''

    return f'<div class="issue-line">{date} | {title} | {badge} {codes_str}</div>'


def render_alert_card(part):
    """Render an alert card for a flagged part."""
    sev = part['Severity']
    css_class = f"alert-{sev.lower()}"
    stats = part['Stats']

    me = part['ME Key']
    desc = part['Part Description'][:60]
    stage = part['Pipeline Stage']
    total = stats['total']
    scraps = stats['scraps']
    wrinkles = stats['wrinkles']
    pending = stats['pending']

    issues_html = ""
    # Show last 5 issues sorted by date
    sorted_issues = sorted(part['Issues'], key=lambda x: x.get('Day of Created', ''))
    for issue in sorted_issues[-5:]:
        issues_html += render_issue_line(issue)

    stats_parts = []
    if scraps > 0:
        stats_parts.append(f'<span class="red-text">{scraps} scraps</span>')
    if wrinkles > 0:
        stats_parts.append(f'{wrinkles} wrinkles')
    if pending > 0:
        stats_parts.append(f'<span class="orange-text">{pending} pending</span>')
    stats_str = f"{total} issues: " + ", ".join(stats_parts) if stats_parts else f"{total} issues"

    html = f"""
    <div class="alert-card {css_class}">
        <div class="alert-title">{desc}</div>
        <div class="alert-meta">{me} | {stage} | {stats_str}</div>
        <div class="alert-detail">{issues_html}</div>
    </div>
    """
    return html


# ============================================================
# MAIN APP
# ============================================================

st.title("Kanban Quality Watch")
st.caption("Cross-references your Jira production pipeline with Ion quality data to flag parts with quality history.")

# Sidebar: Data upload
with st.sidebar:
    st.header("Data Upload")

    st.subheader("Quality Issues (Ion)")
    ion_files = st.file_uploader(
        "Upload Ion CSV(s)",
        type="csv",
        accept_multiple_files=True,
        key="ion",
        help="Export from Ion. Can upload multiple files (e.g. weekly + monthly)."
    )

    st.subheader("Scrap Data (Ion)")
    scrap_file = st.file_uploader(
        "Upload Scrap CSV (optional)",
        type="csv",
        key="scrap",
        help="Separate scrap export from Ion if available."
    )

    st.subheader("Production Schedule (Jira)")
    jira_file = st.file_uploader(
        "Upload Jira CSV",
        type="csv",
        key="jira",
        help="Export from Jira Kanban board."
    )

    st.divider()

    if st.button("Run Analysis", type="primary", use_container_width=True):
        st.session_state['run'] = True

    st.divider()
    st.caption("Upload fresh CSVs anytime. Hit 'Run Analysis' to refresh the dashboard.")

# ============================================================
# ANALYSIS
# ============================================================

if ion_files and jira_file:
    # Parse all quality data
    all_quality_issues = []
    for f in ion_files:
        try:
            df = pd.read_csv(f)
            all_quality_issues.extend(parse_ion_data(df))
        except Exception as e:
            st.error(f"Error reading {f.name}: {e}")

    if scrap_file:
        try:
            df = pd.read_csv(scrap_file)
            # Add scrap issues, dedup against existing
            existing_ids = {i['Issue ID'] for i in all_quality_issues}
            scrap_issues = parse_ion_data(df)
            for si in scrap_issues:
                if si['Issue ID'] not in existing_ids:
                    all_quality_issues.append(si)
                    existing_ids.add(si['Issue ID'])
        except Exception as e:
            st.error(f"Error reading scrap file: {e}")

    # Parse Jira
    try:
        jira_df = pd.read_csv(jira_file)
        kanban_parts = parse_jira_data(jira_df)
    except Exception as e:
        st.error(f"Error reading Jira file: {e}")
        kanban_parts = []

    if all_quality_issues and kanban_parts:
        # Cross-reference
        results = cross_reference(kanban_parts, all_quality_issues)

        flagged = [r for r in results if r['Severity'] != 'CLEAN']
        red = [r for r in flagged if r['Severity'] == 'RED']
        orange = [r for r in flagged if r['Severity'] == 'ORANGE']
        yellow = [r for r in flagged if r['Severity'] == 'YELLOW']
        clean = [r for r in results if r['Severity'] == 'CLEAN']

        # Top metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Pipeline parts</div>
                <div class="metric-value">{len(results)}</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Quality issues loaded</div>
                <div class="metric-value">{len(all_quality_issues)}</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">RED alerts</div>
                <div class="metric-value red-text">{len(red)}</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">ORANGE alerts</div>
                <div class="metric-value orange-text">{len(orange)}</div>
            </div>""", unsafe_allow_html=True)
        with col5:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Flagged / Clean</div>
                <div class="metric-value">{len(flagged)} / {len(clean)}</div>
            </div>""", unsafe_allow_html=True)

        st.divider()

        # Stage order for display
        stage_order = ['Layup', 'Ready to Cure', 'Ready to Layup', 'Material Cutting', 'Scheduled', 'Ready to Schedule']

        # Tab layout
        tab_all, tab_red, tab_stage, tab_search = st.tabs(["All Alerts", "Red Alerts Only", "By Pipeline Stage", "Search by Part"])

        with tab_all:
            if red:
                st.markdown('<div class="stage-header">RED ALERT: Stop and plan before layup</div>', unsafe_allow_html=True)
                for part in red:
                    st.markdown(render_alert_card(part), unsafe_allow_html=True)

            if orange:
                st.markdown('<div class="stage-header">ORANGE ALERT: Extra eyes needed</div>', unsafe_allow_html=True)
                # Group by stage
                for stage in stage_order:
                    stage_parts = [p for p in orange if p['Pipeline Stage'] == stage]
                    if stage_parts:
                        st.markdown(f"**{stage}** ({len(stage_parts)})")
                        for part in stage_parts:
                            st.markdown(render_alert_card(part), unsafe_allow_html=True)

            if yellow:
                st.markdown('<div class="stage-header">YELLOW: Watch list</div>', unsafe_allow_html=True)
                with st.expander(f"Show {len(yellow)} yellow alerts"):
                    for stage in stage_order:
                        stage_parts = [p for p in yellow if p['Pipeline Stage'] == stage]
                        if stage_parts:
                            st.markdown(f"**{stage}** ({len(stage_parts)})")
                            for part in stage_parts:
                                st.markdown(render_alert_card(part), unsafe_allow_html=True)

        with tab_red:
            if red:
                for part in red:
                    st.markdown(render_alert_card(part), unsafe_allow_html=True)
                    with st.expander(f"Full issue history: {part['Part Description'][:50]}"):
                        for issue in sorted(part['Issues'], key=lambda x: x.get('Day of Created', '')):
                            disp = issue.get('Issue Disposition Type', '') or 'Pending'
                            codes = extract_defect_codes(issue.get('Defect Code', ''))
                            st.markdown(
                                f"**{issue['Day of Created']}** | {issue['Title']} | "
                                f"*{disp}* | {', '.join(codes)} | ID: {issue['Issue ID']}"
                            )
            else:
                st.success("No red alerts. Nice.")

        with tab_stage:
            for stage in stage_order:
                stage_flagged = [r for r in flagged if r['Pipeline Stage'] == stage]
                stage_clean_count = len([r for r in clean if r['Pipeline Stage'] == stage])
                stage_total = len([r for r in results if r['Pipeline Stage'] == stage])

                if stage_total > 0:
                    st.markdown(
                        f'<div class="stage-header">{stage}: {len(stage_flagged)} flagged / {stage_total} total</div>',
                        unsafe_allow_html=True
                    )

                    if stage_flagged:
                        for part in sorted(stage_flagged, key=lambda x: -x['Score']):
                            st.markdown(render_alert_card(part), unsafe_allow_html=True)
                    else:
                        st.markdown("*All parts clean in this stage.*")

        with tab_search:
            search = st.text_input("Search by part name, part number, or ME key")
            if search:
                search_upper = search.upper()
                matches = [r for r in results if
                    search_upper in r['Part Description'].upper() or
                    search_upper in r['Part Number'].upper() or
                    search_upper in r.get('Part Number Raw', '').upper() or
                    search_upper in r['ME Key'].upper()]

                if matches:
                    st.markdown(f"**{len(matches)} results:**")
                    for part in matches:
                        if part['Severity'] != 'CLEAN':
                            st.markdown(render_alert_card(part), unsafe_allow_html=True)
                        else:
                            st.markdown(
                                f"✅ **{part['Part Description'][:55]}** | "
                                f"{part['ME Key']} | {part['Pipeline Stage']} | No quality history"
                            )
                else:
                    st.info("No matches found.")

        # ============================================================
        # SUMMARY TABLE (expandable)
        # ============================================================
        st.divider()
        with st.expander("Full pipeline summary table"):
            summary_data = []
            for r in results:
                if r['Severity'] != 'CLEAN':
                    summary_data.append({
                        'Severity': r['Severity'],
                        'Stage': r['Pipeline Stage'],
                        'ME Key': r['ME Key'],
                        'Part': r['Part Description'][:50],
                        'PN': r.get('Part Number Raw', ''),
                        'Issues': r['Stats']['total'],
                        'Scraps': r['Stats']['scraps'],
                        'Wrinkles': r['Stats']['wrinkles'],
                        'Pending': r['Stats']['pending'],
                    })

            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(
                    summary_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'Severity': st.column_config.TextColumn(width="small"),
                        'Stage': st.column_config.TextColumn(width="medium"),
                        'Scraps': st.column_config.NumberColumn(format="%d"),
                        'Wrinkles': st.column_config.NumberColumn(format="%d"),
                    }
                )

        # ============================================================
        # QUALITY ISSUE SUMMARY
        # ============================================================
        with st.expander("Quality issue summary (loaded data)"):
            defect_counts = defaultdict(int)
            disp_counts = defaultdict(int)
            for i in all_quality_issues:
                codes = extract_defect_codes(i.get('Defect Code', ''))
                for code in codes:
                    defect_counts[code] += 1
                d = i.get('Issue Disposition Type', '').strip()
                disp_counts[d if d else 'Pending'] += 1

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Defect types:**")
                for code, count in sorted(defect_counts.items(), key=lambda x: -x[1]):
                    st.markdown(f"- {code}: {count}")
            with col2:
                st.markdown("**Dispositions:**")
                for disp, count in sorted(disp_counts.items(), key=lambda x: -x[1]):
                    st.markdown(f"- {disp}: {count}")

else:
    # Landing page
    st.info("Upload your Ion quality CSV(s) and Jira Kanban CSV in the sidebar to get started.")

    st.markdown("""
    **How to use:**
    1. Export your quality issues from Ion (CSV). You can upload multiple files (e.g. weekly + monthly + scrap).
    2. Export your Jira Kanban board (CSV export from Jira).
    3. Upload both in the sidebar and hit **Run Analysis**.
    4. The dashboard will cross-reference every part in your pipeline against quality history and flag anything with issues.

    **Severity levels:**
    - **RED**: 2+ scrap events on the part number. Stop and plan before layup.
    - **ORANGE**: 1 scrap event, or 3+ total issues. Extra eyes needed.
    - **YELLOW**: 1-2 issues, no scrap. Watch list.
    - **CLEAN**: No quality history. Standard process.

    **Pipeline stages tracked:** Ready to Schedule, Scheduled, Material Cutting, Ready to Layup, Layup, Ready to Cure
    """)
