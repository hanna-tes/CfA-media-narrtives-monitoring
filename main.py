# main.py

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date, timedelta
from data_loader import load_and_transform_data, get_news_categories, get_media_names_for_filter
import time  # Make sure this is imported

TAG_DISPLAY_THRESHOLD = 0.15
ARTICLES_PER_PAGE = 5

LABELS = sorted([
    "Factual", "Neutral", "Pro-Russia", "Anti-West", "Anti-France",
    "Sensationalist", "Anti-US", "Opinion"
], reverse=True)


def display_tags(tags, font="Inter"):
    tag_html = "".join([
        f"<span style='background-color: #e0e0e0; color: #333; padding: 3px 8px; margin: 2px; "
        f"border-radius: 5px; font-size: 0.8em; font-family: {font};'> {tag} </span>"
        for tag in tags
    ])
    st.markdown(f"<div style='display: flex; flex-wrap: wrap; margin-top: 5px;'>{tag_html}</div>", unsafe_allow_html=True)


def display_label_scores(scores, font="Inter"):
    """Display label scores as clean horizontal bars."""
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    html = "<div style='margin-top:10px;'>"
    for label, score in sorted_scores:
        if score > TAG_DISPLAY_THRESHOLD:
            width = score * 100
            html += f"<div style='display:flex;align-items:center;margin-bottom:2px;font-family:{font};'>" \
                    f"<span style='width:80px;font-size:0.9em;text-align:left;margin-right:5px;'>{label}:</span>" \
                    f"<div style='flex-grow:1;height:10px;background-color:#f0f0f0;border-radius:3px;overflow:hidden;'>" \
                    f"<div style='width:{width:.0f}%;height:100%;background-color:#4CAF50;border-radius:3px;'></div>" \
                    f"</div>" \
                    f"<span style='margin-left:5px;font-size:0.9em;font-weight:bold;'>{width:.0f}%</span>" \
                    f"</div>"
    html += "</div>"
    
    st.markdown(html, unsafe_allow_html=True)


def create_percentage_chart(df_filtered, labels, threshold):
    data = {label: (df_filtered[label] > threshold).sum() for label in labels}
    df = pd.DataFrame(data.items(), columns=['label', 'count'])
    if df['count'].sum() == 0:
        return None
    df['percentage'] = (df['count'] / len(df_filtered) * 100).round(1)
    return alt.Chart(df).mark_bar().encode(
        x=alt.X('percentage:Q', title='Percentage (%)', axis=alt.Axis(format='.0f')),
        y=alt.Y('label:N', sort='-x', title=''),
        tooltip=[
            alt.Tooltip('label:N', title='Label'),
            alt.Tooltip('percentage:Q', format='.1f', title='Percentage')
        ]
    ).properties(title='Percentage of Articles with Labels')


def main():
    st.set_page_config(page_title="Vulnerability Index", layout="wide")

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    # --- Load Data with REAL Progress Tracking ---
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Start timing
    start_time = time.time()
    
    # Function to update progress from data_loader
    def update_progress(progress, message=None):
        progress_bar.progress(min(progress, 1.0))
        if message:
            status_text.text(message)
    
    # Load data WITH progress tracking
    all_articles_df = load_and_transform_data(progress_callback=update_progress)
    
    # Calculate load time
    load_time = time.time() - start_time
    
    # Clear progress when done
    progress_bar.empty()
    status_text.empty()

    if all_articles_df.empty:
        st.warning("⚠️ No articles loaded.")
        st.stop()

    # --- Sidebar ---
    with st.sidebar:
        st.subheader("🔍 Filter Articles")

        all_media_names = get_media_names_for_filter()
        selected_media = st.selectbox(
            'Filter by media outlet',
            ["All outlets"] + sorted(all_media_names),
            help="Filter articles by media outlet"
        )

        selected_label = st.selectbox(
            'Filter by label',
            ["No filter"] + LABELS,
            help="Show only articles with this label above threshold"
        )

        selected_category = st.selectbox(
            'Filter by category',
            ["All categories"] + get_news_categories(),
            help="Filter articles by news category"
        )

        # Safe date slider
        valid_dates = pd.to_datetime(all_articles_df['date_published'], errors='coerce').dropna()
        if valid_dates.empty:
            min_date = date(2020, 1, 1)
            max_date = date(2030, 1, 1)
        else:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()

        if min_date == max_date:
            max_date = max_date + timedelta(days=1)

        timeline = st.slider(
            "Choose a time period",
            min_value=min_date,
            max_value=max_date,
            value=(min_date, max_date),
            format="YYYY/MM/DD"
        )

        st.divider()

        # --- Charts in Sidebar ---
        st.subheader("📊 Percentage of Articles with Labels")
        df_charts = all_articles_df.copy()
        df_charts['date_published'] = pd.to_datetime(df_charts['date_published'], errors='coerce')
        df_charts = df_charts[
            (df_charts['date_published'].dt.date >= timeline[0]) &
            (df_charts['date_published'].dt.date <= timeline[1])
        ]
        if selected_media != "All outlets":
            df_charts = df_charts[df_charts['source_name'] == selected_media]
        if selected_label != "No filter":
            df_charts = df_charts[df_charts[selected_label] > TAG_DISPLAY_THRESHOLD]

        if not df_charts.empty:
            chart1 = create_percentage_chart(df_charts, LABELS, TAG_DISPLAY_THRESHOLD)
            if chart1:
                st.altair_chart(chart1, use_container_width=True, theme=None)
        else:
            st.info("No data to display charts.")
        
        # Add performance info and cache clearing
        st.divider()
        st.caption(f"Loaded in {load_time:.1f}s")
        if st.button("🔄 Clear LLM Cache"):
            st.session_state.llm_cache = {}
            st.rerun()

    # --- Main Content Area ---
    st.title("🌍 Vulnerability Index")
    st.subheader("Filter articles by date, media outlet, category, and narrative tags")

    # Apply filters
    filtered_df = all_articles_df.copy()
    filtered_df['date_published'] = pd.to_datetime(filtered_df['date_published'], errors='coerce')
    filtered_df = filtered_df[
        (filtered_df['date_published'].dt.date >= timeline[0]) &
        (filtered_df['date_published'].dt.date <= timeline[1])
    ]
    if selected_media != "All outlets":
        filtered_df = filtered_df[filtered_df['source_name'] == selected_media]
    if selected_label != "No filter":
        filtered_df = filtered_df[filtered_df[selected_label] > TAG_DISPLAY_THRESHOLD]
    filtered_df = filtered_df.sort_values(by='date_published', ascending=False).reset_index(drop=True)

    total = len(filtered_df)
    total_pages = (total + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE
    st.write(f"📄 Showing {(st.session_state.current_page-1)*ARTICLES_PER_PAGE+1}–{min(st.session_state.current_page*ARTICLES_PER_PAGE, total)} of {total}")

    start = (st.session_state.current_page - 1) * ARTICLES_PER_PAGE
    end = start + ARTICLES_PER_PAGE
    page_df = filtered_df.iloc[start:end]

    if total == 0:
        st.info("📭 No articles match filters.")
    else:
        for _, row in page_df.iterrows():
            col1, col2 = st.columns([1, 2])
            with col1:
                img_url = row['urlToImage']
                if pd.isna(img_url) or not str(img_url).startswith(('http://', 'https://')):
                    img_url = 'https://placehold.co/400x200/cccccc/000000?text=No+Image'
                try:
                    st.markdown(f"<a href='{row['url']}' target='_blank'><img src='{img_url}' style='width:100%; border-radius: 8px;'></a>", unsafe_allow_html=True)
                except Exception:
                    st.markdown(f"<a href='{row['url']}' target='_blank'><img src='https://placehold.co/400x200/cccccc/000000?text=Image+Error' style='width:100%; border-radius: 8px;'></a>", unsafe_allow_html=True)
                source = row['source_name']
                display_tags([source] if pd.notna(source) else ["Unknown"])

            with col2:
                st.markdown(f"<h3><a href='{row['url']}' target='_blank' style='color: inherit; text-decoration: none;'>{row['headline']}</a></h3>", unsafe_allow_html=True)
                date_str = row['date_published'].strftime('%Y-%m-%d') if pd.notna(row['date_published']) else "Unknown"
                st.caption(f"📅 {date_str}")
                st.write(row['text'] if pd.notna(row['text']) else "No summary available.")
                scores = {lbl: row[lbl] for lbl in LABELS if lbl in row and pd.notna(row[lbl])}
                display_label_scores(scores)
            st.markdown("---")

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
