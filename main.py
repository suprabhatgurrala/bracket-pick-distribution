import requests
import pandas as pd
import streamlit as st
import datetime

def get_bracket_data(scoring_period_id=None, year=2026):
    base_url = f"https://gambit-api.fantasy.espn.com/apis/v1/challenges/tournament-challenge-bracket-{year}/"
    params = {}
    if scoring_period_id:
        params["scoringPeriodId"] = scoring_period_id
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    data = response.json()
    return data

@st.cache_data
def fetch_bracket_data(year):
    results = []

    # Get initial metadata to find all scoring periods
    data = get_bracket_data(year=year)
    
    scoring_periods = data.get('scoringPeriods', [])
    period_ids = [p['id'] for p in scoring_periods]
    period_map = {p['id']: p['abbrev'] for p in scoring_periods}
    region_names = data.get('settings', {}).get('regionNames', {})
    
    # Use a progress bar for data fetching
    progress_bar = st.progress(0)
    for i, scoring_period_id in enumerate(period_ids):
        data = get_bracket_data(scoring_period_id, year=year)

        for prop in data.get('propositions', []):
            for outcome in prop.get('possibleOutcomes', []):
                name = outcome.get('name')
                region_id = outcome.get('regionId')
                region_seed = outcome.get('regionSeed')
                
                percentage = None
                choice_counters = outcome.get('choiceCounters', [])
                count = 0
                for counter in choice_counters:
                    if counter.get('scoringFormatId') == 5:
                        percentage = counter.get('percentage')
                        count = counter.get('count')
                        break
                
                if percentage is None and choice_counters:
                    percentage = choice_counters[0].get('percentage')
                    count = choice_counters[0].get('count', 0)
                
                rd_abbrv = period_map[scoring_period_id]
                
                results.append({
                    "Name": name,
                    "Region": region_names.get(f"{region_id}"),
                    "Seed": region_seed,
                    f"{rd_abbrv} Percentage": percentage if percentage is not None else None,
                    f"{rd_abbrv} Count": count
                })
        progress_bar.progress((i + 1) / len(period_ids))
    
    progress_bar.empty()
    df = pd.DataFrame(results)
    # Group by team info and take the max for matching columns
    df = df.groupby(["Name", "Region", "Seed"]).max().reset_index()
    # Convert flat columns to MultiIndex: (Round, Type)
    # Name, Region, Seed will have (" ", "Name"), (" ", "Region"), (" ", "Seed")
    new_cols = []
    for col in df.columns:
        if col in ["Name", "Region", "Seed"]:
            new_cols.append(("", col))
        else:
            parts = col.rsplit(" ", 1)
            new_cols.append((parts[0], parts[1]))
    
    df.columns = pd.MultiIndex.from_tuples(new_cols)
    return df

def main():
    st.set_page_config(page_title="ESPN Bracket Pick Distribution", layout="wide")
    
    current_year = datetime.date.today().year
    years = list(range(2023, current_year + 1))
    
    col_title, col_year = st.columns([3, 1])
    with col_year:
        year = st.selectbox("Select Year", options=reversed(years), index=0)
    
    with col_title:
        st.title(f"🏀 ESPN Bracket Pick Distribution {year}")
    
    with st.spinner(f"Fetching latest bracket data from ESPN for {year}..."):
        espn_df = fetch_bracket_data(year)
    
    st.subheader("Pick Distribution by Round")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Percentage of brackets picking each team to reach/win the specified round.")
    with col2:
        view_type = st.radio("Display Format", ["Percentages", "Total Counts"], horizontal=True)
    
    # Filter by Region
    all_regions = ["All"] + sorted(espn_df[("", "Region")].dropna().unique().tolist())
    selected_region = st.pills("Filter by Region", options=all_regions, selection_mode="single", default="All")
    
    if selected_region and selected_region != "All":
        espn_df = espn_df[espn_df[("", "Region")] == selected_region]
    
    # Filter columns based on view type
    data_type = "Percentage" if view_type == "Percentages" else "Count"
    
    # Sort by NCG descending by default if it exists
    ncg_col = ("NCG", data_type)
    if ncg_col in espn_df.columns:
        espn_df = espn_df.sort_values(by=[ncg_col], ascending=False)
    
    # Select Name, Region, Seed and the chosen data type for each round
    display_cols = [col for col in espn_df.columns if col[1] == data_type or col[0] == ""]
    df_to_show = espn_df[display_cols]
    
    # Configure formatting using Pandas Styler
    # We use a dictionary where keys are the MultiIndex tuples
    format_dict = {}
    for col in display_cols:
        if col[1] == "Percentage":
            format_dict[col] = "{:.3%}"
        elif col[1] == "Count":
            format_dict[col] = "{:,.0f}" # Comma separator, 0 decimals
    
    # Display the dataframe with formatting
    st.dataframe(
        df_to_show.style.format(format_dict),
        hide_index=True,
        use_container_width=True,
        height=800
    )

if __name__ == "__main__":
    main()
