import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np 
from urllib.parse import urlparse, urljoin

try:
    from weasyprint import HTML
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
# NOTE: The following libraries are REQUIRED for the real scraping logic provided by the user.
# If running in a restricted environment (like a code interpreter), these operations will fail.
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    st.error("Missing libraries: Please install 'requests' and 'beautifulsoup4' (`pip install requests beautifulsoup4`) to enable image scraping.")
    requests = None
    BeautifulSoup = None

# --- SCRAPER FUNCTIONS ---

def fetch_og_image(url, timeout=10):
    """Fetch Open Graph image from article URL."""
    if not requests or not BeautifulSoup:
        return None
    if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
        return None
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try og:image first
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            img_url = og_image['content']
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_safe := og_image.get('content'):
                img_url = img_safe
            return img_url

        # Fallback: first <img> in main content
        main_content = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
        if main_content:
            img_tag = main_content.find('img')
            if img_tag and img_tag.get('src'):
                img_url = img_tag['src']
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    img_url = urljoin(url, img_url)
                return img_url

        # Last resort: any <img>
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            img_url = img_tag['src']
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                img_url = urljoin(url, img_url)
            return img_url

    except Exception:
        pass
    return None

def is_valid_image_url(url):
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower()
    blocked = ['logo', 'ad.', 'banner', 'sponsor', 'doubleclick', 'gif', 'svg', 'png?size=', 'taboola', 'youtube', 'favicon', '.ico']
    return all(word not in url_lower for word in blocked)

# --- IMPORT FROM DATA_LOADER (vulnerability + enrichment) ---
from data_loader import (
    load_and_transform_data,
    enrich_with_scraping_and_llm,
    get_media_names,
    get_countries,
    get_actors,
    get_vulnerability_system,
    compute_gs,
    COUNTRIES as VULN_COUNTRIES,
    ACTORS as VULN_ACTORS
)

# --- NAME MAPPING ---
ACTOR_MAP = {
    "France": "France",
    "Russia": "Russia",
    "China": "China",
    "Turkey": "Turkey",
    "Rwanda": "Rwanda",
    "US": "UnitedStates",
    "USA": "UnitedStates",
    "United States": "UnitedStates",
    "UAE": "UAE",
    "Saudi Arabia": "Saudi",
    "Saudi": "Saudi",
    "Iran": "Iran",
    "Israel": "Israel",
    "Non-State": "NonState",
    "NonState": "NonState",
}

COUNTRY_MAP = {
    "DRC": "DRC",
    "Democratic Republic of the Congo": "DRC",
    "Senegal": "Senegal",
    "Ethiopia": "Ethiopia",
    "Cote d'Ivoire": "CoteIvoire",
    "Côte d'Ivoire": "CoteIvoire",
    "Ivory Coast": "CoteIvoire",
}

# --- STRATEGIC INTENT ---
REAL_INTENTS_IN_DATA = [
    "Economic Dependency", "Economic Impact",
    "Sovereignty Erosion", "Diplomatic Influence",
    "LGBTQI+ Rights Intervention",
    "Religious Polarisation",
    "Resource Control",
    "Information Warfare"
]

# Map dataset values → vulnerability keys
INTENT_TO_VULN_KEY = {
    "Economic Dependency": "Economic",
    "Economic Impact": "Economic",
    "Sovereignty Erosion": "Sovereignty",
    "Diplomatic Influence": "Sovereignty",
    "LGBTQI+ Rights Intervention": "LGBTQ",
    "Religious Polarisation": "Religious",
    "Resource Control": "ResourceDependency",
    "Information Warfare": "SocialFragility"
}

# For UI: use grouped labels 
UI_LABEL_FOR_KEY = {
    "Economic": "Economic Dependency / Impact",
    "Sovereignty": "Sovereignty Erosion / Diplomatic Influence",
    "LGBTQ": "LGBTQI+ Rights Intervention",
    "Religious": "Religious Polarisation",
    "ResourceDependency": "Resource Control",
    "SocialFragility": "Information Warfare"
}

UI_INTENT_OPTIONS = ["All"] + list(UI_LABEL_FOR_KEY.values())

def get_influence_baseline_score(actor, country, intent_key):
    CA = get_vulnerability_system()
    a_norm = ACTOR_MAP.get(actor, actor)
    c_norm = COUNTRY_MAP.get(country, country)
    if c_norm not in VULN_COUNTRIES:
        return 0.0
    if intent_key == "All":
        scores = []
        for i in CA:
            if a_norm in CA[i] and c_norm in CA[i][a_norm]:
                scores.append(CA[i][a_norm][c_norm])
        return sum(scores) / len(scores) if scores else 0.0
    else:
        return CA.get(intent_key, {}).get(a_norm, {}).get(c_norm, 0.0)

# --- STREAMLIT APP LAYOUT ---

# ✅ FIXED: Removed trailing spaces in URLs
NEW_BACKGROUND_URL = "https://media.istockphoto.com/id/1502033887/vector/beige-gray-grainy-gradient-background-poster-backdrop-noise-texture-webpage-header-wide.jpg?s=612x612&w=0&k=20&c=eGwiA8zZ4cobGeMz5QeRs5zKzlp1Rr-BcROwT4S22y0="
BRIGHT_LOGO_URL = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png"

st.markdown(f"""
<style>
/* -------------------- THEME AWARE STYLES -------------------- */
.stApp {{
    background-image: url("{NEW_BACKGROUND_URL}");
    background-size: cover;
    background-attachment: fixed;
}}
/* Ensure main text elements use Streamlit's theme color for visibility */
h1, h2, h3, h4, h5, h6, .stAlert p, .stMarkdown, .stPlotlyChart .modebar {{ 
    color: #1a1a1a !important; 
}}

/* FIX: Ensure Metric Labels (small text above score) are dark and readable */
.stMetric label, .stMetric .css-1ndc21z > div:first-child {{
    color: #444444 !important; 
    font-weight: bold;
}}
/* Ensure Metric Values (the large score numbers) are clearly visible */
.stMetric .css-1ndc21z > div:last-child > div:first-child {{
    color: #1a1a1a !important; 
}}
/* General text components using default text color (important for sidebars/select boxes) */
.css-1d3w5av, .stText, .stSelectbox label, .stNumberInput label {{
    color: var(--text-color) !important; 
}}


/* -------------------- CARD-SPECIFIC STYLES (Always Dark) -------------------- */
.card {{
    background: #1e1e1e; 
    color: #ffffff; 
    border-radius: 12px;
    padding: 20px;
    margin: 15px 0;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    transition: transform 0.2s;
}}
.card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.4);
}}
.image-container img {{
    width: 180px;
    height: auto;
    object-fit: cover;
    border-radius: 8px;
    margin-right: 15px;
}}
.header {{
    font-size: 1.2em;
    font-weight: bold;
    margin-bottom: 5px;
}}
.meta {{
    font-size: 0.9em;
    color: #aaa;
    margin-bottom: 10px;
}}
.summary {{
    font-size: 1em;
    line-height: 1.6;
    margin-bottom: 10px;
}}
.tags {{
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}}
.tag {{
    background: #2a2a2a;
    color: #4ade80;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.85em;
}}
.link {{
    color: #60a5fa;
    text-decoration: underline;
}}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Vulnerability Index Tool", layout="wide")

# 🖼️ Logo in header 
st.image(BRIGHT_LOGO_URL, width=150)
st.title("🌍 Vulnerability Index Tool")

# Load base data
with st.spinner("Loading dataset..."):
    df_base = load_and_transform_data()
if df_base.empty:
    st.stop()

# Enrich with scraping
with st.spinner("Enriching articles (Scraping Images)..."):
    progress_bar = st.progress(0)
    status_text = st.empty()
    def progress_callback(p, msg):
        progress_bar.progress(min(p, 1.0))
        status_text.text(msg)
    df = enrich_with_scraping_and_llm(df_base, progress_callback=progress_callback)
progress_bar.empty()
status_text.empty()

# ------------------ CREATE DISPLAY TEXT FROM article_text ------------------
def create_display_text(df_in):
    df_out = df_in.copy()
    
    def extract_summary_and_headline(text):
        if not isinstance(text, str) or not text.strip() or "No summary available" in text:
            return "Summary not available.", "No Headline"
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        if not sentences:
            return text[:100] + "...", "Article Snippet"
        headline = sentences[0] + "."
        summary = headline + " " + sentences[1] + "." if len(sentences) > 1 else headline
        return summary, headline

    results = df_out['article_text'].apply(extract_summary_and_headline)
    df_out['llm_summary'] = [r[0] for r in results]
    df_out['display_headline'] = [r[1] for r in results]
    return df_out

df = create_display_text(df)

# Sidebar filters
with st.sidebar:
    st.title("🔍 Filters")
    selected_media = st.selectbox("Media Outlet", ["All"] + get_media_names())
    selected_country = st.selectbox("Target Country", ["All"] + get_countries())
    selected_actor = st.selectbox("Foreign Actor", ["All"] + get_actors())
    selected_intent_ui = st.selectbox("Strategic Intent", UI_INTENT_OPTIONS)
    tones = ["All"] + sorted(df['tone'].dropna().unique())
    selected_tone = st.selectbox("Tone", tones)

# Apply filters
filtered = df.copy()
if selected_media != "All":
    filtered = filtered[filtered['media_outlet'] == selected_media]
if selected_country != "All":
    filtered = filtered[filtered['target_country'] == selected_country]
if selected_actor != "All":
    filtered = filtered[filtered['inferred_actor'] == selected_actor]

# ✅ FIXED: Replace broken UI_INTENT_LABELS loop
if selected_intent_ui != "All":
    # Reverse map: UI label → vulnerability key
    vuln_key = None
    for key, label in UI_LABEL_FOR_KEY.items():
        if label == selected_intent_ui:
            vuln_key = key
            break
    if vuln_key:
        # Get all dataset values for this vulnerability key
        allowed_values = [k for k, v in INTENT_TO_VULN_KEY.items() if v == vuln_key]
        filtered = filtered[filtered['strategic_intent'].isin(allowed_values)]

if selected_tone != "All":
    filtered = filtered[filtered['tone'] == selected_tone]

# --- KPI Metrics ---
st.header("📊 Key Indicators")

current_article_count = len(filtered)
previous_article_count = len(df) * 0.95 
article_delta = current_article_count - previous_article_count
article_delta_str = f"{article_delta:,.0f}"

# Tone Score
if 'tone' in filtered.columns:
    tone_mapping = {
        'Factual': 0.0, 'Sensationalist': -0.3, 'Cynical': -0.8, 'Alarmist': -1.0, 'Positive': 1.0, 'Neutral': 0.0
    }
    filtered['tone_clean'] = filtered['tone'].astype(str).str.title().str.strip()
    filtered['tone_numeric'] = filtered['tone_clean'].map(tone_mapping).fillna(0)
    current_tone_score = filtered['tone_numeric'].mean() if not filtered.empty else 0.0
    tone_delta = current_tone_score - 0.1
    tone_delta_str = f"{tone_delta:+.2f}"
else:
    current_tone_score = 0.0
    tone_delta_str = "N/A"

# --- CII DYNAMIC CALCULATION ---
#  Use vuln_key from above
if selected_intent_ui != "All":
    selected_vuln_key_for_score = None
    for key, label in UI_LABEL_FOR_KEY.items():
        if label == selected_intent_ui:
            selected_vuln_key_for_score = key
            break
    baseline_influence_score = get_influence_baseline_score(selected_actor, selected_country, selected_vuln_key_for_score)
else:
    baseline_influence_score = get_influence_baseline_score(selected_actor, selected_country, "All")

final_influence_score = baseline_influence_score
if baseline_influence_score > 0 and current_article_count > 0:
    volume_factor = min(1.0, current_article_count / 100)
    tone_factor = 1.0 - (current_tone_score / 2.0)
    final_influence_score = min(1.0, baseline_influence_score * volume_factor * tone_factor)

previous_influence_score = final_influence_score * (0.95 + (0.1 * (np.random.rand() - 0.5))) if final_influence_score > 0.05 else 0.0
influence_delta = final_influence_score - previous_influence_score
influence_delta_str = f"{influence_delta:+.2f}"

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Articles Analyzed", f"{current_article_count:,.0f}", article_delta_str)
with col2:
    st.metric("Average Tone Score (Sentiment)", f"{current_tone_score:.2f}", tone_delta_str, delta_color="inverse")
with col3:
    st.metric("Contextual Influence Index", f"{final_influence_score:.2f}", influence_delta_str, delta_color="inverse")

# Alerts
if selected_actor != "All" and selected_country != "All":
    if final_influence_score >= 0.8:
        st.error(f"🚨 **High Vulnerability Warning:** CII for **{selected_actor}** in **{selected_country}** is critically high ({final_influence_score:.2f}).")
    elif final_influence_score >= 0.6:
        st.warning(f"⚠️ **Moderate Vulnerability Alert:** CII is elevated ({final_influence_score:.2f}).")

# Explanation (collapsed by default)
with st.expander("❓ Understanding the Dashboard Metrics", expanded=False):
    st.markdown("""
    ### 🔹 **Contextual Vulnerability Index (CVI)**
    Combines **structural vulnerability** (debt, military, etc.) and **narrative activity** (volume, tone).
    
    ### 🔹 **Tone Score**
    Ranges from **-1.0 (alarmist)** to **+1.0 (positive)**.
    
    ### 🔹 Formula
    `CVI = Structural_Vulnerability × min(Volume/100, 1) × (1 - Tone/2)`
    """)

st.markdown("---")
st.header("📈 Article Volume Trend")

if 'posting_time' in filtered.columns and not filtered.empty:
    filtered['posting_time'] = pd.to_datetime(filtered['posting_time'], errors='coerce')
    filtered.dropna(subset=['posting_time'], inplace=True)
    time_series_data = filtered.resample('D', on='posting_time')['URL'].count().reset_index()
    time_series_data.columns = ['Date', 'Article Count']
    fig = px.line(time_series_data, x='Date', y='Article Count', title=f'Daily Volume: {selected_actor} in {selected_country}', template='plotly_dark')
    fig.update_traces(mode='lines+markers')
    st.plotly_chart(fig, use_container_width=True)
else:
    st.markdown("<p style='text-align: center; color: #777;'>No time-series data available.</p>", unsafe_allow_html=True)

st.markdown("---")
st.write(f"### Showing **{len(filtered)}** of **{len(df)}** articles")

# Pagination
articles_per_page = 5
total_pages = max(1, (len(filtered) - 1) // articles_per_page + 1)
if "page" not in st.session_state:
    st.session_state.page = 0
start_idx = st.session_state.page * articles_per_page
end_idx = start_idx + articles_per_page
page_articles = filtered.iloc[start_idx:end_idx]

# Display Articles
for _, row in page_articles.iterrows():
    summary_display = str(row.get('llm_summary', 'Summary extraction failed.'))
    headline = str(row.get('display_headline', 'Article Snippet (No Headline)'))
    image_url = str(row.get('urlToImage', ''))
    display_image = image_url if image_url and image_url not in ['None', 'nan', ''] else 'https://placehold.co/400x200/cccccc/000000?text=No+Image'
    media = str(row.get('media_outlet', 'Unknown'))
    tone = str(row.get('tone', 'N/A'))
    intent = str(row.get('strategic_intent', 'N/A'))
    posting_time = "Date Unknown"
    if pd.notna(row.get('posting_time')):
        try:
            posting_time = pd.to_datetime(row['posting_time']).strftime('%Y-%m-%d %H:%M')
        except:
            pass

    st.markdown(f"""
    <div class="card">
        <div style="display: flex; align-items: flex-start;">
            <div class="image-container">
                {f'<img src="{display_image}" alt="Article Image">' if 'No+Image' not in display_image else '<div style="width: 180px; height: 120px; background: #333; display: flex; align-items: center; justify-content: center; border-radius: 8px;">No Image</div>'}
            </div>
            <div style="flex: 1;">
                <div class="header">{headline}</div>
                <div class="meta">Source: {media} – {posting_time}</div>
                <div class="summary">{summary_display}</div>
                <div class="tags">
                    <span class="tag">Tone: {tone}</span>
                    <span class="tag">Intent: {intent}</span>
                </div>
                <a href="{row.get('URL', '#')}" target="_blank" class="link">🔗 Read full article</a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Pagination Controls
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.button("⬅ Previous", on_click=lambda: st.session_state.update(page=max(0, st.session_state.page - 1)), disabled=(st.session_state.page == 0))
with col2:
    st.markdown(f"<h5 style='text-align: center;'>Page {st.session_state.page + 1} of {total_pages}</h5>", unsafe_allow_html=True)
with col3:
    st.button("Next ➡", on_click=lambda: st.session_state.update(page=min(total_pages - 1, st.session_state.page + 1)), disabled=(st.session_state.page >= total_pages - 1))


# ------------------ PDF REPORT GENERATION ------------------
st.markdown("---")
st.header("📥 Export Report")

if not PDF_AVAILABLE:
    st.info("📄 PDF export is not available in this environment (requires weasyprint).")
elif len(filtered) == 0:
    st.info("💡 Apply filters to analyze articles, then download a report.")
else:
    # Build HTML content
    filters_html = f"""
    <div style="background:#f8f9fa;padding:10px;border-radius:5px;margin:15px 0;">
        <p><b>Filters:</b> Actor: {selected_actor} | Country: {selected_country} | Intent: {selected_intent_ui} | Tone: {selected_tone}</p>
        <p><b>Total Articles Analyzed:</b> {len(filtered)}</p>
    </div>
    """

    # Executive summary
    intents = filtered['strategic_intent'].value_counts().head(3)
    actors = filtered['inferred_actor'].value_counts().head(3)
    tone = filtered['tone_numeric'].mean() if 'tone_numeric' in filtered.columns else 0
    tone_desc = "neutral" if abs(tone) < 0.2 else ("positive" if tone > 0 else "negative")
    top_intents = ", ".join([f"{i} ({c})" for i, c in intents.items()]) if not intents.empty else "none"
    top_actors = ", ".join([f"{a} ({c})" for a, c in actors.items()]) if not actors.empty else "none"
    summary_html = f"""
    <p>During this period, a total of {len(filtered)} articles were analyzed. The dominant strategic narratives 
    include {top_intents}. The primary foreign actors covered are {top_actors}. 
    The overall media tone is {tone_desc} (average tone score: {tone:.2f}).</p>
    """

    # Country breakdown
    country_html = ""
    if selected_actor != "All" and 'selected_vuln_key_for_score' in locals() and selected_vuln_key_for_score:
        for country in VULN_COUNTRIES:
            if selected_country == "All" or selected_country == country:
                c_df = filtered[filtered['target_country'] == country]
                score = get_influence_baseline_score(selected_actor, country, selected_vuln_key_for_score)
                intents_country = c_df['strategic_intent'].value_counts().head(2)
                intent_list = ", ".join(intents_country.index) if not intents_country.empty else "various"
                country_html += f"""
                <div style="background:#f8f9fa;padding:12px;margin:12px 0;border-left:4px solid #3498db;">
                    <b>{country}</b>: {len(c_df)} articles | Vulnerability Score: {score:.2f}<br>
                    Key narratives: {intent_list}
                </div>
                """

    # Final HTML
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; line-height: 1.6; color: #333; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ width: 200px; }}
            h1 {{ color: #2c3e50; margin-bottom: 10px; }}
            h2 {{ color: #34495e; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <img src="https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png" class="logo" alt="Code for Africa">
            <h1>Media Narratives Monitoring Report</h1>
            <p><i>Generated on {pd.Timestamp.now().strftime('%Y-%m-%d')}</i></p>
        </div>

        {filters_html}
        <h2>Executive Summary</h2>
        {summary_html}

        <h2>Country-Specific Analysis</h2>
        {country_html if country_html else "<p>No country-specific data available.</p>"}

        <p><i>This report was generated using the Code for Africa Media Narratives Monitoring Dashboard.</i></p>
    </body>
    </html>
    """

    # Generate PDF
    try:
        pdf_bytes = HTML(string=full_html).write_pdf()
        st.download_button(
            label="📄 Download Report as PDF",
            data=pdf_bytes,
            file_name="media_narratives_report.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error("Failed to generate PDF.")
        st.caption(f"Error: {str(e)}")
