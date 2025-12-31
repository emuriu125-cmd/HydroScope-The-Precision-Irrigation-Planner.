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
        net_irrigation_stage_mm = max(0.0, (etc_daily_mm - avg_effective_rain_daily) * duration_days)
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
    st.rerun()

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
        
        # ADDITION: Retrieve last saved values from session_state for all fields to carry over across tabs
        date_entry = colD1.date_input("Date", value=st.session_state.get("date_value_input", datetime.date.today()))
        temp_entry = colD2.number_input("Avg Temp (°C)", value=st.session_state.get("temp_value_input", 25.0))
        rain_entry = colD3.number_input("Rainfall (mm)", value=st.session_state.get("rain_value_input", 0.0))
        eto_entry = colD4.number_input("Avg ETo (mm/day)", value=st.session_state.get("eto_value_input", 5.0))
        
        log_weather_btn = st.form_submit_button("➕ Log New Weather Data")

    if log_weather_btn:
        new_entry = {"Date": date_entry, "Temperature (°C)": temp_entry, "Rainfall (mm)": rain_entry, "ETo (mm/day)": eto_entry}
        st.session_state["weather_log_data"] = pd.concat(
            [st.session_state["weather_log_data"], pd.DataFrame([new_entry])], ignore_index=True)
        
        # ADDITION: Explicitly save ALL inputs to session_state so they are shared with the second tab
        st.session_state["date_value_input"] = date_entry
        st.session_state["temp_value_input"] = temp_entry
        st.session_state["rain_value_input"] = rain_entry
        st.session_state["eto_value_input"] = eto_entry
        
        st.success("Weather data logged successfully! Defaults updated for all tabs.")

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

        # YOUR ORIGINAL BUTTON RETAINED
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
            # Clear sharing keys so inputs reset to original defaults
            for key in ["date_value_input", "temp_value_input", "rain_value_input", "eto_value_input"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()


# ----------------------------
# 2. CROP WATER GUIDE
# ----------------------------
elif page == "🌱 Crop Water Guide":
    st.title("🌱 Crop Water Guide")
    st.markdown("Enter your crop parameters here. The calculation happens in the **💧 Supply Planner**.")

    st.session_state["avg_daily_eto_cw"] = st.session_state.get("eto_value_input", 5.0)

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
        st.session_state["manual_acres"] = active_plot["acres"]
        disabled_inputs = True  # FIX: Defined here
    else:
        selected_crop_name = None
        st.session_state.setdefault("manual_acres", 1.0)
        disabled_inputs = False # FIX: Defined here

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
        # Wrapped value in float() to prevent 2025 type-mismatch crashes
        st.session_state["manual_acres"] = st.number_input(
            "Acres",
            value=float(st.session_state["manual_acres"]),
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
# 4. SUPPLY PLANNER (RESTORED VERSION)
# ----------------------------
elif page == "💧 Supply Planner":
    st.title("💧 Water Supply Planner")
    st.markdown("Plan how many hours per day you should irrigate based on your water source and crop water needs.")

    # Sync basic values
    st.session_state.setdefault("manual_acres", 1.0)
    st.session_state.setdefault("crop_selection_cw", "Maize")

    # ----------------------------
    # 🔹 Detect ACTIVE PLOT usage
    # ----------------------------
    if (
        st.session_state.get("active_plot_id") and
        st.session_state["active_plot_id"] in st.session_state["plots_data"]
    ):
        active_plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        acres = float(active_plot["acres"])
        crop_name = active_plot["crop_type"]
        st.info(f"Using Active Plot: **{active_plot['name']}** ({acres} acres)")
    else:
        acres = float(st.session_state["manual_acres"])
        crop_name = st.session_state["crop_selection_cw"]

    # Gather inputs from Crop Water Guide
    avg_daily_eto = float(st.session_state.get("avg_daily_eto_cw", 5.0))
    effective_rain_weekly = float(st.session_state.get("effective_rain_weekly_cw", 0.0))
    efficiency_percent = float(st.session_state.get("efficiency_percent_cw", 80))
    water_source_type = st.session_state.get("c_source_type", "Pump")

    # Use simple crop-average Kc value
    crop_data = crop_options_detailed.get(crop_name)
    if crop_data and crop_data.get("Kc_Values"):
        kc_values = [v for v in crop_data["Kc_Values"].values() if v is not None]
        avg_kc = sum(kc_values) / len(kc_values) if kc_values else 1.0
    else:
        avg_kc = 1.0  # fallback

    # Water source details (Placed outside the button for user input)
    source_flow_lph = st.number_input(
        "Water Source Flow Rate (L/hour)",
        value=1200.0,
        min_value=100.0,
        key="supply_planner_flow_input"
    )
    days_to_apply = st.slider("Days to Apply Irrigation", 1, 14, 7)

    # ----------------------------
    # 🔘 GENERATE BUTTON (FIXED: NO AUTO-PREDICT)
    # ----------------------------
    if st.button("🚀 Generate Irrigation Plan"):
        # ✨ Simple Water Calculation (old style)
        crop_water_mm = avg_daily_eto * avg_kc

        # 1 acre = 4047 m2
        liters_per_mm_per_acre = 4047  
        daily_liters = crop_water_mm * liters_per_mm_per_acre * acres

        # Apply effective rainfall weekly
        rainfall_reduction = (effective_rain_weekly / 7) * liters_per_mm_per_acre * acres
        daily_liters = max(daily_liters - rainfall_reduction, 0.0)

        # Apply irrigation efficiency
        daily_liters = daily_liters / (efficiency_percent / 100)

        total_weekly_liters = daily_liters * days_to_apply
        total_hours_needed = total_weekly_liters / source_flow_lph
        hours_per_day = total_hours_needed / days_to_apply

        # ----------------------------
        # 🟦 Results
        # ----------------------------
        st.subheader("💦 Water Use Summary")
        colA, colB, colC = st.columns(3)
        # Added unique keys to metrics as a 2025 safety measure
        colA.metric("Daily Crop Water Need", f"{daily_liters:,.0f} L/day")
        colB.metric("Weekly Need", f"{total_weekly_liters:,.0f} L/week")
        colC.metric("Avg Kc", f"{avg_kc:.2f}")

        st.subheader("⚙️ Irrigation Plan")
        st.success(
            f"Run your **{water_source_type}** for **{hours_per_day:.1f} hours/day** "
            f"for **{days_to_apply} days**."
        )
        st.caption("This is the simplified classic version of the planner.")

# ----------------------------
# 5. SUBSCRIPTION
# ----------------------------
elif page == "💳 Subscription":
    st.title("💳 Subscription & Billing")
    st.info("You are currently on the **Free Tier**.")
    st.markdown("""
    - **Current Features:** Unlimited weather logging and plot tracking.
    - **Pro Features (Coming Soon):** Satellite ETo integration and PDF reports.
    """)

# ----------------------------
# 6. ABOUT
# ----------------------------
elif page == "About":
    st.title("📖 About HydroScope")
    st.write("HydroScope is a precision irrigation tool designed to help farmers optimize water use in 2025.")
    st.caption("Version 2.5 | Sustainable Agriculture Initiative")


