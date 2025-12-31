import streamlit as st
import pandas as pd
import plotly.express as px
import uuid

st.set_page_config(page_title="HydroScope", layout="wide")

# ----------------------------
# SESSION STATE
# ----------------------------
if "has_predicted" not in st.session_state: st.session_state["has_predicted"] = False
if "prediction_log" not in st.session_state: st.session_state["prediction_log"] = []
if "prediction_log_water" not in st.session_state: st.session_state["prediction_log_water"] = []
if "forecast_log" not in st.session_state: st.session_state["forecast_log"] = []
if "crop_log" not in st.session_state: st.session_state["crop_log"] = []
if "weather_log_data" not in st.session_state:
    st.session_state["weather_log_data"] = pd.DataFrame(columns=["Date", "Temperature (°C)", "Rainfall (mm)", "ETo (mm/day)"])
if "eto_value_input" not in st.session_state: st.session_state["eto_value_input"] = 5.0
if "plots_data" not in st.session_state: st.session_state["plots_data"] = {}
if "active_plot_id" not in st.session_state: st.session_state["active_plot_id"] = None
if "saved_supply_plan_data" not in st.session_state: st.session_state["saved_supply_plan_data"] = None
if "display_supply_results" not in st.session_state: st.session_state["display_supply_results"] = False

# ----------------------------
# CROP DATA
# ----------------------------
crop_options_detailed = {
    "Maize": {
        "Duration_Days": {"Initial": 20, "Development": 35, "Mid": 45, "Late": 26},
        "Kc_Values": {"Initial": 0.3, "Mid": 1.2, "End": 0.7}
    },
    "Beans": {
        "Duration_Days": {"Initial": 15, "Development": 25, "Mid": 30, "Late": 10},
        "Kc_Values": {"Initial": 0.4, "Mid": 1.1, "End": 0.4}
    },
    "Tomatoes": {
        "Duration_Days": {"Initial": 30, "Development": 40, "Mid": 60, "Late": 20},
        "Kc_Values": {"Initial": 0.4, "Mid": 1.1, "End": 0.7}
    },
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
page = st.sidebar.radio("Navigate", [
    "🌤️ Weather Guide",
    "🌱 Crop Water Guide",
    "🏡 Farm Setup & Plots",
    "💧 Supply Planner",
    "💳 Subscription",
    "About"
], key="main_navigation")

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
        log_weather_btn = st.form_submit_button("➕ Log New Weather Data")

    if log_weather_btn:
        new_entry = {"Date": date_entry, "Temperature (°C)": temp_entry, "Rainfall (mm)": rain_entry, "ETo (mm/day)": eto_entry}
        st.session_state["weather_log_data"] = pd.concat([st.session_state["weather_log_data"], pd.DataFrame([new_entry])], ignore_index=True)
        st.session_state["eto_value_input"] = float(eto_entry)
        st.success("Weather data logged!")

# ----------------------------
# 4. SUPPLY PLANNER
# ----------------------------
elif page == "💧 Supply Planner":
    st.title("💧 Water Supply Planner")
    
    # Context setup
    active_id = st.session_state.get("active_plot_id")
    if active_id and active_id in st.session_state["plots_data"]:
        p = st.session_state["plots_data"][active_id]
        acres, crop_name = p["acres"], p["crop_type"]
        st.info(f"Active Plot: {p['name']}")
    else:
        acres = st.session_state.get("manual_acres", 1.0)
        crop_name = st.session_state.get("crop_selection_cw", "Maize")

    flow = st.number_input("Flow Rate (L/hr)", value=1200.0)
    days = st.slider("Days to Apply", 1, 14, 7)

    if st.button("🚀 Generate Irrigation Plan"):
        crop_data = crop_options_detailed.get(crop_name)
        vals = [v for v in crop_data["Kc_Values"].values() if v is not None] if crop_data and crop_data.get("Kc_Values") else [1.0]
        avg_kc = sum(vals)/len(vals)
        
        daily_l = (st.session_state.get("avg_daily_eto_cw", 5.0) * avg_kc * 4047 * acres)
        eff = st.session_state.get("efficiency_percent_cw", 80) / 100
        net_daily_l = daily_l / eff
        hrs = (net_daily_l * days / flow) / days
        
        st.subheader("💦 Plan Results")
        st.success(f"Irrigate for {hrs:.1f} hours/day.")

# ----------------------------
# 5. SUBSCRIPTION
# ----------------------------
elif page == "💳 Subscription":
    st.title("💳 Subscription & Billing")
    st.info("Currently on the **Free Tier**.")
    st.markdown("""
    - **Basic Features:** Unlimited weather logging and plot tracking.
    - **Pro Features:** Coming soon (Satellite ETo integration, multi-user access).
    """)

# ----------------------------
# 6. ABOUT
# ----------------------------
elif page == "About":
    st.title("📖 About HydroScope")
    st.write("HydroScope is a precision irrigation planner designed to help farmers optimize water use based on local weather and crop types.")
    st.caption("Version 2.5 | 2025 Release")

