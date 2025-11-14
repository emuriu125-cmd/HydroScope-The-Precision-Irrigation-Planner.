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

def calculate_stage_based_water(acres, avg_daily_eto, effective_rain_weekly, efficiency_percent, crop_data):
    area_sq_meters = acres * 4046.86
    efficiency_decimal = efficiency_percent / 100
    total_gross_irrigation_mm = 0
    avg_effective_rain_daily = (effective_rain_weekly / 7) if effective_rain_weekly else 0

    kc_init = crop_data["Kc_Values"]["Initial"]
    kc_mid = crop_data["Kc_Values"]["Mid"]
    kc_end = crop_data["Kc_Values"]["End"]

    stages = ["Initial", "Development", "Mid", "Late"]
    for stage in stages:
        duration_days = crop_data["Duration_Days"][stage]
        if stage == "Initial": kc_stage_avg = kc_init
        elif stage == "Development": kc_stage_avg = (kc_init + kc_mid) / 2
        elif stage == "Mid": kc_stage_avg = kc_mid
        else: kc_stage_avg = (kc_mid + kc_end) / 2

        etc_daily_mm = kc_stage_avg * avg_daily_eto
        net_irrigation_stage_mm = max(0, (etc_daily_mm - avg_effective_rain_daily) * duration_days)
        gross_irrigation_stage_mm = net_irrigation_stage_mm / efficiency_decimal if efficiency_decimal > 0 else net_irrigation_stage_mm
        total_gross_irrigation_mm += gross_irrigation_stage_mm

    total_water_liters = total_gross_irrigation_mm * area_sq_meters
    return total_water_liters, total_gross_irrigation_mm

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
    st.experimental_rerun()

def deactivate_plot():
    st.session_state["active_plot_id"] = None

def clear_all_plots():
    st.session_state["plots_data"].clear()
    st.session_state["active_plot_id"] = None
    st.rerun()

def clear_supply_results():
    st.session_state["display_supply_results"] = False

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
    st.markdown("Log your daily weather observations to track local trends. This data helps you get accurate water needs.")

    with st.form(key='weather_form'):
        colD1, colD2, colD3, colD4 = st.columns(4)
        date_entry = colD1.date_input("Date")
        temp_entry = colD2.number_input("Avg Temp (°C)", value=25.0)
        rain_entry = colD3.number_input("Rainfall (mm)", value=0.0)
        eto_entry = colD4.number_input("Avg ETo (mm/day)", value=5.0)
        log_weather_btn = st.form_submit_button("➕ Log New Weather Data")

    if log_weather_btn:
        new_entry = {"Date": date_entry, "Temperature (°C)": temp_entry, "Rainfall (mm)": rain_entry, "ETo (mm/day)": eto_entry}
        st.session_state["weather_log_data"] = pd.concat(
            [st.session_state["weather_log_data"], pd.DataFrame([new_entry])], ignore_index=True)
        st.session_state["eto_value_input"] = eto_entry
        st.success("Weather data logged successfully! Defaults updated.")

    if not st.session_state["weather_log_data"].empty:
        display_weather_data = st.session_state["weather_log_data"].copy()
        display_weather_data["Date"] = pd.to_datetime(display_weather_data["Date"])

        avg_temp = display_weather_data["Temperature (°C)"].mean()
        avg_rain = display_weather_data["Rainfall (mm)"].sum()
        avg_eto = display_weather_data["ETo (mm/day)"].mean()

        colM1, colM2, colM3 = st.columns(3)
        colM1.metric("Avg Temp", f"{avg_temp:.1f} °C")
        colM2.metric("Total Rain", f"{avg_rain:.1f} mm")
        colM3.metric("Avg ETo", f"{avg_eto:.1f} mm/day")

        if st.button("🚀 Use Avg ETo as Default"):
            st.session_state["eto_value_input"] = avg_eto
            st.info(f"Average ETo ({avg_eto:.1f}) set as default.")

        st.subheader("📋 Weather Log")
        st.table(display_weather_data.set_index("Date").sort_index())

        if len(display_weather_data) >= 2:
            fig1 = px.scatter(display_weather_data, x="Temperature (°C)", y="ETo (mm/day)", trendline="ols",
                              title="ETo vs Temperature")
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("Add more entries for trend analysis.")

        if st.button("🧹 Clear Weather Log"):
            st.session_state["weather_log_data"] = pd.DataFrame(columns=["Date", "Temperature (°C)", "Rainfall (mm)", "ETo (mm/day)"])
            
# ----------------------------
# 2. CROP WATER GUIDE
# ----------------------------
elif page == "🌱 Crop Water Guide":
    st.title("🌱 Crop Water Guide")
    st.markdown("Enter your crop parameters here. The calculation happens in the **💧 Supply Planner**.")

    # Keep ETo in sync from other pages
    st.session_state["avg_daily_eto_cw"] = st.session_state.get("eto_value_input", 5.0)

    # Detect Active Plot
    if (
        st.session_state.get("active_plot_id") and 
        st.session_state["active_plot_id"] in st.session_state["plots_data"]
    ):
        active_plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]

        st.markdown(
            f"###### *Using Active Plot: {active_plot['name']} "
            f"({active_plot['acres']} acres of {active_plot['crop_type']})*"
        )

        selected_crop_name = active_plot["crop_type"]
        default_acres = active_plot["acres"]

        # 🔥 FIX: force acres to match the active plot
        st.session_state["manual_acres"] = default_acres

        disabled_inputs = True

    else:
        selected_crop_name = None
        disabled_inputs = False

        # Only apply default 1 acre when NOT using a plot
        st.session_state.setdefault("manual_acres", 1.0)

    # Initialize other session state defaults (safe)
    defaults = {
        "crop_selection_cw": list(crop_options_detailed.keys())[0],
        "avg_daily_eto_cw": st.session_state["avg_daily_eto_cw"],
        "effective_rain_weekly_cw": 0.0,
        "efficiency_percent_cw": 80,
        "c_source_cap": 1000.0,
        "c_days_apply": 7,
        "c_source_type": "Pump"
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

    # ----------------------------
    # 🌿 2x2 GRID — Row 1
    # ----------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.session_state["manual_acres"] = st.number_input(
            "Acres",
            value=st.session_state["manual_acres"],
            min_value=0.1, step=0.1,
            disabled=disabled_inputs
        )

        # Auto-select the crop
        crop_list = list(crop_options_detailed.keys())
        crop_index = crop_list.index(selected_crop_name) if selected_crop_name in crop_list else 0

        st.session_state["crop_selection_cw"] = st.selectbox(
            "Crop Type",
            options=crop_list,
            index=crop_index,
            disabled=disabled_inputs
        )

    with col2:
        st.session_state["avg_daily_eto_cw"] = st.number_input(
            "Avg Daily ETo (mm/day)",
            value=st.session_state["avg_daily_eto_cw"]
        )

        st.session_state["effective_rain_weekly_cw"] = st.number_input(
            "Avg Effective Rain (mm/week)",
            value=st.session_state["effective_rain_weekly_cw"]
        )

    # ----------------------------
    # 🌿 2x2 GRID — Row 2
    # ----------------------------
    col3, col4 = st.columns(2)

    with col3:
        st.session_state["efficiency_percent_cw"] = st.number_input(
            "Irrigation Efficiency (%)",
            value=st.session_state["efficiency_percent_cw"],
            min_value=1, max_value=100
        )

    with col4:
        st.session_state["c_source_type"] = st.selectbox(
            "Water Source Type",
            options=["Tank", "Pipes", "Pump"],
            index=["Tank", "Pipes", "Pump"].index(st.session_state["c_source_type"])
        )

    # ----------------------------
    # 📱 Help Expander
    # ----------------------------
    with st.expander("📱 Need Help Getting These Values?"):
        st.markdown("""
        - 🌤️ **ETo:** Use *FAO ETo Calculator*
        - 🌾 **Kc Values:** Try **FAO CropWat Mobile App**
        - ☔ **Rainfall:** Use **RainViewer** or **AccuWeather**
        - 💧 **Efficiency:**  
            - Drip: **75–90%**  
            - Sprinkler: **60–70%**  
            - Furrow: **40–60%**  
        """)

        
# ----------------------------
# 3. FARM SETUP & PLOTS
# ----------------------------
elif page == "🏡 Farm Setup & Plots":
    st.title("🏡 Farm Setup & Plots Management")
    with st.form(key='new_plot_form'):
        colP1, colP2, colP3 = st.columns(3)
        plot_name = colP1.text_input("Plot Name", value=f"Plot {len(st.session_state['plots_data']) + 1}")
        plot_acres = colP2.number_input("Acres", min_value=0.1, value=1.0)
        plot_crop = colP3.selectbox("Crop Type", list(crop_options_detailed.keys()))
        add_plot_btn = st.form_submit_button("➕ Save New Plot")

    if add_plot_btn:
        new_plot_id = str(uuid.uuid4())
        st.session_state["plots_data"][new_plot_id] = {"id": new_plot_id, "name": plot_name, "acres": plot_acres, "crop_type": plot_crop}
        st.success(f"Plot '{plot_name}' saved!")

    if not st.session_state["plots_data"]:
        st.info("No plots yet. Add one above.")
    else:
        st.button("🧹 Clear All Plots", on_click=clear_all_plots)
        # Reduced from 5 columns to 3 columns to make the display more compact
        for plot_id, plot in st.session_state["plots_data"].items():
            is_active = (st.session_state["active_plot_id"] == plot_id)
            status = "✅ Active" if is_active else "❌ Inactive"
            
            # Use 3 columns instead of 5
            col_d1, col_d2, col_d3 = st.columns(3)
            
            col_d1.metric("Name", plot["name"])
            # Combined acres and crop type into a single column's metric
            col_d2.metric("Details", f"{plot['acres']} acres | {plot['crop_type']}")
            
            with col_d3:
                # Placed buttons in the final column, using smaller 'st.button' calls
                st.markdown(f"**Status:** {status}")
                if is_active:
                    st.button("Deactivate", key=f"deact_{plot_id}", on_click=deactivate_plot)
                else:
                    st.button("Activate", key=f"act_{plot_id}", on_click=set_active_plot, args=(plot_id,))
                # Moved the delete button inline as well
                st.button("Delete", key=f"del_{plot_id}", on_click=delete_plot, args=(plot_id,))

# ----------------------------
# 4. SUPPLY PLANNER
# ----------------------------
elif page == "💧 Supply Planner":
    st.title("💧 Water Supply Planner")
    st.button("🔄 Recalculate Plan", on_click=lambda: st.session_state.update(display_supply_results=True))

    # ✅ Ensure manual_acres and crop_selection_cw exist before using them
    st.session_state.setdefault("manual_acres", 1.0)
    st.session_state.setdefault("crop_selection_cw", "Maize")

    if st.session_state.get("active_plot_id") and st.session_state["active_plot_id"] in st.session_state["plots_data"]:
        active_plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        acres, crop_name = active_plot["acres"], active_plot["crop_type"]
        st.markdown(f"###### Using Active Plot: {active_plot['name']}")
    else:
        acres, crop_name = st.session_state["manual_acres"], st.session_state["crop_selection_cw"]

    avg_daily_eto = st.session_state.get("avg_daily_eto_cw", st.session_state["eto_value_input"])
    effective_rain_weekly = st.session_state.get("effective_rain_weekly_cw", 0.0)
    efficiency_percent = st.session_state.get("efficiency_percent_cw", 80)
    source_capacity_lph = st.session_state.get("c_source_cap", 1000.0)
    days_to_apply = st.session_state.get("c_days_apply", 7)
    water_source_type = st.session_state.get("c_source_type", "Pump")

    if st.session_state["display_supply_results"]:
        try:
            crop_data = crop_options_detailed.get(crop_name, {"Duration_Days": None, "Kc_Values": None})
            if crop_data["Duration_Days"]:
                total_water_liters, total_gross_irrigation_mm = calculate_stage_based_water(
                    acres, avg_daily_eto, effective_rain_weekly, efficiency_percent, crop_data)
                st.subheader("💦 Results")
                colR1, colR2, colR3 = st.columns(3)
                colR1.metric("Total Water Needed", f"{total_water_liters:,.0f} L")
                colR2.metric("Gross Irrigation", f"{total_gross_irrigation_mm:.1f} mm")
                colR3.metric("Acres", f"{acres:.1f}")

                if source_capacity_lph > 0 and days_to_apply > 0:
                    total_hours_needed = total_water_liters / source_capacity_lph
                    hours_per_day = total_hours_needed / days_to_apply
                    st.success(f"Run **{water_source_type}** for ~{hours_per_day:.1f} hrs/day for {days_to_apply} days.")
            else:
                st.warning("Invalid or missing crop data.")
        except Exception as e:
            st.error(f"Error during calculation: {e}")

        st.button("🧹 Clear Results", on_click=clear_supply_results)
    else:
        st.info("Results cleared. Adjust inputs in Crop Water Guide and recalc.")

# ----------------------------
# 5. SUBSCRIPTION
# ----------------------------
elif page == "💳 Subscription":
    st.title("💳 Upgrade Your Plan")
    st.markdown("Subscription options will appear here soon.")

# ----------------------------
# 6. ABOUT
# ----------------------------
elif page == "About":
    st.title("About HydroScope")
    st.markdown("HydroScope helps farmers manage water efficiently using FAO-based crop coefficients and ETo data.")
    st.markdown("Contact: emuriu125@gmail.com/0769124686.")
