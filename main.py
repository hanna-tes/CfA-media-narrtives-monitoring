# main.py

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date, timedelta
from data_loader import load_and_transform_data, get_news_categories, get_media_names_for_filter
# Removed 'import time' as it's not used in main.py

TAG_DISPLAY_THRESHOLD = 0.15
ARTICLES_PER_PAGE = 50

# List of labels as per the screenshot
LABELS = sorted([
    "Factual", "Neutral", "Pro-Russia", "Anti-West", "Anti-France",
    "Sensationalist", "Anti-US", "Opinion"
], reverse=True)

# Function to display tags (for source name)
def display_tags(tags, font="Inter", color="grey", wrap=True):
    tag_html = ""
    for tag in tags:
        tag_html += f"<span style='background-color: #e0e0e0; color: #333; padding: 3px 8px; margin: 2px; border-radius: 5px; font-size: 0.8em; font-family: {font};'> {tag} </span>"
    st.markdown(f"<div style='display: flex; flex-wrap: {'wrap' if wrap else 'nowrap'}; margin-top: 5px;'>{tag_html}</div>", unsafe_allow_html=True)

# Function to display label scores (approximating the bar in the screenshot)
def display_label_scores(scores, font="Inter"):
    score_html = ""
    # Sort scores by value in descending order
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    
    # Start building HTML
    html_content = "<div style='margin-top: 10px;'>"
    
    for label, score in sorted_scores:
        if score > TAG_DISPLAY_THRESHOLD: # Only display if above threshold
            width = score * 100
            html_content += f"""
            <div style='display: flex; align-items: center; margin-bottom: 2px; font-family: {font};'>
                <span style='width: 80px; font-size: 0.9em; text-align: left; margin-right: 5px;'>{label}:</span>
                <div style='flex-grow: 1; height: 10px; background-color: #f0f0f0; border-radius: 3px; overflow: hidden;'>
                    <div style='width: {width:.1f}%; height: 100%; background-color: #4CAF50; border-radius: 3px;'></div>
                </div>
                <span style='margin-left: 5px; font-size: 0.9em; font-weight: bold;'>{width:.0f}%</span>
            </div>
            """
    
    html_content += "</div>" # Closing the main wrapper div

    if html_content != "<div style='margin-top: 10px;'></div>": # Only display if there's actual content
        try:
            st.html(html_content) # Use st.html for better rendering of raw HTML
        except AttributeError:
            # Fallback for older Streamlit versions that might not have st.html
            st.markdown(html_content, unsafe_allow_html=True)
    else:
        st.markdown("<div style='margin-top: 10px; font-size: 0.9em; color: #888; font-family: Inter;'>No significant labels</div>", unsafe_allow_html=True)


# Chart functions (adapted from your original code)
def create_percentage_chart(df_filtered, labels, threshold):
    label_data = {}
    for label in labels:
        count = (df_filtered[label] > threshold).sum()
        label_data[label] = count

    df_labels = pd.DataFrame(label_data.items(), columns=['label', 'count'])
    if df_labels['count'].sum() == 0: # Handle empty data for chart
        return None
    df_labels['percentage'] = (df_labels['count'] / len(df_filtered) * 100).round(1)

    chart = alt.Chart(df_labels).mark_bar().encode(
        x=alt.X('percentage', title='Percentage', axis=alt.Axis(format='.0f')),
        y=alt.Y('label', sort='-x', title=''),
        tooltip=['label', alt.Tooltip('percentage', format='.1f') + '%']
    ).properties(
        title='Percentage of articles with labels'
    )
    return chart

def create_average_label_scores_chart(avg_scores):
    df_avg_scores = avg_scores.reset_index()
    df_avg_scores.columns = ['label', 'average_score']
    if df_avg_scores['average_score'].sum() == 0: # Handle empty data for chart
        return None
    df_avg_scores['average_score'] = (df_avg_scores['average_score'] * 100).round(1)

    chart = alt.Chart(df_avg_scores).mark_bar().encode(
        x=alt.X('average_score', title='Average Score (%)', axis=alt.Axis(format='.0f')),
        y=alt.Y('label', sort='-x', title=''),
        tooltip=['label', alt.Tooltip('average_score', format='.1f') + '%']
    ).properties(
        title='Average Label Scores'
    )
    return chart


def main():
    """Main function to run the Streamlit app."""
    
    st.set_page_config(page_title="Vulnerability Index", layout="wide")

    # Initialize session state for pagination
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1
    if 'skip_web_scraping' not in st.session_state:
        st.session_state.skip_web_scraping = False


    # Sidebar for filtering options
    with st.sidebar:
        st.expander("Help: How to use this tool").write(f"""
            Explore a collection of articles. Articles can be filtered by **media outlet**, **timeline**, and **tags (labels)**.

            ### Filtering by Media Outlet
            Select a media outlet to show only articles from that source.

            ### Filtering by Date
            Select a time period to filter the articles by publication date.

            ### Filtering by Tags
            Articles have been tagged with labels such as _pro-Russian_ or _anti-US_ using an AI-based labeling system (simulated here). The AI assigns a score to each tag, indicating how much it believes the tag applies to the article.
            
            For example: A tag score of 0.5 means the AI estimates that the label is moderately relevant to the article. A score closer to 1.0 indicates the label is highly relevant, while a score closer to 0.0 suggests little to no relevance. Use these scores to better understand how much a specific perspective is reflected in the article.
        """)
        
        st.subheader("Filter articles")

        # Add the debug checkbox for skipping web scraping
        st.session_state.skip_web_scraping = st.checkbox(
            "Skip web scraping (for faster debugging)", 
            value=st.session_state.skip_web_scraping,
            help="Check this to load data faster by skipping fetching snippets/images from article URLs. Snippets will be derived from headlines."
        )

        # Load all data initially (cached) - now passes the skip_web_scraping flag
        all_articles_df = load_and_transform_data(st.session_state.skip_web_scraping)
        
        if all_articles_df.empty:
            st.warning("No articles loaded. Please check your data URL and Streamlit logs for errors.")
            return

        st.write(f"Total articles loaded: **{len(all_articles_df)}**")
        
        # Filter by Media Outlet (renamed from 'country' as per screenshot)
        all_media_names = get_media_names_for_filter()
        selected_media_name = st.selectbox(
            'Select a country', # Text changed to match screenshot
            ["All countries"] + all_media_names, # Text changed to match screenshot
            help="Filter articles by media outlet"
        )
        
        # Filter by Label (selectbox as per screenshot)
        selected_label_filter = st.selectbox(
            'Filter by label',
            ["No filter"] + LABELS,
            help="Filter articles by label"
        )
        # st.session_state.clicked_tags.clear() # No longer needed as it's a single selectbox
        # if selected_label_filter != "No filter":
        #     st.session_state.clicked_tags.add(selected_label_filter)

        # Choose a time period slider
        # Ensure min_date and max_date are consistently datetime.date objects
        min_date_from_df = all_articles_df['date_published'].min()
        max_date_from_df = all_articles_df['date_published'].max()

        # Handle NaT values if all dates are unparseable
        if pd.isna(min_date_from_df) or pd.isna(max_date_from_df):
            min_date = date.today() - timedelta(days=30)
            max_date = date.today()
            st.warning("Date range could not be determined from data. Using a default 30-day range.")
        else:
            # Ensure they are datetime.date objects, not pandas Timestamps
            min_date = min_date_from_df.date() if isinstance(min_date_from_df, pd.Timestamp) else min_date_from_df
            max_date = max_date_from_df.date() if isinstance(max_date_from_df, pd.Timestamp) else max_date_from_df

        # If min_date and max_date are the same, add a day to max_date for slider to work
        if min_date == max_date:
            max_date = max_date + timedelta(days=1)

        timeline = st.slider(
            "Choose a time period",
            value=[min_date, max_date],
            min_value=min_date,
            max_value=max_date,
            format="YYYY/MM/DD",
            help="Filter articles by publication date"
        )
        
        st.divider()

        # Apply initial filters for charts
        df_for_charts = all_articles_df.copy()
        
        # Date filter for charts (ensure date_published is consistently datetime.date)
        df_for_charts['date_published_dt'] = df_for_charts['date_published'].apply(lambda x: x.date() if isinstance(x, (datetime, pd.Timestamp)) else x)
        df_for_charts = df_for_charts[
            (df_for_charts['date_published_dt'] >= timeline[0]) & 
            (df_for_charts['date_published_dt'] <= timeline[1])
        ]
        
        # Media name filter (for charts)
        if selected_media_name != "All countries":
            df_for_charts = df_for_charts[df_for_charts['source_name'] == selected_media_name]

        # Label filter (for charts)
        if selected_label_filter != "No filter":
            df_for_charts = df_for_charts[df_for_charts[selected_label_filter] > TAG_DISPLAY_THRESHOLD]


        # Display charts
        if not df_for_charts.empty:
            st.subheader("Percentage of Articles with Labels")
            fig_percentages = create_percentage_chart(df_for_charts, LABELS, threshold=TAG_DISPLAY_THRESHOLD)
            if fig_percentages: # Check if chart object is not None
                st.altair_chart(fig_percentages, use_container_width=True, theme=None) # Added theme=None
            
            st.subheader("Average Label Scores")
            # Calculate average scores for the chart
            avg_scores = df_for_charts[LABELS].mean().sort_values(ascending=False)
            fig_avg_scores = create_average_label_scores_chart(avg_scores)
            if fig_avg_scores: # Check if chart object is not None
                st.altair_chart(fig_avg_scores, use_container_width=True, theme=None) # Added theme=None
        else:
            st.info("No data to display charts for current filters.")

    # --- Main Content Area ---
    st.markdown("""
        <style>
        .stAppViewBlockContainer {
            padding-top: -80px !important;
            margin-top: -80px !important;
        }
        </style>
        """, unsafe_allow_html=True)
    
    st.title("Vulnerability Index")
    st.subheader("Filter articles by date, media outlet, category, and tags")

    # Apply main filters to the dataframe for display
    filtered_df_display = all_articles_df.copy()

    # Date filter for display (ensure date_published is consistently datetime.date)
    filtered_df_display['date_published_dt'] = filtered_df_display['date_published'].apply(lambda x: x.date() if isinstance(x, (datetime, pd.Timestamp)) else x)
    filtered_df_display = filtered_df_display[
        (filtered_df_display['date_published_dt'] >= timeline[0]) & 
        (filtered_df_display['date_published_dt'] <= timeline[1])
    ]

    # Media name filter
    if selected_media_name != "All countries":
        filtered_df_display = filtered_df_display[filtered_df_display['source_name'] == selected_media_name]

    # Label filter
    if selected_label_filter != "No filter":
        filtered_df_display = filtered_df_display[filtered_df_display[selected_label_filter] > TAG_DISPLAY_THRESHOLD]
    
    # Sort by date, most recent first for display
    filtered_df_display = filtered_df_display.sort_values(by='date_published_dt', ascending=False)


    total_articles = len(filtered_df_display)
    total_pages = (total_articles + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE # Calculate total pages

    st.write(f"Showing articles {(st.session_state.current_page - 1) * ARTICLES_PER_PAGE + 1}-"
             f"{min(st.session_state.current_page * ARTICLES_PER_PAGE, total_articles)} out of {total_articles}")

    # Calculate start and end indices for the current page
    start_idx = (st.session_state.current_page - 1) * ARTICLES_PER_PAGE
    end_idx = start_idx + ARTICLES_PER_PAGE

    df_subset_display = filtered_df_display.iloc[start_idx:end_idx]

    # Continue with the existing loop to display articles
    for index, row in df_subset_display.iterrows():
        col1, col2 = st.columns([1, 2])
        # Show images and source tags in the left column
        with col1:
            image_url = row['urlToImage'] if pd.notna(row['urlToImage']) else 'https://placehold.co/400x200/cccccc/000000?text=No+Image'
            try:
                # ✅ Make image clickable
                st.markdown(f"<a href='{row['url']}' target='_blank'><img src='{image_url}' style='width:100%; border-radius: 8px;'></a>", unsafe_allow_html=True)
            except Exception:
                st.markdown(f"<a href='{row['url']}' target='_blank'><img src='https://placehold.co/400x200/cccccc/000000?text=Image+Error' style='width:100%; border-radius: 8px;'></a>", unsafe_allow_html=True)
            source = row['source_name']
            display_tags([source] if pd.notna(source) else ["Unknown"])
        
        with col2:
            st.markdown(f"<h3><a href='{row['url']}' target='_blank' style='color: inherit; text-decoration: none;'>{row['headline']}</a></h3>", unsafe_allow_html=True)
            date_published = row['date_published_dt'] # Use the explicitly converted date here
            text_snippet = row['text'] if pd.notna(row['text']) else "No summary available."
            url = row['url']
            
            st.caption(f"📅 {date_published}")
            st.write(text_snippet) # Use st.write for plain text, not st.html unless it's pure HTML
            st.markdown(f"<a href='{url}' target='_blank' style='color: #1f77b4;'>→ Read full article</a>", unsafe_allow_html=True)
            
            # Retrieve scores from the row and filter tags
            article_labels_scores = {label: row[label] for label in LABELS if label in row and pd.notna(row[label])}
            
            # Display the label scores, approximating the style in the screenshot
            display_label_scores(article_labels_scores)
        st.markdown("---")

    # Add pagination controls at the bottom
    st.write("") # Add some space
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ Previous", disabled=st.session_state.current_page == 1):
                st.session_state.current_page -= 1
                st.rerun()
        with col2:
            st.markdown(f"<p style='text-align: center; margin-top: 10px;'>Page {st.session_state.current_page} of {total_pages}</p>", unsafe_allow_html=True)
        with col3:
            if st.button("Next ➡️", disabled=st.session_state.current_page == total_pages):
                st.session_state.current_page += 1
                st.rerun()


if __name__ == "__main__":
    main()
