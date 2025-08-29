# main.py

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date, timedelta
from data_loader import load_and_transform_data, get_news_categories, get_media_names_for_filter

TAG_DISPLAY_THRESHOLD = 0.15
ARTICLES_PER_PAGE = 5

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

# Function to display label scores (bar-like UI)
def display_label_scores(scores, font="Inter"):
    score_html = ""
    # Sort scores by value in descending order
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    for label, score in sorted_scores:
        if score > TAG_DISPLAY_THRESHOLD:  # Only display if above threshold
            score_html += f"""
            <div style='display: flex; align-items: center; margin-bottom: 2px; font-family: {font};'>
                <span style='width: 80px; font-size: 0.9em; text-align: left; margin-right: 5px;'>{label}:</span>
                <div style='flex-grow: 1; height: 10px; background-color: #f0f0f0; border-radius: 3px; overflow: hidden;'>
                    <div style='width: {score*100}%; height: 100%; background-color: #4CAF50; border-radius: 3px;'></div>
                </div>
                <span style='margin-left: 5px; font-size: 0.9em; font-weight: bold;'>{score*100:.0f}%</span>
            </div>
            """
    if score_html:
        st.markdown(f"<div style='margin-top: 10px;'>{score_html}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='margin-top: 10px; font-size: 0.9em; color: #888;'>No significant labels</div>", unsafe_allow_html=True)


# Chart functions
def create_percentage_chart(df_filtered, labels, threshold):
    label_data = {}
    for label in labels:
        count = (df_filtered[label] > threshold).sum()
        label_data[label] = count

    df_labels = pd.DataFrame(label_data.items(), columns=['label', 'count'])
    if df_labels['count'].sum() == 0:
        return None  # No data to show
    df_labels['percentage'] = (df_labels['count'] / len(df_filtered) * 100).round(1)

    chart = alt.Chart(df_labels).mark_bar().encode(
        x=alt.X('percentage:Q', title='Percentage (%)', axis=alt.Axis(format='.0f')),
        y=alt.Y('label:N', sort='-x', title=''),
        tooltip=[
            alt.Tooltip('label:N', title='Label'),
            alt.Tooltip('percentage:Q', format='.1f', title='Percentage') + '%'
        ]
    ).properties(
        title='Percentage of Articles with Labels'
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    )
    return chart

def create_average_label_scores_chart(avg_scores):
    df_avg_scores = avg_scores.reset_index()
    df_avg_scores.columns = ['label', 'average_score']
    df_avg_scores['average_score'] = (df_avg_scores['average_score'] * 100).round(1)

    if df_avg_scores['average_score'].sum() == 0:
        return None  # No data to show

    chart = alt.Chart(df_avg_scores).mark_bar().encode(
        x=alt.X('average_score:Q', title='Average Score (%)', axis=alt.Axis(format='.0f')),
        y=alt.Y('label:N', sort='-x', title=''),
        tooltip=[
            alt.Tooltip('label:N', title='Label'),
            alt.Tooltip('average_score:Q', format='.1f', title='Avg Score') + '%'
        ]
    ).properties(
        title='Average Label Scores'
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    )
    return chart


def main():
    """Main function to run the Streamlit app."""
    
    st.set_page_config(page_title="Vulnerability Index", layout="wide")

    # Initialize session state for pagination
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1
    if 'clicked_tags' not in st.session_state:
        st.session_state.clicked_tags = set()

    # Load all data initially (cached)
    all_articles_df = load_and_transform_data()
    
    if all_articles_df.empty:
        st.warning("⚠️ No articles loaded. Please check your data file or internet connection.")
        return

    # Sidebar for filtering options
    with st.sidebar:
        with st.expander("📘 Help: How to use this tool"):
            st.write(f"""
                Explore a collection of **{len(all_articles_df)} articles**. Filter by **media outlet**, **date**, and **labels (tags)**.

                ### Filtering by Media Outlet
                Select a media outlet to show only articles from that source.

                ### Filtering by Date
                Use the slider to select a time period.

                ### Filtering by Labels
                Each article is assigned a score (0–1) for labels like _Pro-Russia_ or _Anti-US_.
                A score above **{TAG_DISPLAY_THRESHOLD:.0%}** is considered relevant.
                Use the selectbox to filter articles by a specific label.
            """)

        st.subheader("🔍 Filter Articles")

        # Filter by Media Outlet
        all_media_names = get_media_names_for_filter()
        selected_media_name = st.selectbox(
            'Select a country',
            ["All countries"] + sorted(all_media_names),
            help="Filter articles by media outlet"
        )

        # Filter by Label
        selected_label_filter = st.selectbox(
            'Filter by label',
            ["No filter"] + LABELS,
            help="Show only articles with this label above threshold"
        )
        st.session_state.clicked_tags.clear()
        if selected_label_filter != "No filter":
            st.session_state.clicked_tags.add(selected_label_filter)

        # Date filter
        min_date = pd.to_datetime(all_articles_df['date_published'].min())
        max_date = pd.to_datetime(all_articles_df['date_published'].max())
        timeline = st.slider(
            "Choose a time period",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            format="YYYY/MM/DD",
            help="Filter by publication date"
        )

        st.divider()

        # Apply filters for charts
        df_for_charts = all_articles_df.copy()
        df_for_charts['date_published'] = pd.to_datetime(df_for_charts['date_published'])  # Ensure datetime

        # Date filter
        df_for_charts = df_for_charts[
            (df_for_charts['date_published'] >= timeline[0]) &
            (df_for_charts['date_published'] <= timeline[1])
        ]

        # Media filter
        if selected_media_name != "All countries":
            df_for_charts = df_for_charts[df_for_charts['source_name'] == selected_media_name]

        # Label filter
        if selected_label_filter != "No filter":
            df_for_charts = df_for_charts[df_for_charts[selected_label_filter] > TAG_DISPLAY_THRESHOLD]

        # Display charts
        if not df_for_charts.empty:
            fig_percentages = create_percentage_chart(df_for_charts, LABELS, TAG_DISPLAY_THRESHOLD)
            if fig_percentages is not None:
                st.altair_chart(fig_percentages, use_container_width=True, theme=None)
            else:
                st.info("📊 No labels above threshold to display in chart.")

            avg_scores = df_for_charts[LABELS].mean().sort_values(ascending=False)
            fig_avg_scores = create_average_label_scores_chart(avg_scores)
            if fig_avg_scores is not None:
                st.altair_chart(fig_avg_scores, use_container_width=True, theme=None)
            else:
                st.info("📊 No average scores to display.")
        else:
            st.info("📊 No data to display charts for current filters.")

    # --- Main Content Area ---
    st.title("🌍 Vulnerability Index")
    st.subheader("Filter articles by date, country, and narrative tags")

    # Apply filters to main display
    filtered_df_display = all_articles_df.copy()
    filtered_df_display['date_published'] = pd.to_datetime(filtered_df_display['date_published'])

    filtered_df_display = filtered_df_display[
        (filtered_df_display['date_published'] >= timeline[0]) &
        (filtered_df_display['date_published'] <= timeline[1])
    ]

    if selected_media_name != "All countries":
        filtered_df_display = filtered_df_display[filtered_df_display['source_name'] == selected_media_name]

    if selected_label_filter != "No filter":
        filtered_df_display = filtered_df_display[filtered_df_display[selected_label_filter] > TAG_DISPLAY_THRESHOLD]

    filtered_df_display = filtered_df_display.sort_values(by='date_published', ascending=False).reset_index(drop=True)

    total_articles = len(filtered_df_display)
    total_pages = (total_articles + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE

    st.write(f"📄 Showing articles **{(st.session_state.current_page - 1) * ARTICLES_PER_PAGE + 1}–"
             f"{min(st.session_state.current_page * ARTICLES_PER_PAGE, total_articles)}** out of **{total_articles}**")

    # Pagination
    start_idx = (st.session_state.current_page - 1) * ARTICLES_PER_PAGE
    end_idx = start_idx + ARTICLES_PER_PAGE
    df_subset_display = filtered_df_display.iloc[start_idx:end_idx]

    if total_articles == 0:
        st.info("📭 No articles match your current filters.")
    else:
        for index, row in df_subset_display.iterrows():
            col1, col2 = st.columns([1, 2])
            with col1:
                # Use fallback image if needed
                image_url = row['urlToImage']
                if pd.isna(image_url) or not str(image_url).strip() or not image_url.startswith(('http://', 'https://')):
                    image_url = 'https://placehold.co/400x200/cccccc/000000?text=No+Image'

                try:
                    st.image(image_url, use_column_width=True)
                except Exception:
                    st.image('https://placehold.co/400x200/cccccc/000000?text=Image+Error', use_column_width=True)

                # Display source tag
                source = row['source_name']
                if pd.notna(source) and str(source).strip():
                    display_tags([str(source)], wrap=True)
                else:
                    display_tags(["Unknown Source"], wrap=True)

            with col2:
                headline = row['headline']
                st.markdown(f"<h3 style='margin-top: 0;'>{headline}</h3>", unsafe_allow_html=True)

                date_str = row['date_published'].strftime('%Y-%m-%d')
                st.caption(f"📅 {date_str}")

                text_snippet = row['text'] if pd.notna(row['text']) else "No snippet available."
                st.html(f"{text_snippet} <a href='{row['url']}' target='_blank' style='color: #1f77b4;'>→ Read full article</a>")

                # Show label scores
                article_labels_scores = {label: row[label] for label in LABELS if label in row and pd.notna(row[label])}
                display_label_scores(article_labels_scores)

            st.markdown("---")

    # Pagination Controls
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ Previous", disabled=st.session_state.current_page == 1, key="prev_btn"):
                st.session_state.current_page -= 1
                st.rerun()
        with col2:
            st.markdown(f"<p style='text-align: center; margin-top: 10px;'>Page {st.session_state.current_page} of {total_pages}</p>", unsafe_allow_html=True)
        with col3:
            if st.button("Next ➡️", disabled=st.session_state.current_page == total_pages, key="next_btn"):
                st.session_state.current_page += 1
                st.rerun()


if __name__ == "__main__":
    main()
