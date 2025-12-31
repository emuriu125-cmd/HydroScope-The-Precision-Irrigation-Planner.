import streamlit as st
import pandas as pd
import plotly.express as px
import uuid

st.set_page_config(page_title="HydroScope", layout="wide")

# ----------------------------
# SESSION STATE INITIALIZATION
# ----------------------------
if "plots_data" not in st.session_state: st.session_state["plots_data"] = {}
if "active_plot_id" not in st.session_state: st.session_state["active_plot_id"] = None
if "weather_log_data" not in st.session_state:
    st.session_state["weather_log_data"] = pd.DataFrame(columns=["Date", "Temperature (°C)", "Rainfall (mm)", "ETo (mm/day)"])
if "eto_value_input" not in st.session_state: st.session_state["eto_value_input"] = 5.0
if "manual_acres" not in st.session_state: st.session_state["manual_acres"] = 1.0

# ----------------------------
# CROP DATA
# ----------------------------
crop_options_detailed = {
    "Maize": {"Duration_Days": {"Initial": 20, "Development": 35, "Mid": 45, "Late": 26}, "Kc_Values": {"Initial": 0.3, "Mid": 1.2, "End": 0.7}},
    "Beans": {"Duration_Days": {"Initial": 15, "Development": 25, "Mid": 30, "Late": 10}, "Kc_Values": {"Initial": 0.4, "Mid": 1.1, "End": 0.4}},
    "Tomatoes": {"Duration_Days": {"Initial": 30, "Development": 40, "Mid": 60, "Late": 20}, "Kc_Values": {"Initial": 0.4, "Mid": 1.1, "End": 0.7}},
    "Other / Custom Crop": {"Duration_Days": None, "Kc_Values": None}
}

# ----------------------------
# HELPERS
# ----------------------------
def set_active_plot(plot_id):
    st.session_state["active_plot_id"] = plot_id

def delete_plot(plot_id):
    if plot_id in st.session_state["plots_data"]:
        del st.session_state["plots_data"][plot_id]
    if st.session_state["active_plot_id"] == plot_id:
        st.session_state["active_plot_id"] = None
    st.rerun()

def deactivate_plot():
    st.session_state["active_plot_id"] = None

def clear_all_plots():
    st.session_state["plots_data"].clear()
    st.session_state["active_plot_id"] = None
    st.rerun()

# ----------------------------
# SIDEBAR
# ----------------------------
st.sidebar.title("⚙️ HydroScope Controls")
page = st.sidebar.radio("Navigate", ["🌤️ Weather Guide", "🌱 Crop Water Guide", "🏡 Farm Setup & Plots", "💧 Supply Planner"])

# ----------------------------
# 1. WEATHER GUIDE
# ----------------------------
if page == "🌤️ Weather Guide":
    st.title("🌤️ Local Weather Data & ETo Guide")
    with st.form(key='weather_form'):
        colD1, colD2, colD3, colD4 = st.columns(4)
        date_entry = colD1.date_input("Date")
        temp_entry = colD2.number_input("Avg Temp (°C)", value=25.0)
        rain_entry = colD3.number_input("Rainfall (mm)", value=0.0)
        eto_entry = colD4.number_input("Avg ETo (mm/day)", value=5.0)
        if st.form_submit_button("➕ Log New Weather Data"):
            new_entry = {"Date": date_entry, "Temperature (°C)": temp_entry, "Rainfall (mm)": rain_entry, "ETo (mm/day)": eto_entry}
            st.session_state["weather_log_data"] = pd.concat([st.session_state["weather_log_data"], pd.DataFrame([new_entry])], ignore_index=True)
            st.session_state["eto_value_input"] = float(eto_entry)
            st.success("Weather data logged!")

# ----------------------------
# 2. CROP WATER GUIDE
# ----------------------------
elif page == "🌱 Crop Water Guide":
    st.title("🌱 Crop Water Guide")
    
    # Session State defaults for this page
    defaults = {
        "crop_selection_cw": "Maize",
        "avg_daily_eto_cw": float(st.session_state.get("eto_value_input", 5.0)),
        "effective_rain_weekly_cw": 0.0,
        "efficiency_percent_cw": 80,
        "c_source_type": "Pump"
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

    # Active Plot Detection
    active_plot_id = st.session_state.get("active_plot_id")
    if active_plot_id and active_plot_id in st.session_state["plots_data"]:
        active_plot = st.session_state["plots_data"][active_plot_id]
        st.info(f"Using Active Plot: {active_plot['name']}")
        selected_crop_name = active_plot["crop_type"]
        st.session_state["manual_acres"] = float(active_plot["acres"])
        disabled_inputs = True
    else:
        selected_crop_name = st.session_state["crop_selection_cw"]
        disabled_inputs = False

    col1, col2 = st.columns(2)
    with col1:
        st.session_state["manual_acres"] = st.number_input("Acres", value=float(st.session_state["manual_acres"]), min_value=0.1, disabled=disabled_inputs)
        crop_list = list(crop_options_detailed.keys())
        st.session_state["crop_selection_cw"] = st.selectbox("Crop", options=crop_list, index=crop_list.index(selected_crop_name) if selected_crop_name in crop_list else 0, disabled=disabled_inputs)
    with col2:
        st.session_state["avg_daily_eto_cw"] = st.number_input("Avg Daily ETo (mm/day)", value=float(st.session_state["avg_daily_eto_cw"]))
        st.session_state["effective_rain_weekly_cw"] = st.number_input("Rain (mm/week)", value=float(st.session_state["effective_rain_weekly_cw"]))

# ----------------------------
# 3. FARM SETUP & PLOTS
# ----------------------------
elif page == "🏡 Farm Setup & Plots":
    st.title("🏡 Farm Setup & Plots")
    with st.form(key='new_plot_form'):
        colP1, colP2, colP3 = st.columns(3)
        plot_name = colP1.text_input("Plot Name", value=f"Plot {len(st.session_state['plots_data']) + 1}")
        plot_acres = colP2.number_input("Acres", min_value=0.1, value=1.0)
        plot_crop = colP3.selectbox("Crop Type", list(crop_options_detailed.keys()))
        if st.form_submit_button("➕ Save New Plot"):
            pid = str(uuid.uuid4())
            st.session_state["plots_data"][pid] = {"id": pid, "name": plot_name, "acres": plot_acres, "crop_type": plot_crop}
            st.rerun()

    for pid, p in st.session_state["plots_data"].items():
        c1, c2, c3 = st.columns(3)
        c1.metric("Name", p["name"])
        c2.metric("Details", f"{p['acres']} ac | {p['crop_type']}")
        with c3:
            if st.session_state["active_plot_id"] == pid:
                st.button("Deactivate", key=f"de_{pid}", on_click=deactivate_plot)
            else:
                st.button("Activate", key=f"ac_{pid}", on_click=set_active_plot, args=(pid,))
            st.button("Delete", key=f"del_{pid}", on_click=delete_plot, args=(pid,))

# ----------------------------
# 4. SUPPLY PLANNER
# ----------------------------
elif page == "💧 Supply Planner":
    st.title("💧 Water Supply Planner")
    
    # Get current context
    active_id = st.session_state.get("active_plot_id")
    if active_id and active_id in st.session_state["plots_data"]:
        p = st.session_state["plots_data"][active_id]
        acres, crop_name = p["acres"], p["crop_type"]
    else:
        acres = st.session_state.get("manual_acres", 1.0)
        crop_name = st.session_state.get("crop_selection_cw", "Maize")

    avg_kc = 1.0
    crop_data = crop_options_detailed.get(crop_name)
    if crop_data and crop_data["Kc_Values"]:
        vals = [v for v in crop_data["Kc_Values"].values() if v is not None]
        avg_kc = sum(vals)/len(vals) if vals else 1.0

    daily_l = (st.session_state.get("avg_daily_eto_cw", 5.0) * avg_kc * 4047 * acres)
    rain_reduction = (st.session_state.get("effective_rain_weekly_cw", 0.0) / 7) * 4047 * acres
    net_daily_l = max(daily_l - rain_reduction, 0.0) / (st.session_state.get("efficiency_percent_cw", 80) / 100)

    flow = st.number_input("Flow Rate (L/hr)", value=1200.0, min_value=100.0)
    days = st.slider("Days to Apply", 1, 14, 7)
    
    hrs_per_day = (net_daily_l * days / flow) / days
    st.success(f"Irrigate for {hrs_per_day:.1f} hours/day.")
