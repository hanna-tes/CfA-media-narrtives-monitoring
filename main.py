import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np 
from urllib.parse import urlparse, urljoin

# NOTE: The following libraries are REQUIRED for the real scraping logic provided by the user.
# If running in a restricted environment (like a code interpreter), these operations will fail.
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    st.error("Missing libraries: Please install 'requests' and 'beautifulsoup4' (`pip install requests beautifulsoup4`) to enable image scraping.")
    requests = None
    BeautifulSoup = None

# --- SCRAPER FUNCTIONS (Provided by User) ---

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

# --- MOCK PLACEHOLDERS FOR CONTEXTUAL INFLUENCE MODEL (CA, G, R) ---
INTENT_FACTORS = {
    'Diplomatic Pressure': {'Economic Dependency': 0.7, 'Security Dependency': 0.3},
    'Economic Coercion': {'Economic Dependency': 0.9, 'Resource Dependence': 0.5},
    'Information Warfare': {'Social Fragility': 0.8, 'Media Literacy': 0.2},
    'Security Dependency': {'Military Presence': 0.9, 'Debt Vulnerability': 0.4}
}

def mock_compute_gs():
    return {
        'Senegal': {'Debt Vulnerability': 0.6, 'Military Presence': 0.3, 'Resource Dependence': 0.5, 'Social Fragility': 0.4, 'Media Literacy': 0.5, 'Economic Dependency': 0.7},
        'Ethiopia': {'Debt Vulnerability': 0.9, 'Military Presence': 0.7, 'Resource Dependence': 0.8, 'Social Fragility': 0.9, 'Media Literacy': 0.4, 'Economic Dependency': 0.6},
        'Nigeria': {'Debt Vulnerability': 0.5, 'Military Presence': 0.4, 'Resource Dependence': 0.9, 'Social Fragility': 0.8, 'Media Literacy': 0.6, 'Economic Dependency': 0.5},
    }

def mock_compute_R(g):
    actors = ['China', 'Rwanda', 'Turkey', 'Russia']
    countries = list(g.keys())
    R_mock = {}
    for intent in INTENT_FACTORS:
        R_mock[intent] = {}
        for actor in actors:
            R_mock[intent][actor] = {}
            for country in countries:
                R_mock[intent][actor][country] = np.random.rand() * 0.8 + 0.1
    return R_mock

def mock_compute_CAs(g, R):
    CA_mock = {}
    actors = ['China', 'Rwanda', 'Turkey', 'Russia']
    for intent, factors in INTENT_FACTORS.items():
        CA_mock[intent] = {}
        for actor in actors:
            CA_mock[intent][actor] = {}
            for country, g_factors in g.items():
                total_weighted_vulnerability = 0
                max_possible_score = 0
                r_val = R[intent][actor][country]
                for factor, weight in factors.items():
                    g_val = g_factors.get(factor, 0)
                    total_weighted_vulnerability += (r_val * g_val * weight)
                    max_possible_score += (1.0 * 1.0 * weight)
                score = min(total_weighted_vulnerability / (max_possible_score if max_possible_score > 0 else 1.0), 1.0)
                CA_mock[intent][actor][country] = score
    return CA_mock

g = mock_compute_gs()
R = mock_compute_R(g)
CA = mock_compute_CAs(g,R)

# --- DATA LOADER AND ENRICHMENT FUNCTIONS ---

@st.cache_data
def load_and_transform_data():
    try:
        df = pd.read_csv("Merged_dataset_sample.csv")
    except FileNotFoundError:
        st.error("Error: 'Merged_dataset_sample.csv' not found.")
        return pd.DataFrame()
        
    df['posting_time'] = pd.to_datetime(df['posting_time'], errors='coerce')
    required_cols = ['media_outlet', 'inferred_actor', 'strategic_intent', 'tone', 'target_country', 'URL', 'article_text', 'urlToImage']
    for col in required_cols:
        if col not in df.columns:
            df[col] = np.nan
            
    return df.dropna(subset=['article_text'])

def get_media_names(): return ['Rnanews', 'Rfi', 'A News', 'Yeni Şafak']
def get_countries(): return ['Senegal', 'Ethiopia', 'Nigeria', 'DRC']
def get_actors(): return ['Rwanda', 'France', 'Turkey', 'China', 'Russia']

def enrich_with_scraping_and_llm(df, progress_callback=None):
    if 'scraped_data' not in st.session_state:
        st.session_state.scraped_data = {'url_to_image': {}}
        
    scraped_image = st.session_state.scraped_data['url_to_image']

    # Identify URLs needing image scraping
    # This assumes 'urlToImage' is empty/NaN if scraping hasn't happened.
    needs_image = df['urlToImage'].isna() & df['URL'].notnull() 
    urls_to_fetch = df[needs_image]['URL'].dropna().unique()

    if len(urls_to_fetch) > 0:
        total = len(urls_to_fetch)
        for i, url in enumerate(urls_to_fetch):
            if url not in scraped_image:
                # Scrape real image
                img_url = fetch_og_image(url)
                
                # Validate and fallback to Clearbit logo if needed
                if not is_valid_image_url(img_url):
                    try:
                        domain = urlparse(url).netloc.replace('www.', '', 1)
                        img_url = f"https://logo.clearbit.com/{domain}"
                    except:
                        img_url = None
                
                scraped_image[url] = img_url

            if progress_callback:
                progress_callback(min(1.0, (i + 1) / total), f"Scraping images: {i+1}/{total}...")

        st.session_state.scraped_data['url_to_image'] = scraped_image

    # Map images back to DataFrame
    df['urlToImage'] = df['URL'].map(scraped_image).fillna(df['urlToImage'])
    
    # Final safety net for display
    df['urlToImage'] = df['urlToImage'].fillna('https://placehold.co/400x200/cccccc/000000?text=No+Image')
    return df

@st.cache_data
def create_display_text(df_in):
    df_out = df_in.copy()
    
    def extract_summary_and_headline(text):
        if not isinstance(text, str) or not text.strip():
            return 'Summary extraction pending or failed.', 'Article Snippet (No Text)'
        
        headline_match = re.search(r'[^.?!]*[.?!]', text)
        headline = headline_match.group(0).strip() if headline_match else 'Article Snippet'
        
        if headline_match:
            text_after_first = text[headline_match.end():]
            second_sentence_match = re.search(r'[^.?!]*[.?!]', text_after_first)
            
            if second_sentence_match and headline_match.end() + second_sentence_match.end() < 500:
                summary = headline + " " + second_sentence_match.group(0).strip()
            else:
                summary = headline
        else:
            summary = text[:200].strip() + '...'
            
        return summary, headline

    results = df_out['article_text'].fillna('').apply(lambda x: extract_summary_and_headline(x))
    df_out['llm_summary'] = [r[0] for r in results]
    df_out['display_headline'] = [r[1] for r in results]
    
    return df_out


# --- STREAMLIT APP LAYOUT ---

NEW_BACKGROUND_URL = "https://media.istockphoto.com/id/1502033887/vector/beige-gray-grainy-gradient-background-poster-backdrop-noise-texture-webpage-header-wide.jpg?s=612x612&w=0&k=20&c=eGwiA8zZ4cobGeMz5QeRs5zKzlp1Rr-BcROwT4S22y0=" 
BRIGHT_LOGO_URL = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png"

# 🎨 Custom CSS for theme-aware dark cards AND READABILITY FIX
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
    # df now includes the 'urlToImage' column populated by the scraper
    df = enrich_with_scraping_and_llm(df_base, progress_callback=progress_callback)
progress_bar.empty()
status_text.empty()

df = create_display_text(df)

# Sidebar filters
with st.sidebar:
    st.title("🔍 Filters")
    selected_media = st.selectbox("Media Outlet", ["All"] + get_media_names())
    selected_country = st.selectbox("Target Country", ["All"] + get_countries())
    selected_actor = st.selectbox("Foreign Actor", ["All"] + get_actors())
    
    intents = ["All"] + sorted(INTENT_FACTORS.keys())
    selected_intent = st.selectbox("Strategic Intent", intents)
    
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
if selected_intent != "All":
    filtered = filtered[filtered['strategic_intent'] == selected_intent]
if selected_tone != "All":
    filtered = filtered[filtered['tone'] == selected_tone]

# Influence Index Logic (Baseline Structural Vulnerability Lookup)
@st.cache_data
def get_influence_baseline_score(actor, country, intent):
    if actor == "All" or country == "All" or not CA:
        return 0.0 
        
    actor_normalized = actor.title()
    country_normalized = country.title()
    
    # Handle acronyms/exceptions
    if actor.upper() in ['UAE', 'DRC']: actor_normalized = actor.upper()
    if country.upper() in ['UAE', 'DRC', 'ROC']: country_normalized = country.upper()
    
    if intent != "All":
        score = CA.get(intent, {}).get(actor_normalized, {}).get(country_normalized, 0.0)
        return score
    
    scores = []
    for i in CA:
         score = CA[i].get(actor_normalized, {}).get(country_normalized, 0.0)
         if score is not None:
             scores.append(score)

    return sum(scores) / len(scores) if scores else 0.0


# --- 1. KPI Metrics ---
st.header("📊 Key Indicators")

# Calculate KPIs
current_article_count = len(filtered)
previous_article_count = len(df) * 0.95 
article_delta = current_article_count - previous_article_count
article_delta_str = f"{article_delta:,.0f}"

# Tone Score calculation (required for dynamic CII)
if 'tone' in filtered.columns:
    tone_mapping = {
        'Factual': 0.0, 'Sensationalist': -0.3, 'Cynical': -0.8, 'Alarmist': -1.0, 'Positive': 1.0, 'Neutral': 0.0
    }
    filtered['tone_clean'] = filtered['tone'].astype(str).str.title().str.strip()
    filtered['tone_numeric'] = filtered['tone_clean'].map(tone_mapping).fillna(0)
    
    current_tone_score = filtered['tone_numeric'].mean() if not filtered.empty else 0.0
    previous_tone_score = 0.1 
    tone_delta = current_tone_score - previous_tone_score
    tone_delta_str = f"{tone_delta:+.2f}"
else:
    current_tone_score = 0.0
    tone_delta_str = "N/A"

# --- CII DYNAMIC CALCULATION ---
baseline_influence_score = get_influence_baseline_score(selected_actor, selected_country, selected_intent)
final_influence_score = baseline_influence_score

if baseline_influence_score > 0 and current_article_count > 0:
    # 1. Volume Factor: Max articles = 100 for normalization (0.0 to 1.0)
    volume_factor = min(1.0, current_article_count / 100)
    
    # 2. Tone Factor: Makes negative tone increase vulnerability score. 
    tone_factor = 1.0 - (current_tone_score / 2.0)

    # 3. Dynamic Adjustment: Blend the structural vulnerability with the current narrative activity.
    dynamic_modulation_factor = (volume_factor * tone_factor) 
    
    final_influence_score = min(1.0, baseline_influence_score * dynamic_modulation_factor)

# Recalculate Delta based on the final score
previous_influence_score = final_influence_score * (0.95 + (0.1 * (np.random.rand() - 0.5))) if final_influence_score > 0.05 else 0.0
influence_delta = final_influence_score - previous_influence_score
influence_delta_str = f"{influence_delta:+.2f}"

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Total Articles Analyzed",
        value=f"{current_article_count:,.0f}",
        delta=article_delta_str,
        delta_color="normal" 
    )

with col2:
    st.metric(
        label="Average Tone Score (Sentiment)",
        value=f"{current_tone_score:.2f}",
        delta=tone_delta_str,
        delta_color="inverse" 
    )

with col3:
    st.metric(
        label="Contextual Influence Index",
        value=f"{final_influence_score:.2f}",
        delta=influence_delta_str,
        delta_color="inverse"
    )

# Alert if Influence Index is high 
if selected_actor != "All" and selected_country != "All":
    if final_influence_score > 0.6 and final_influence_score < 0.8:
        st.warning(f"⚠️ **Moderate Vulnerability Alert:** The Contextual Influence Index for **{selected_actor}** in **{selected_country}** is elevated ({final_influence_score:.2f}).")
    elif final_influence_score >= 0.8:
        st.error(f"🚨 **High Vulnerability Warning:** The Contextual Influence Index for **{selected_actor}** in **{selected_country}** is critically high ({final_influence_score:.2f}).")


# --- Metric Explanation Section ---
st.markdown("<br>", unsafe_allow_html=True)

with st.expander("❓ Understanding the Dashboard Metrics (Click to Expand)", expanded=False):
    st.markdown("---")
    
    st.markdown("#### 1. Average Tone Score (Sentiment)")
    st.markdown(
        """
        This score measures the overall **journalistic framing and emotional valence** of the filtered articles. 
        It is tuned to your specific set of journalistic tone categories, ranging from **-1.0 (Critically Negative)** to **+1.0 (Highly Positive)**.
        """
    )
    
    st.markdown("##### CII Components (The Risk Formula):")
    st.markdown(
        """
        1.  **Structural Vulnerability (G-Factor):** **Why the country is weak.** (The static baseline component.)
        2.  **Narrative Amplification (R-Factor):** **What the actor is doing.** (The dynamic component, calculated from article volume and tone.)
        
        A high CII means the actor's efforts are landing on highly vulnerable ground.
        """
    )
    st.markdown("")

    
st.markdown("---")

# --- 2. Time-Series Trend Analysis ---
st.header("📈 Article Volume Trend")

if 'posting_time' in filtered.columns and not filtered.empty:
    
    filtered['posting_time'] = pd.to_datetime(filtered['posting_time'], errors='coerce')
    filtered.dropna(subset=['posting_time'], inplace=True)
    
    time_series_data = filtered.resample('D', on='posting_time')['URL'].count().reset_index()
    time_series_data.columns = ['Date', 'Article Count']
    
    fig = px.line(
        time_series_data,
        x='Date',
        y='Article Count',
        title=f'Daily Article Volume for {selected_actor} in {selected_country}',
        labels={'Article Count': 'Number of Articles'},
        template='plotly_dark' 
    )
    
    fig.update_traces(mode='lines+markers', marker_size=5)
    fig.update_layout(hovermode="x unified", title_x=0.5)
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.markdown("<p style='text-align: center; color: #777;'>No time-series trend data available based on current filters.</p>", unsafe_allow_html=True)

st.markdown("---")
st.write(f"### Showing **{len(filtered)}** of **{len(df)}** articles")


# Pagination (5 per page)
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
    
    # READS the image URL from the 'urlToImage' column (populated by the scraper above)
    image_url = str(row.get('urlToImage', None)) 
    media = str(row.get('media_outlet', 'Unknown'))
    tone = str(row.get('tone', 'N/A'))
    intent = str(row.get('strategic_intent', 'N/A'))
    
    posting_time = "Date Unknown"
    if pd.notna(row.get('posting_time')):
        try:
            if isinstance(row['posting_time'], pd.Timestamp):
                 posting_time = row['posting_time'].strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass

    # Image rendering logic
    display_image = image_url if image_url and image_url not in ['None', 'nan'] else 'https://placehold.co/400x200/cccccc/000000?text=No+Image'

    # 🎨 Render Card
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

# Pagination Controls (at bottom)
st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅ Previous", on_click=lambda: st.session_state.update(page=max(0, st.session_state.page - 1)), disabled=(st.session_state.page == 0)):
        pass
with col2:
    st.markdown(f"<h5 style='text-align: center; color: var(--text-color);'>Page {st.session_state.page + 1} of {total_pages}</h5>", unsafe_allow_html=True)
with col3:
    if st.button("Next ➡", on_click=lambda: st.session_state.update(page=min(total_pages - 1, st.session_state.page + 1)), disabled=(st.session_state.page >= total_pages - 1)):
        pass
