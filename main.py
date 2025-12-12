import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np # Needed for array operations in mock model

# --- MOCK PLACEHOLDERS FOR EXTERNAL FILES (MUST BE DEFINED FOR CODE TO RUN) ---

# 1. MOCK for contextual_all_intents_v2.py components
INTENT_FACTORS = {
    'Diplomatic Pressure': {'Economic Dependency': 0.7, 'Security Dependency': 0.3},
    'Economic Coercion': {'Economic Dependency': 0.9, 'Resource Dependence': 0.5},
    'Information Warfare': {'Social Fragility': 0.8, 'Media Literacy': 0.2},
    'Security Dependency': {'Military Presence': 0.9, 'Debt Vulnerability': 0.4}
}

def mock_compute_gs():
    # Mock 'g' factors (Structural Vulnerability) for a few countries
    return {
        'Senegal': {'Debt Vulnerability': 0.6, 'Military Presence': 0.3, 'Resource Dependence': 0.5, 'Social Fragility': 0.4, 'Media Literacy': 0.5, 'Economic Dependency': 0.7},
        'Ethiopia': {'Debt Vulnerability': 0.9, 'Military Presence': 0.7, 'Resource Dependence': 0.8, 'Social Fragility': 0.9, 'Media Literacy': 0.4, 'Economic Dependency': 0.6},
        'Nigeria': {'Debt Vulnerability': 0.5, 'Military Presence': 0.4, 'Resource Dependence': 0.9, 'Social Fragility': 0.8, 'Media Literacy': 0.6, 'Economic Dependency': 0.5},
    }

def mock_compute_R(g):
    # Mock R-factors (Narrative Amplification)
    # R is typically a matrix of Intent x Actor x Factor, but here we mock a simplified matrix
    actors = ['China', 'Rwanda', 'Turkey', 'Russia']
    countries = list(g.keys())
    R_mock = {}
    
    # Generate R-factors (randomly 0.1 to 0.9)
    for intent in INTENT_FACTORS:
        R_mock[intent] = {}
        for actor in actors:
            R_mock[intent][actor] = {}
            for country in countries:
                R_mock[intent][actor][country] = np.random.rand() * 0.8 + 0.1
    return R_mock

def mock_compute_CAs(g, R):
    # Mock CA (Contextual Influence Index) - Intent x Actor x Country
    CA_mock = {}
    actors = ['China', 'Rwanda', 'Turkey', 'Russia']
    
    for intent, factors in INTENT_FACTORS.items():
        CA_mock[intent] = {}
        for actor in actors:
            CA_mock[intent][actor] = {}
            for country, g_factors in g.items():
                
                # Simplified calculation: (Sum of (R * g * Intent_Weight)) / Max_Possible_Score
                total_weighted_vulnerability = 0
                max_possible_score = 0
                r_val = R[intent][actor][country] # Mock R-factor for this combination
                
                for factor, weight in factors.items():
                    g_val = g_factors.get(factor, 0)
                    total_weighted_vulnerability += (r_val * g_val * weight)
                    max_possible_score += (1.0 * 1.0 * weight) # Max R * Max G * Weight
                
                # Normalize the score (0.0 to 1.0)
                score = min(total_weighted_vulnerability / (max_possible_score if max_possible_score > 0 else 1.0), 1.0)
                CA_mock[intent][actor][country] = score
    return CA_mock

# 2. MOCK for data_loader.py components
@st.cache_data
def load_and_transform_data():
    # Assuming the user's uploaded file is named exactly this
    try:
        df = pd.read_csv("Merged_dataset_sample.csv")
    except FileNotFoundError:
        st.error("Error: 'Merged_dataset_sample.csv' not found. Please ensure the file is in the correct location or uploaded.")
        return pd.DataFrame()
        
    # Basic data cleaning/type conversion expected from data_loader
    df['posting_time'] = pd.to_datetime(df['posting_time'], errors='coerce')
    
    # Ensure all required columns exist (for robustness)
    required_cols = ['media_outlet', 'inferred_actor', 'strategic_intent', 'tone', 'target_country', 'URL', 'article_text']
    for col in required_cols:
        if col not in df.columns:
            df[col] = np.nan
            
    return df.dropna(subset=['article_text'])


# Mock enrichment: just passes the data through
def enrich_with_scraping_and_llm(df_base, progress_callback):
    # In a real app, this would scrape 'URL' and populate 'article_text'
    # Since 'article_text' is already populated by the CSV, we just simulate progress
    for i in range(1, 101):
        progress_callback(i/100, f"Simulating LLM enrichment: {i}% complete")
        if i % 25 == 0: # Simulate a time delay
            pass # In a real app, you might use time.sleep(0.1)

    return df_base

# Mock data getter functions
def get_media_names(): return ['Rnanews', 'Rfi', 'A News', 'Yeni Şafak']
def get_countries(): return ['Senegal', 'Ethiopia', 'Nigeria', 'DRC']
def get_actors(): return ['Rwanda', 'France', 'Turkey', 'China', 'Russia']

# --- END OF MOCK PLACEHOLDERS ---

# --- RUN CONTEXTUAL INFLUENCE MODEL ---
# 1. Compute the raw factor scores (g)
g = mock_compute_gs()
# 2. Compute the relative influence R-factors
R = mock_compute_R(g)
# 3. Compute the final Contextual Influence Index (CA) lookup table
CA = mock_compute_CAs(g,R)
# --- MODEL RUN COMPLETE ---


# --- NEW BACKGROUND AND LOGO ---
NEW_BACKGROUND_URL = "https://media.istockphoto.com/id/1502033887/vector/beige-gray-grainy-gradient-background-poster-backdrop-noise-texture-webpage-header-wide.jpg?s=612x612&w=0&k=20&c=eGwiA8zZ4cobGeMz5QeRs5zKzlp1Rr-BcROwT4S22y0=" 
BRIGHT_LOGO_URL = "https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png"


# 🎨 Custom CSS for theme-aware dark cards AND READABILITY FIX
st.markdown(f"""
<style>
/* -------------------- THEME AWARE STYLES -------------------- */
/* Set background image for the app */
.stApp {{
    background-image: url("{NEW_BACKGROUND_URL}");
    background-size: cover;
    background-attachment: fixed;
}}
/* Ensure main text elements use Streamlit's theme color for visibility */
h1, h2, h3, h4, h5, h6, .stAlert p, .stMarkdown, .stPlotlyChart .modebar {{ 
    color: #1a1a1a !important; /* Dark color for section headers and general text */
}}

/* FIX: Ensure Metric Labels (small text above score) are dark and readable */
.stMetric label, .stMetric .css-1ndc21z > div:first-child {{
    color: #444444 !important; /* Dark gray for metric labels */
    font-weight: bold;
}}
/* Ensure Metric Values (the large score numbers) are clearly visible */
.stMetric .css-1ndc21z > div:last-child > div:first-child {{
    color: #1a1a1a !important; /* Very dark for main scores */
}}
/* General text components using default text color (important for sidebars/select boxes) */
.css-1d3w5av, .stText, .stSelectbox label, .stNumberInput label {{
    color: var(--text-color) !important; 
}}


/* -------------------- CARD-SPECIFIC STYLES (Always Dark) -------------------- */
.card {{
    background: #1e1e1e; /* Dark card background */
    color: #ffffff; /* White text inside dark card */
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
with st.spinner("Enriching articles..."):
    progress_bar = st.progress(0)
    status_text = st.empty()
    def progress_callback(p, msg):
        progress_bar.progress(min(p, 1.0))
        status_text.text(msg)
    # df is the DataFrame containing the full 'article_text'
    df = enrich_with_scraping_and_llm(df_base, progress_callback=progress_callback)
progress_bar.empty()
status_text.empty()

# --- CRITICAL: Recommended Summary Preprocessing Step ---
# Creates clean 'llm_summary' and 'display_headline' columns from the raw 'article_text'.
@st.cache_data
def create_display_text(df_in):
    df_out = df_in.copy()
    
    def extract_summary_and_headline(text):
        if not isinstance(text, str) or not text.strip():
            return 'Summary extraction pending or failed.', 'Article Snippet (No Text)'
        
        # 1. Determine the Headline (first sentence)
        # Regex to find the first sentence ending in . ? or !
        headline_match = re.search(r'[^.?!]*[.?!]', text)
        headline = headline_match.group(0).strip() if headline_match else 'Article Snippet'
        
        # 2. Determine the Summary (first 1-2 sentences)
        if headline_match:
            # Check for a second sentence
            text_after_first = text[headline_match.end():]
            second_sentence_match = re.search(r'[^.?!]*[.?!]', text_after_first)
            
            if second_sentence_match and headline_match.end() + second_sentence_match.end() < 500:
                summary = headline + " " + second_sentence_match.group(0).strip()
            else:
                summary = headline
        else:
            # Fallback for non-sentence structures
            summary = text[:200].strip() + '...'
            
        return summary, headline

    # Apply the summary extraction
    # Fill NA values with empty string before processing to avoid errors
    results = df_out['article_text'].fillna('').apply(lambda x: extract_summary_and_headline(x))
    df_out['llm_summary'] = [r[0] for r in results]
    df_out['display_headline'] = [r[1] for r in results]
    
    return df_out

df = create_display_text(df)

# Sidebar filters
with st.sidebar:
    st.title("🔍 Filters")
    # Ensuring "All" is available for selections
    selected_media = st.selectbox("Media Outlet", ["All"] + get_media_names())
    selected_country = st.selectbox("Target Country", ["All"] + get_countries())
    selected_actor = st.selectbox("Foreign Actor", ["All"] + get_actors())
    
    # Intent list now sourced directly from the model script keys
    intents = ["All"] + sorted(INTENT_FACTORS.keys())
    selected_intent = st.selectbox("Strategic Intent", intents)
    
    # Safely get unique tones
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
    # Assumes the data's 'strategic_intent' column matches the INTENT_FACTORS keys
    filtered = filtered[filtered['strategic_intent'] == selected_intent]
if selected_tone != "All":
    filtered = filtered[filtered['tone'] == selected_tone]

# Influence Index Logic (Use actual CA calculated above)
@st.cache_data
def get_influence_score(actor, country, intent):
    if actor == "All" or country == "All" or not CA:
        return 0.0 # Return 0 if filters are too broad or CA is empty
        
    # Normalize input case using .title() to match the TitleCase keys in contextual_all_intents_v2.py
    # Handle known acronyms that .title() messes up (e.g., UAE -> Uae)
    if actor.upper() in ['UAE', 'DRC']:
        actor_normalized = actor.upper()
    else:
        actor_normalized = actor.title()
    
    if country.upper() in ['UAE', 'DRC', 'ROC']:
        country_normalized = country.upper()
    else:
        country_normalized = country.title()
    
    # If a specific intent is selected, use that score
    if intent != "All":
        # CA[intent][actor][country] - Safely retrieve the score, default to 0.0
        score = CA.get(intent, {}).get(actor_normalized, {}).get(country_normalized, 0.0)
        return score
    
    # If "All" intents are selected, calculate the average score across all intents
    scores = []
    for i in CA:
         score = CA[i].get(actor_normalized, {}).get(country_normalized, 0.0)
         if score is not None:
             scores.append(score)

    # Calculate average score
    return sum(scores) / len(scores) if scores else 0.0


current_influence_score = 0.0
# The influence score is only calculated when specific Actor AND Country are selected.
if selected_country != "All" and selected_actor != "All":
    current_influence_score = get_influence_score(selected_actor, selected_country, selected_intent)
    
# --- 1. KPI Metrics ---
st.header("📊 Key Indicators")

# Calculate KPIs
current_article_count = len(filtered)
# --- Mock Data for Delta Calculation ---
previous_article_count = len(df) * 0.95 
article_delta = current_article_count - previous_article_count
article_delta_str = f"{article_delta:,.0f}"

# FIX: Mock previous influence score based on current score
# Ensure previous score is close to current but varies slightly for visual delta
previous_influence_score = current_influence_score * (0.95 + (0.1 * (np.random.rand() - 0.5))) if current_influence_score > 0.05 else 0.0
influence_delta = current_influence_score - previous_influence_score
influence_delta_str = f"{influence_delta:+.2f}"

# Tone Score (Using agreed-upon mapping)
if 'tone' in filtered.columns:
    tone_mapping = {
        'Factual': 0.0,
        'Sensationalist': -0.3, 
        'Cynical': -0.8,         
        'Alarmist': -1.0,        
        'Positive': 1.0,
        'Neutral': 0.0
    }
    # Clean and map tone scores
    filtered['tone_clean'] = filtered['tone'].astype(str).str.title().str.strip()
    filtered['tone_numeric'] = filtered['tone_clean'].map(tone_mapping).fillna(0)
    
    # Ensure all non-mapped values (e.g., NaN or unexpected strings) default to 0.0
    current_tone_score = filtered['tone_numeric'].mean() if not filtered.empty else 0.0
    previous_tone_score = 0.1 # Placeholder value for previous score
    tone_delta = current_tone_score - previous_tone_score
    tone_delta_str = f"{tone_delta:+.2f}"
else:
    current_tone_score = 0.0
    tone_delta_str = "N/A"

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
        # Tone delta color should be 'inverse' because a high negative score (e.g., -0.8) should show a red arrow (inverse)
        delta=tone_delta_str,
        delta_color="inverse" 
    )

with col3:
    st.metric(
        label="Contextual Influence Index",
        value=f"{current_influence_score:.2f}",
        # Influence delta color should be 'inverse' because higher score means higher risk
        delta=influence_delta_str,
        delta_color="inverse"
    )

# Alert if Influence Index is high (e.g., > 0.6)
if selected_actor != "All" and selected_country != "All":
    if current_influence_score > 0.6 and current_influence_score < 0.8:
        st.warning(f"⚠️ **Moderate Vulnerability Alert:** The Contextual Influence Index for **{selected_actor}** in **{selected_country}** is elevated ({current_influence_score:.2f}).")
    elif current_influence_score >= 0.8:
        st.error(f"🚨 **High Vulnerability Warning:** The Contextual Influence Index for **{selected_actor}** in **{selected_country}** is critically high ({current_influence_score:.2f}).")
    elif current_influence_score == 0.00:
        st.info("ℹ️ **CII Calculation Tip:** The Contextual Influence Index is currently 0.00, likely due to a case sensitivity mismatch (e.g., 'UAE' vs 'Uae') in the filter or model data. Ensure casing is consistent across the model and filters.")


# --- NEW: Metric Explanation Section (Visual and non-boring) ---
st.markdown("<br>", unsafe_allow_html=True)

with st.expander("❓ Understanding the Dashboard Metrics (Click to Expand)", expanded=False):
    st.markdown("---")
    
    # 1. Average Tone Score
    st.markdown("####  1. Average Tone Score (Sentiment)")
    st.markdown(
        """
        This score measures the overall **journalistic framing and emotional valence** of the filtered articles. 
        It is tuned to your specific set of journalistic tone categories, ranging from **-1.0 (Critically Negative)** to **+1.0 (Highly Positive)**.
        """
    )

    st.markdown("##### Score Mapping:")
    # Using columns for a visually appealing score table/breakdown
    tone_col1, tone_col2, tone_col3, tone_col4 = st.columns(4)
    
    with tone_col1:
        # Factual/Neutral is the baseline
        st.success("🔵 **0.0 (Factual/Neutral)**: Objective and Balanced")
    with tone_col2:
        # Sensationalist is a lighter negative
        st.info("🟠 **-0.3 (Sensationalist)**: Moderately Negative (Exaggeration)")
    with tone_col3:
        # Cynical is more severe negative
        st.warning("🔴 **-0.8 (Cynical)**: Highly Negative (Distrust)")
    with tone_col4:
        # Alarmist is the most severe negative
        st.error("🚨 **-1.0 (Alarmist)**: Critically Negative (Fear/Crisis)")
    
    st.markdown("---")
    
    # 2. Contextual Influence Index
    st.markdown("####  2. Contextual Influence Index (CII)")
    
    st.markdown(
        """
        The CII is the dashboard's core measure of **vulnerability** to foreign influence operations, 
        ranging from **0.00 (No Vulnerability)** to **1.00 (Critical Vulnerability)**.

        It is a composite score calculated by assessing the overlap between a country's pre-existing weaknesses and the narratives currently being pushed by a specific actor.
        
        
        """
    )
    
    st.markdown("##### CII Components (The Risk Formula):")
    st.markdown(
        """
        1.  **Structural Vulnerability (G-Factor):** **Why the country is weak.** These are objective, underlying risks (e.g., high debt, military reliance) that make the country susceptible to *specific* strategic intents.
        2.  **Narrative Amplification (R-Factor):** **What the actor is doing.** This is the measure of how successfully the foreign actor's narratives (media volume, tone, intent match) are being broadcast and resonating in the media.
        
        A high CII means the actor's efforts are landing on highly vulnerable ground.
        """
    )
    
    # Add a visual risk scale
    st.markdown("##### Risk Scale:")
    risk_col1, risk_col2, risk_col3 = st.columns(3)
    with risk_col1:
        st.markdown("### 0.00 - 0.40")
        st.success("🟢 **LOW RISK**")
    with risk_col2:
        st.markdown("### 0.41 - 0.79")
        st.warning("🟡 **MODERATE RISK**")
    with risk_col3:
        st.markdown("### 0.80 - 1.00")
        st.error("🔴 **CRITICAL RISK**")

st.markdown("---")

# --- 2. Time-Series Trend Analysis ---
st.header("📈 Article Volume Trend")

if 'posting_time' in filtered.columns and not filtered.empty:
    
    # Ensure 'posting_time' is datetime (re-do just in case filtering changed the type)
    filtered['posting_time'] = pd.to_datetime(filtered['posting_time'], errors='coerce')
    filtered.dropna(subset=['posting_time'], inplace=True)
    
    # Aggregate article count by day
    time_series_data = filtered.resample('D', on='posting_time')['URL'].count().reset_index()
    time_series_data.columns = ['Date', 'Article Count']
    
    # Create the interactive Plotly line chart 
    fig = px.line(
        time_series_data,
        x='Date',
        y='Article Count',
        title=f'Daily Article Volume for {selected_actor} in {selected_country}',
        labels={'Article Count': 'Number of Articles'},
        template='plotly_dark' 
    )
    
    # Customize layout for better appearance
    fig.update_traces(mode='lines+markers', marker_size=5)
    fig.update_layout(hovermode="x unified", title_x=0.5)
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Insufficient time-series data to display a trend. Filter criteria may be too narrow or 'posting_time' data is missing/invalid.")
    
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
    
    # Use the pre-processed columns for display
    summary_display = str(row.get('llm_summary', 'Summary extraction failed.'))
    headline = str(row.get('display_headline', 'Article Snippet (No Headline)'))
    
    image_url = str(row.get('urlToImage', None)) 
    media = str(row.get('media_outlet', 'Unknown'))
    target_country = str(row.get('target_country', 'N/A'))
    inferred_actor = str(row.get('inferred_actor', 'N/A'))
    tone = str(row.get('tone', 'N/A'))
    intent = str(row.get('strategic_intent', 'N/A'))
    
    # Format posting time
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
