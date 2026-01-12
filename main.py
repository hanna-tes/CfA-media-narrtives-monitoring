import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np 
from urllib.parse import urlparse, urljoin

# --- MUST BE THE FIRST STREAMLIT COMMAND ---
st.set_page_config(page_title="Vulnerability Index Tool", layout="wide")

try:
    from weasyprint import HTML
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    st.error("Missing libraries: Please install 'requests' and 'beautifulsoup4' to enable image scraping.")
    requests = None
    BeautifulSoup = None

# --- SCRAPER FUNCTIONS ---

def fetch_og_image(url, timeout=10):
    if not requests or not BeautifulSoup:
        return None
    if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
        return None
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            img_url = og_image['content']
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            return img_url

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
    except Exception:
        pass
    return None

def is_valid_image_url(url):
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower()
    blocked = ['logo', 'ad.', 'banner', 'sponsor', 'doubleclick', 'gif', 'svg', 'png?size=', 'taboola', 'youtube', 'favicon', '.ico']
    return all(word not in url_lower for word in blocked)

# --- DATA IMPORTS ---
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
from search_engine import initialize_search_engine, HybridSearchEngine

# --- MAPPINGS ---
ACTOR_MAP = {
    "France": "France", "Russia": "Russia", "China": "China", "Turkey": "Turkey",
    "Rwanda": "Rwanda", "US": "UnitedStates", "USA": "UnitedStates", "United States": "UnitedStates",
    "UAE": "UAE", "Saudi Arabia": "Saudi", "Saudi": "Saudi", "Iran": "Iran",
    "Israel": "Israel", "Non-State": "NonState", "NonState": "NonState",
}

COUNTRY_MAP = {
    "DRC": "DRC", "Democratic Republic of the Congo": "DRC", "Senegal": "Senegal",
    "Ethiopia": "Ethiopia", "Cote d'Ivoire": "CoteIvoire", "Côte d'Ivoire": "CoteIvoire",
    "Ivory Coast": "CoteIvoire",
}

INTENT_TO_VULN_KEY = {
    "Economic Dependency": "Economic", "Economic Impact": "Economic",
    "Sovereignty Erosion": "Sovereignty", "Diplomatic Influence": "Sovereignty",
    "LGBTQI+ Rights Intervention": "LGBTQ", "Religious Polarisation": "Religious",
    "Resource Control": "ResourceDependency", "Information Warfare": "SocialFragility"
}

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
        scores = [CA[i][a_norm][c_norm] for i in CA if a_norm in CA[i] and c_norm in CA[i][a_norm]]
        return sum(scores) / len(scores) if scores else 0.0
    return CA.get(intent_key, {}).get(a_norm, {}).get(c_norm, 0.0)

# --- UI ASSETS ---
NEW_BACKGROUND_URL = "https://media.istockphoto.com/id/1502033887/vector/beige-gray-grainy-gradient-background-poster-backdrop-noise-texture-webpage-header-wide.jpg?s=612x612&w=0&k=20&c=eGwiA8zZ4cobGeMz5QeRs5zKzlp1Rr-BcROwT4S22y0="
BRIGHT_LOGO_URL = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png"

# --- CUSTOM CSS ---
st.markdown(f"""
<style>
.stApp {{
    background-image: url("{NEW_BACKGROUND_URL}");
    background-size: cover;
    background-attachment: fixed;
}}

h1, h2, h3, .stMarkdown {{ color: #1a1a1a !important; }}

.professional-header {{
    display: flex;
    align-items: center;
    gap: 15px;
    padding: 20px 0;
    margin-bottom: 10px;
    border-bottom: 1px solid rgba(0,0,0,0.1);
}}

.chat-container {{
    background: rgba(255, 255, 255, 0.2);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-radius: 18px;
    padding: 25px;
    margin: 20px 0;
    border: none !important;
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
}}

.card {{
    background: #1e1e1e; 
    color: #ffffff; 
    border-radius: 12px;
    padding: 20px;
    margin: 15px 0;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}}

.tag {{
    background: #2a2a2a;
    color: #4ade80;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.85em;
}}

.link {{ color: #60a5fa; text-decoration: underline; }}

.stMetric label {{ color: #444 !important; font-weight: bold; }}
</style>
""", unsafe_allow_html=True)

# --- DATA LOADING ---
with st.spinner("Loading dataset..."):
    df_base = load_and_transform_data()
if df_base.empty:
    st.stop()

with st.spinner("Enriching articles..."):
    progress_bar = st.progress(0)
    status_text = st.empty()
    df = enrich_with_scraping_and_llm(df_base, progress_callback=lambda p, m: (progress_bar.progress(min(p, 1.0)), status_text.text(m)))
progress_bar.empty()
status_text.empty()

def create_display_text(df_in):
    df_out = df_in.copy()
    def extract_summary_and_headline(text):
        if not isinstance(text, str) or not text.strip() or "No summary available" in text:
            return "Summary not available.", "No Headline"
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        headline = sentences[0] + "." if sentences else "Article Snippet"
        summary = headline + " " + sentences[1] + "." if len(sentences) > 1 else headline
        return summary, headline
    results = df_out['article_text'].apply(extract_summary_and_headline)
    df_out['llm_summary'] = [r[0] for r in results]
    df_out['display_headline'] = [r[1] for r in results]
    return df_out

df = create_display_text(df)

if 'search_engine' not in st.session_state:
    st.session_state.search_engine = initialize_search_engine(df)

# --- PROFESSIONAL HEADER & CHATBOT ---
st.markdown(f"""
<div class="professional-header">
    <img src="{BRIGHT_LOGO_URL}" width="45" height="45">
    <h2 style="margin:0; font-weight: 700; color: #1a1a1a;">Insights & Analysis</h2>
</div>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.container():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for message in st.session_state.messages:
        avatar = BRIGHT_LOGO_URL if message["role"] == "assistant" else None
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question about the data..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar=BRIGHT_LOGO_URL):
            with st.spinner("Analyzing..."):
                try:
                    search_engine_instance = st.session_state.search_engine
                    context_from_search = search_engine_instance.get_context_for_llm(prompt, top_k=5)
                    from groq import Groq
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    messages = [
                        {"role": "system", "content": "You are an expert analyst. Answer the user query using the provided context."},
                        {"role": "user", "content": f"Context:\n{context_from_search}\n\nQuery: '{prompt}'"}
                    ]
                    chat_completion = client.chat.completions.create(
                        messages=messages, model="llama-3.1-8b-instant", temperature=0.3, max_tokens=1024,
                    )
                    llm_response = chat_completion.choices[0].message.content
                    st.markdown(llm_response)
                    st.session_state.messages.append({"role": "assistant", "content": llm_response})
                except Exception as e:
                    st.error(f"Error: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.image(BRIGHT_LOGO_URL, width=150)
    st.title("🔍 Filters")
    selected_media = st.selectbox("Media Outlet", ["All"] + get_media_names())
    selected_country = st.selectbox("Target Country", ["All"] + get_countries())
    selected_actor = st.selectbox("Foreign Actor", ["All"] + get_actors())
    selected_intent_ui = st.selectbox("Strategic Intent", UI_INTENT_OPTIONS)
    selected_tone = st.selectbox("Tone", ["All"] + sorted(df['tone'].dropna().unique()))

# Apply Filters
filtered = df.copy()
if selected_media != "All": filtered = filtered[filtered['media_outlet'] == selected_media]
if selected_country != "All": filtered = filtered[filtered['target_country'] == selected_country]
if selected_actor != "All": filtered = filtered[filtered['inferred_actor'] == selected_actor]
if selected_intent_ui != "All":
    vuln_key = next((k for k, v in UI_LABEL_FOR_KEY.items() if v == selected_intent_ui), None)
    if vuln_key:
        allowed_values = [k for k, v in INTENT_TO_VULN_KEY.items() if v == vuln_key]
        filtered = filtered[filtered['strategic_intent'].isin(allowed_values)]
if selected_tone != "All": filtered = filtered[filtered['tone'] == selected_tone]

# --- KPI METRICS ---
st.header("📊 Dashboard Indicators")
col1, col2, col3 = st.columns(3)

tone_mapping = {'Factual': 0.0, 'Sensationalist': -0.3, 'Cynical': -0.8, 'Alarmist': -1.0, 'Positive': 1.0, 'Neutral': 0.0}
filtered['tone_numeric'] = filtered['tone'].astype(str).str.title().str.strip().map(tone_mapping).fillna(0)
current_tone_score = filtered['tone_numeric'].mean() if not filtered.empty else 0.0

vuln_key_for_score = next((k for k, v in UI_LABEL_FOR_KEY.items() if v == selected_intent_ui), "All")
baseline_score = get_influence_baseline_score(selected_actor, selected_country, vuln_key_for_score)
final_cii = min(1.0, baseline_score * min(1.0, len(filtered)/100) * (1.0 - (current_tone_score/2.0)))

with col1: st.metric("Total Articles", f"{len(filtered):,}")
with col2: st.metric("Average Tone Score", f"{current_tone_score:.2f}")
with col3: st.metric("Vulnerability Index (CII)", f"{final_cii:.2f}")

# --- FANCY TRANSPARENT TREND CHART ---
st.markdown("---")
if 'posting_time' in filtered.columns and not filtered.empty:
    filtered['posting_time'] = pd.to_datetime(filtered['posting_time'], errors='coerce')
    time_series = filtered.dropna(subset=['posting_time']).resample('D', on='posting_time')['URL'].count().reset_index()
    time_series.columns = ['Date', 'Count']
    
    # Customizing the chart to match the Glassmorphism UI
    fig = px.line(time_series, x='Date', y='Count', title="Article Volume Trend")
    fig.update_traces(line_color='#2E86AB', line_width=3, mode='lines+markers', marker=dict(size=8, color='#4ade80'))
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#1a1a1a',
        xaxis=dict(showgrid=False, title="Date"),
        yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)', title="Article Count"),
        margin=dict(l=20, r=20, t=50, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- ARTICLE FEED ---
st.markdown("---")
st.write(f"### Article Feed ({len(filtered)})")

articles_per_page = 5
total_pages = max(1, (len(filtered) - 1) // articles_per_page + 1)
if "page" not in st.session_state: st.session_state.page = 0
start_idx = st.session_state.page * articles_per_page
page_articles = filtered.iloc[start_idx:start_idx + articles_per_page]

for _, row in page_articles.iterrows():
    img_url = row.get('urlToImage', 'https://placehold.co/400x200/cccccc/000000?text=No+Image')
    st.markdown(f"""
    <div class="card">
        <div style="display: flex; gap: 20px;">
            <img src="{img_url}" style="width: 170px; height: 110px; object-fit: cover; border-radius: 8px;">
            <div style="flex: 1;">
                <div style="font-weight: bold; font-size: 1.1em; margin-bottom: 5px;">{row.get('display_headline')}</div>
                <div style="font-size: 0.85em; color: #aaa; margin-bottom: 10px;">Source: {row.get('media_outlet')}</div>
                <div style="font-size: 0.95em; margin-bottom: 10px;">{row.get('llm_summary')}</div>
                <div style="display: flex; gap: 10px;">
                    <span class="tag">Tone: {row.get('tone')}</span>
                    <span class="tag">Intent: {row.get('strategic_intent')}</span>
                </div>
                <br><a href="{row.get('URL', '#')}" target="_blank" class="link">Read More 🔗</a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 2, 1])
if c1.button("⬅ Previous", disabled=st.session_state.page == 0):
    st.session_state.page -= 1
    st.rerun()
c2.markdown(f"<p style='text-align: center;'>Page {st.session_state.page + 1} of {total_pages}</p>", unsafe_allow_html=True)
if c3.button("Next ➡", disabled=st.session_state.page >= total_pages - 1):
    st.session_state.page += 1
    st.rerun()
