import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Epic Fury | Movement Command Center", page_icon="⚓", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --navy:#071a2f; --panel:#102d4b; --muted:#9fb5cc; --cyan:#39c6d8; }
.stApp { background: radial-gradient(circle at top right,#123d61 0,#071a2f 42%,#061322 100%); color:#edf6ff; }
.block-container { max-width: 1500px; padding-top: 1.5rem; }
[data-testid="stSidebar"] { background: rgba(5,18,34,.96); border-right:1px solid rgba(255,255,255,.08); }
[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(31,76,111,.72),rgba(10,32,55,.9)); border:1px solid rgba(115,192,224,.18); border-radius:14px; padding:14px; }
[data-testid="stMetricLabel"] { color:#a9c2d8; } [data-testid="stMetricValue"] { color:#fff; }
[data-testid="stChatMessage"] { border:1px solid rgba(122,190,220,.16); border-radius:14px; background:rgba(13,43,70,.56); }
[data-testid="stDataFrame"] { border:1px solid rgba(122,190,220,.16); border-radius:12px; }
hr { border-color:rgba(255,255,255,.12); }
</style>
""", unsafe_allow_html=True)

STATUS_COLORS = {"ON LOCATION":"#27ae60","PENDING":"#f39c12","TRAVEL CONFIRMED":"#2980b9","CANCELLED":"#c0392b","NO SHOW":"#8e44ad","IN TRANSIT":"#00a6b2","ARRIVAL PENDING":"#e67e22","STS TRANSIT":"#008c9e","FY27 LOA NEEDED":"#795548"}

@st.cache_data
def load_data():
    base = Path(__file__).resolve().parent
    candidates = ["MSC Epic Fury Movement Tracker_N1.xlsx", "MSC Epic Fury Movement Tracker_N1.csv", "Epic Fury Data", "clean_mcs.csv", "CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv"]
    path = next((base / name for name in candidates if (base / name).exists()), None)
    if path is None: return None
    data = pd.read_excel(path) if path.suffix.lower() == ".xlsx" else pd.read_csv(path)
    data.columns = [str(c).strip() for c in data.columns]
    data = data.rename(columns={"CIVMAR/PER":"PERSON", "EXT STATUS":"EXT_STATUS", "IN/OUT":"IN_OUT", "DATE 1":"DATE_1", "DATE 2":"DATE_2", "COMMENTS & ACTIONS":"COMMENTS"})
    for col in data.columns:
        if data[col].dtype == "object": data[col] = data[col].fillna("Unknown").astype(str).str.strip()
    for col in ["DATE_1","DATE_2","DOA","DUE OFF DT","LILP DATE"]:
        if col in data: data[col] = pd.to_datetime(data[col], errors="coerce")
    if "STATUS" in data: data["STATUS"] = data["STATUS"].astype(str).str.upper().replace({"NAN":"UNKNOWN","NONE":"UNKNOWN"})
    return data

def text_col(data, col):
    return data[col].fillna("Unknown").astype(str).str.upper() if col in data else pd.Series("Unknown", index=data.index)

def apply_filters(data):
    with st.sidebar:
        st.header("Mission filters")
        search = st.text_input("Search personnel", placeholder="Last name or full name")
        def choose(label, col):
            vals = sorted(text_col(data, col).unique().tolist()) if col in data else []
            return st.selectbox(label, ["ALL"] + vals)
        status = choose("Status", "STATUS"); location = choose("Location", "LOCATION"); vessel = choose("Vessel", "VESSEL")
        sex = choose("Sex", "SEX")
        st.divider(); st.caption("Filters apply to charts, KPIs, roster, and chatbot context.")
    result = data.copy()
    if search:
        result = result[text_col(result,"PERSON").str.contains(search.upper(), na=False)] if "PERSON" in result else result
    for col, value in [("STATUS",status),("LOCATION",location),("VESSEL",vessel),("SEX",sex)]:
        if value != "ALL" and col in result: result = result[text_col(result,col) == value]
    return result

def answer_question(question, data):
    q = question.lower().strip(); status = text_col(data,"STATUS"); total = len(data)
    if not q: return "Ask me about counts, statuses, locations, vessels, ratings, due-off dates, or a person's record."
    if any(word in q for word in ["how many", "count", "total"]):
        for key in sorted(status.unique(), key=len, reverse=True):
            if key.lower() in q: return f"There are **{int((status == key).sum())}** records with status **{key}** in the current filtered view."
        if "location" in q and "LOCATION" in data: return "Locations: " + ", ".join(f"**{k}** ({v})" for k,v in text_col(data,"LOCATION").value_counts().head(8).items())
        return f"The current filtered view contains **{total}** personnel records."
    if "status" in q or "breakdown" in q: return "Status breakdown: " + ", ".join(f"**{k}** ({v})" for k,v in status.value_counts().items())
    if "location" in q and "LOCATION" in data: return "Top locations: " + ", ".join(f"**{k}** ({v})" for k,v in text_col(data,"LOCATION").value_counts().head(8).items())
    if "vessel" in q and "VESSEL" in data: return "Top vessels: " + ", ".join(f"**{k}** ({v})" for k,v in text_col(data,"VESSEL").value_counts().head(8).items())
    if "no show" in q: return f"There are **{int((status == 'NO SHOW').sum())}** no-show records in the current filtered view."
    if "pending" in q: return f"There are **{int((status == 'PENDING').sum())}** pending records in the current filtered view."
    if "travel confirmed" in q: return f"There are **{int((status == 'TRAVEL CONFIRMED').sum())}** travel-confirmed records in the current filtered view."
    if "due off" in q or "due-off" in q:
        col = "DUE OFF DT" if "DUE OFF DT" in data else None
        if col: return f"**{int(data[col].notna().sum())}** filtered records have a due-off date."
    if "PERSON" in data:
        matches = data[text_col(data,"PERSON").str.contains(q.upper(), na=False)]
        if len(matches):
            row = matches.iloc[0]; return f"I found **{row['PERSON']}** — status: **{row.get('STATUS','Unknown')}**, location: **{row.get('LOCATION','Unknown')}**, vessel: **{row.get('VESSEL','Unknown')}**."
    return "I can answer questions using the records currently shown. Try: *How many are pending?*, *Where are personnel located?*, or search a person's name."

df = load_data()
if df is None:
    st.error("No supported dataset found. Add the Epic Fury CSV or XLSX to the repository root."); st.stop()
filtered = apply_filters(df)
status = text_col(filtered,"STATUS")
counts = status.value_counts()

st.title("⚓ Epic Fury Movement Command Center")
st.caption("Personnel movement, travel readiness, and operational accountability")
metrics = [("FILTERED RECORDS",len(filtered)),("ON LOCATION",counts.get("ON LOCATION",0)),("PENDING",counts.get("PENDING",0)),("TRAVEL CONFIRMED",counts.get("TRAVEL CONFIRMED",0)),("NO SHOW",counts.get("NO SHOW",0)),("ATTENTION ITEMS",sum(counts.get(k,0) for k in ["NO SHOW","FLAGGED","FY27 LOA NEEDED"]))]
cols = st.columns(6)
for col,(label,value) in zip(cols,metrics): col.metric(label,int(value))

st.divider()
chart_left, chart_right = st.columns(2)
if len(filtered):
    status_df = status.value_counts().rename_axis("Status").reset_index(name="Count")
    fig = px.bar(status_df,x="Status",y="Count",color="Status",color_discrete_map=STATUS_COLORS,title="Movement status")
    fig.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",showlegend=False)
    chart_left.plotly_chart(fig,use_container_width=True)
    if "LOCATION" in filtered:
        loc = text_col(filtered,"LOCATION").value_counts().head(10).rename_axis("Location").reset_index(name="Count")
        fig2 = px.bar(loc,x="Count",y="Location",orientation="h",color="Count",color_continuous_scale="Blues",title="Top locations")
        fig2.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
        chart_right.plotly_chart(fig2,use_container_width=True)

st.divider()
tab_roster, tab_timeline, tab_chat = st.tabs(["📋 Roster", "🗓️ Travel timeline", "💬 Ask the tracker"])
with tab_roster:
    st.subheader("Filtered movement roster")
    cols = [c for c in ["STATUS","EXT_STATUS","PERSON","SEX","RATING","VESSEL","LOCATION","START","IN_OUT","DATE_1","DATE_2","DOA","DUE OFF DT","COMMENTS"] if c in filtered]
    view = filtered[cols].copy() if cols else filtered.copy()
    for col in view.columns:
        if pd.api.types.is_datetime64_any_dtype(view[col]): view[col] = view[col].dt.strftime("%Y-%m-%d")
    st.dataframe(view.head(500),use_container_width=True,hide_index=True)
    st.download_button("Download filtered CSV",filtered.to_csv(index=False).encode("utf-8"),"epic_fury_filtered.csv","text/csv")
with tab_timeline:
    st.subheader("Upcoming / recorded travel dates")
    date_col = "DATE_1" if "DATE_1" in filtered else ("DATE_2" if "DATE_2" in filtered else None)
    if date_col and filtered[date_col].notna().any():
        timeline = filtered.dropna(subset=[date_col]).sort_values(date_col).copy(); timeline["Date"] = timeline[date_col]
        timeline["Person"] = timeline.get("PERSON", pd.Series("Record",index=timeline.index))
        fig = px.scatter(timeline,x="Date",y="STATUS",color="STATUS",hover_name="Person",color_discrete_map=STATUS_COLORS,title="Movement activity by date")
        fig.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig,use_container_width=True)
    else: st.info("No travel dates are available in the current filtered view.")
with tab_chat:
    st.subheader("Ask the Epic Fury tracker")
    st.caption("This lightweight assistant answers from the currently filtered dataset; it does not send records to an external AI service.")
    if "chat_history" not in st.session_state: st.session_state.chat_history = []
    for role,message in st.session_state.chat_history: st.chat_message(role).markdown(message)
    prompt = st.chat_input("Ask: How many are pending? Where are personnel located?")
    if prompt:
        st.session_state.chat_history.append(("user",prompt)); response = answer_question(prompt,filtered); st.session_state.chat_history.append(("assistant",response)); st.rerun()
