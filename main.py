import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import numpy as np 
from urllib.parse import urlparse, urljoin

# --- PAGE CONFIG ---
st.set_page_config(page_title="CFA | Vulnerability Index", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM STYLING (The "Fancy" Part) ---
st.markdown("""
<style>
    /* Glassmorphism Effect */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
    }
    
    /* Modern Card UI */
    .article-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        border-left: 5px solid #00d4ff;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
    }
    .article-card:hover {
        transform: scale(1.005);
        box-shadow: 0 4px 20px rgba(0,0,0,0.12);
    }
    
    .headline { font-size: 1.3rem; font-weight: 700; color: #1e293b; margin-bottom: 8px; }
    .source-tag { font-size: 0.85rem; color: #64748b; font-weight: 500; }
    .summary-text { color: #334155; line-height: 1.6; margin: 12px 0; }
    
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 5px;
        text-transform: uppercase;
    }
    .badge-tone { background: #e2e8f0; color: #475569; }
    .badge-intent { background: #dcfce7; color: #166534; }
</style>
""", unsafe_allow_html=True)

# --- SCRAPER & DATA LOGIC (UNCHANGED BUT CACHED) ---
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    st.error("Missing libraries: requests or beautifulsoup4")

@st.cache_data
def load_mock_logic():
    # Keep your INTENT_FACTORS and CA logic here
    # (Same as your original code to ensure the math stays consistent)
    pass

# ... (Insert your existing fetch_og_image, mock_compute_gs, etc. functions here) ...

# --- NEW ANALYTICS COMPONENTS ---

def render_vulnerability_heatmap(ca_data, selected_intent):
    """Visualizes which actors are most active in which countries."""
    if not ca_data: return
    
    # Flattening CA for a heatmap
    plot_data = []
    intents = [selected_intent] if selected_intent != "All" else ca_data.keys()
    
    for intent in intents:
        for actor, countries in ca_data[intent].items():
            for country, score in countries.items():
                plot_data.append({"Actor": actor, "Country": country, "Vulnerability": score})
    
    df_plot = pd.DataFrame(plot_data).groupby(['Actor', 'Country']).mean().reset_index()
    
    fig = px.density_heatmap(
        df_plot, x="Country", y="Actor", z="Vulnerability",
        color_continuous_scale="Viridis",
        title="🌍 Regional Vulnerability Heatmap",
        labels={'Vulnerability': 'CII Score'}
    )
    fig.update_layout(height=400, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

# --- MAIN DASHBOARD LAYOUT ---

def main():
    # 1. Header Section
    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        st.image("https://raw.githubusercontent.com/hanna-tes/CfA-media-narrtives-monitoring/main/CFA_Logo.png", width=120)
    with col_title:
        st.title("Strategic Narrative & Vulnerability Index")
        st.caption("Monitoring foreign influence and structural dependencies across the African media landscape.")

    # 2. Filters Sidebar (More compact)
    with st.sidebar:
        st.markdown("### 🔍 Search Filters")
        selected_actor = st.selectbox("Foreign Actor", ["All", "China", "Russia", "Turkey", "Rwanda"])
        selected_country = st.selectbox("Target Country", ["All", "Nigeria", "Ethiopia", "Senegal", "DRC"])
        selected_intent = st.selectbox("Strategic Intent", ["All", "Economic Coercion", "Information Warfare", "Diplomatic Pressure"])
        st.divider()
        st.info("Insights are updated based on real-time article scraping and structural risk models.")

    # 3. KPI Top Row
    # (Using your existing calculation logic, just displaying it in columns)
    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Articles", "1,284", "+12%", help="Volume of news detected")
    kpi2.metric("Avg Sentiment", "0.42", "-0.05", delta_color="inverse")
    kpi3.metric("CII Score", "0.68", "High Risk", delta_color="off")
    kpi4.metric("Active Actors", "5", "Stable")

    # 4. Analytics Section
    tab1, tab2 = st.tabs(["📈 Narrative Trends", "🗺️ Risk Mapping"])
    
    with tab1:
        # Insert your Plotly Time-Series code here
        st.markdown("#### Volume Over Time")
        # dummy chart
        df_time = pd.DataFrame(np.random.randn(20, 1), columns=['Volume'])
        st.line_chart(df_time)
        
    with tab2:
        # Heatmap visualization
        # render_vulnerability_heatmap(CA, selected_intent)
        st.markdown("*(Heatmap visualization would render here based on your CA data)*")

    # 5. Articles Display (The "Fancy" Result List)
    st.markdown("### 📰 Intelligence Feed")
    
    # Example of a Fancy Card Loop
    for i in range(3): # Replace with: for _, row in filtered.iterrows():
        st.markdown(f"""
        <div class="article-card">
            <div style="display: flex; gap: 20px;">
                <div style="flex: 0 0 150px;">
                    <img src="https://placehold.co/150x100?text=Article+Image" style="width:100%; border-radius:8px; object-fit:cover;">
                </div>
                <div style="flex: 1;">
                    <div class="source-tag">BBC News • 2 hours ago</div>
                    <div class="headline">Strategic Investment in Port Infrastructure signals shifting dependencies</div>
                    <div class="summary-text">Analysis of recent trade agreements suggests a move toward long-term economic alignment with specific regional actors...</div>
                    <div>
                        <span class="badge badge-tone">Neutral</span>
                        <span class="badge badge-intent">Economic Coercion</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
