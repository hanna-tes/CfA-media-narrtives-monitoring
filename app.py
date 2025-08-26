import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import io
import gspread
from urllib.parse import urlparse, parse_qs

# --- Configuration for Google Sheets ---
# Name of your Google Sheet
SHEET_NAME = "CfA_mentions_tracker"  
# Name of the worksheet you want to read from
WORKSHEET_NAME = "Sheet1"  

def get_clean_url(google_url):
    """Extracts the clean URL from a Google redirect link."""
    try:
        parsed_url = urlparse(google_url)
        query_params = parse_qs(parsed_url.query)
        return query_params['url'][0]
    except (KeyError, IndexError):
        return google_url

def categorize_source(url):
    """Categorizes a source based on its URL."""
    url_lower = url.lower()
    if ('yahoo.com' in url_lower or 'reuters.com' in url_lower or 
        'afp.com' in url_lower or 'france24.com' in url_lower or
        'laviesenegalaise.com' in url_lower or 'iol.co.za' in url_lower or
        'tuko.co.ke' in url_lower or 'bizcommunity.com' in url_lower):
        return 'News Outlet'
    elif 'pressreader.com' in url_lower:
        return 'Digital Paper/Magazine'
    elif 'twitter.com' in url_lower or 'facebook.com' in url_lower:
        return 'Social Media'
    elif 'blogspot.com' in url_lower or 'wordpress.com' in url_lower:
        return 'Blog'
    # Add more categories as needed
    else:
        return 'Other'

# Function to load data directly from Google Sheets
@st.cache_data(ttl=600)  # Cache data for 10 minutes to avoid hitting API limits
def load_data_from_google_sheet():
    """Reads data from a Google Sheet using a service account credentials from st.secrets."""
    try:
        creds_json = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_json)
        sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error connecting to Google Sheet: {e}. Please check your credentials and sheet name.")
        return None

def display_dashboard(df_combined):
    """
    Displays the dashboard with a more visually appealing design.
    """
    # Clean the column names for easier access
    df_combined.columns = [col.strip().lower() for col in df_combined.columns]

    # Extract clean URLs from the Google redirect links
    df_combined['url'] = df_combined['url'].apply(get_clean_url)

    # Convert 'daily_update' to datetime format
    df_combined['daily_update'] = pd.to_datetime(df_combined['daily_update'])

    # Add the new source category column
    df_combined['source_category'] = df_combined['url'].apply(categorize_source)

    # --- High-Level Overview Section ---
    st.markdown("---")
    st.markdown("""
        <div style="text-align: center; border-bottom: 2px solid #5D8AA8; padding-bottom: 10px;">
            <h1 style="color: #5D8AA8;">Dashboard Overview</h1>
        </div>
    """, unsafe_allow_html=True)

    total_mentions = len(df_combined)
    mentions_by_source = df_combined['source'].value_counts()
    top_source = mentions_by_source.index[0] if not mentions_by_source.empty else "N/A"

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"### Total Mentions\n\n**{total_mentions}** mentions recorded!")
    with col2:
        st.success(f"### Top Source\n\n**{top_source}** is the top-mentioning source.")

    # --- All Mentions Details Section (now in a prominent table) ---
    st.markdown("---")
    st.markdown("""
        <div style="text-align: center; border-bottom: 2px solid #5D8AA8; padding-bottom: 10px; margin-top: 30px;">
            <h2 style="color: #5D8AA8;">All Mentions Details</h2>
        </div>
    """, unsafe_allow_html=True)
    
    # Display all mentions in an interactive table with clickable links
    st.data_editor(
        df_combined[['daily_update', 'source', 'title', 'snippet', 'url']].rename(columns={
            'daily_update': 'Date',
            'source': 'Source',
            'title': 'Title',
            'snippet': 'Snippet',
            'url': 'URL'
        }),
        disabled=True,
        height=400,
        column_config={
            "URL": st.column_config.LinkColumn("URL")
        }
    )

    # --- Visualizations Section ---
    st.markdown("---")

    plt.style.use('dark_background')

    # New chart: Mentions by Source Category
    mentions_by_category = df_combined['source_category'].value_counts()
    st.subheader("Mentions by Source Category")
    fig, ax = plt.subplots(figsize=(10, 6))
    mentions_by_category.plot(kind='bar', color=plt.cm.viridis.colors, ax=ax)
    ax.set_title('Mentions by Source Category', fontsize=16, color='white')
    ax.set_xlabel('Category', fontsize=12, color='white')
    ax.set_ylabel('Number of Mentions', fontsize=12, color='white')
    ax.tick_params(colors='white')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    st.pyplot(fig)

    # Existing plots
    st.subheader("Mentions by Source")
    fig, ax = plt.subplots(figsize=(10, 6))
    mentions_by_source.plot(kind='bar', color=plt.cm.Paired.colors, ax=ax)
    ax.set_title('Mentions by Source', fontsize=16, color='white')
    ax.set_xlabel('Source', fontsize=12, color='white')
    ax.set_ylabel('Number of Mentions', fontsize=12, color='white')
    ax.tick_params(colors='white')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    st.pyplot(fig)

    st.subheader("Mentions Over Time")
    mentions_over_time = df_combined.groupby('daily_update').size()
    fig, ax = plt.subplots(figsize=(10, 6))
    mentions_over_time.plot(kind='line', marker='o', linestyle='-', color='#5D8AA8', ax=ax)
    ax.set_title('Mentions Over Time', fontsize=16, color='white')
    ax.set_xlabel('Date', fontsize=12, color='white')
    ax.set_ylabel('Number of Mentions', fontsize=12, color='white')
    ax.grid(True, linestyle='--', alpha=0.6, color='gray')
    ax.tick_params(colors='white')
    plt.tight_layout()
    st.pyplot(fig)


def main():
    st.set_page_config(layout="wide", page_title="Code for Africa's Work Mentions Tracking Dashboard")
    st.title("Code for Africa's Work Mentions Tracking Dashboard")
    st.sidebar.header("Data Source")
    data_source_option = st.sidebar.radio(
        "Choose your data source:",
        ("Upload Your Own Dataset", "Link to Google Sheet")
    )
    st.sidebar.markdown("---")

    if data_source_option == "Upload Your Own Dataset":
        st.sidebar.info("Upload one or more CSV files from your local machine.")
        uploaded_files = st.file_uploader(
            "Choose one or more CSV files",
            type="csv",
            accept_multiple_files=True
        )

        if uploaded_files:
            all_dfs = []
            for file in uploaded_files:
                try:
                    df = pd.read_csv(io.StringIO(file.getvalue().decode('utf-8')))
                    all_dfs.append(df)
                except Exception as e:
                    st.error(f"Error reading {file.name}: {e}")
                    return
            df_combined = pd.concat(all_dfs, ignore_index=True)
            display_dashboard(df_combined)
        else:
            st.info("Please upload CSV files to view the dashboard.")

    elif data_source_option == "Link to Google Sheet":
        st.sidebar.info("Loading data directly from your Google Sheet.")
        df = load_data_from_google_sheet()
        if df is not None:
            display_dashboard(df)
        else:
            st.warning("Data could not be loaded from Google Sheet. Please check the credentials and sheet info.")

if __name__ == "__main__":
    main()
