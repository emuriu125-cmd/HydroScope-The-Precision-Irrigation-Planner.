import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import uuid # Import the UUID library

st.set_page_config(page_title="HydroScope", layout="wide")

# ----------------------------
# SESSION STATE (Revised for Plots)
# ----------------------------
if "has_predicted" not in st.session_state: st.session_state["has_predicted"] = False
if "prediction_log" not in st.session_state: st.session_state["prediction_log"] = []
if "prediction_log_water" not in st.session_state: st.session_state["prediction_log_water"] = []
if "forecast_log" not in st.session_state: st.session_state["forecast_log"] = []
if "crop_log" not in st.session_state: st.session_state["crop_log"] = []
if "weather_log_data" not in st.session_state: st.session_state["weather_log_data"] = pd.DataFrame(columns=["Date", "Temperature (°C)", "Rainfall (mm)", "ETo (mm/day)"])
if "eto_value_input" not in st.session_state: st.session_state["eto_value_input"] = 5.0
if "plots_data" not in st.session_state: st.session_state["plots_data"] = {} # Stores all plots
if "active_plot_id" not in st.session_state: st.session_state["active_plot_id"] = None # Stores the ID of the currently active plot


# ----------------------------
# CROP DATA AND FUNCTIONS
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

    kc_mid = crop_data["Kc_Values"]["Mid"]
    kc_end = crop_data["Kc_Values"]["End"]
    kc_init = crop_data["Kc_Values"]["Initial"]
    stages = ["Initial", "Development", "Mid", "Late"]
    
    for stage in stages:
        duration_days = crop_data["Duration_Days"][stage]
        if stage == "Initial": kc_stage_avg = kc_init
        elif stage == "Mid": kc_stage_avg = kc_mid
        elif stage == "Late": kc_stage_avg = (kc_mid + kc_end) / 2
        elif stage == "Development": kc_stage_avg = (kc_init + kc_mid) / 2

        etc_daily_mm = kc_stage_avg * avg_daily_eto
        net_irrigation_stage_mm = max(0, (etc_daily_mm - avg_effective_rain_daily) * duration_days)
        
        if efficiency_decimal > 0:
            gross_irrigation_stage_mm = net_irrigation_stage_mm / efficiency_decimal
        else:
            gross_irrigation_stage_mm = net_irrigation_stage_mm

        total_gross_irrigation_mm += gross_irrigation_stage_mm

    total_water_liters = total_gross_irrigation_mm * area_sq_meters
    return total_water_liters, total_gross_irrigation_mm

# ----------------------------
# SIDEBAR (Revised Order)
# ----------------------------
st.sidebar.title("⚙️ HydroScope Controls")
page = st.sidebar.radio("Navigate", [
    "🌤️ Weather Guide", 
    "🌱 Crop Water Guide", 
    "🏡 Farm Setup & Plots", 
    "💧 Supply Planner", 
    "subscription", 
    "About"
])

# ----------------------------
# 1. WEATHER & EVAPORATION GUIDE 
# ----------------------------
if page == "🌤️ Weather Guide":
    st.title("🌤️ Local Weather Data & ETo Guide")
    st.markdown("Log your daily weather observations to track local trends. This data helps you get accurate water needs in the **Crop Water Guide**.")

    with st.form(key='weather_form'):
        colD1, colD2, colD3, colD4 = st.columns(4)
        with colD1:
            date_entry = st.date_input("Date")
        with colD2:
            temp_entry = st.number_input("Avg Temp (°C)", value=25.0)
        with colD3:
            rain_entry = st.number_input("Rainfall (mm)", value=0.0)
        with colD4:
            eto_entry = st.number_input("Avg ETo (mm/day)", value=5.0)
            
        log_weather_btn = st.form_submit_button("➕ Log New Weather Data")

    if log_weather_btn:
        new_entry = {
            "Date": date_entry,
            "Temperature (°C)": temp_entry,
            "Rainfall (mm)": rain_entry,
            "ETo (mm/day)": eto_entry
        }
        st.session_state["weather_log_data"] = pd.concat([st.session_state["weather_log_data"], pd.DataFrame([new_entry])], ignore_index=True)
        st.session_state["eto_value_input"] = eto_entry
        st.success("Weather data logged successfully! The Crop Guide defaults are updated.")

    if not st.session_state["weather_log_data"].empty:
        display_weather_data = st.session_state["weather_log_data"].copy()
        display_weather_data["Date"] = pd.to_datetime(display_weather_data["Date"])
        
        st.subheader("📊 Historical Weather Trends & Relationships")

        avg_temp = display_weather_data["Temperature (°C)"].mean()
        avg_rain = display_weather_data["Rainfall (mm)"].sum() 
        avg_eto = display_weather_data["ETo (mm/day)"].mean()

        colM1, colM2, colM3 = st.columns(3)
        colM1.metric("Avg Temp Recorded", f"{avg_temp:.1f} °C")
        colM2.metric("Total Rainfall Recorded", f"{avg_rain:.1f} mm")
        colM3.metric("Avg ETo Recorded", f"{avg_eto:.1f} mm/day")
        
        if st.button("🚀 Use the Average ETo in the Crop Water Guide Calculator"):
            st.session_state["eto_value_input"] = avg_eto
            st.info(f"Average ETo ({avg_eto:.1f} mm/day) has been set as the default in the Crop Water Guide tab. Please navigate to that tab now.")

        st.subheader("📋 Raw Data Log (Cleaner Table)")
        st.table(display_weather_data.set_index("Date").sort_index()) 
        
        if len(display_weather_data) >= 2:
            fig_temp = px.scatter(display_weather_data, x="Temperature (°C)", y="ETo (mm/day)", trendline="ols", title="ETo vs. Temperature Relationship")
            st.plotly_chart(fig_temp, use_container_width=True)

            fig_rain = px.scatter(display_weather_data, x="Rainfall (mm)", y="ETo (mm/day)", trendline="ols", title="ETo vs. Rainfall Relationship")
            st.plotly_chart(fig_rain, use_container_width=True)
        else:
            st.info("Log more data points (at least 2) to see linear regression trendlines here.")
        
        if st.button("🧹 Clear Weather Log"):
            st.session_state["weather_log_data"] = pd.DataFrame(columns=["Date", "Temperature (°C)", "Rainfall (mm)", "ETo (mm/day)"])

    with st.expander("❓ **Explain the Jargon**"):
        st.markdown("""
        *   **ETo (Evapotranspiration):** The rate at which water evaporates from the soil and plants, measured in millimeters per day (mm/day).
        *   **Rainfall:** The amount of rain collected, measured in millimeters (mm).
        """)

# ----------------------------
# 2. CROP WATER GUIDE (The core app - UPDATED to use Active Plot)
# ----------------------------
elif page == "🌱 Crop Water Guide":
    st.title("🌱 Crop Water Calculator (Realistic FAO CROPWAT)")
    st.markdown("Use localized data based on FAO guidelines for accurate results.")
    
    # --- Logic for using the active plot or falling back to manual inputs ---
    if st.session_state.get("active_plot_id") and st.session_state["active_plot_id"] in st.session_state["plots_data"]:
        active_plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        st.info(f"Using Active Plot: **{active_plot['name']}** ({active_plot['acres']} acres of {active_plot['crop_type']})")
        
        selected_crop = active_plot['crop_type']
        acres = active_plot['acres']
        crop_name = selected_crop

        total_days = sum(crop_options_detailed[selected_crop]["Duration_Days"].values())
        growth_weeks = round(total_days / 7, 1)
        st.markdown(f"**Growth Period (weeks):** {growth_weeks} (Fixed)")
        
        # We need to manually add the rest of the inputs required for calculation that were in the original code
        col_climate, col_efficiency = st.columns(2)
        with col_climate:
            eto_daily_avg = st.number_input("Average daily Evapotranspiration (ETo mm/day)", value=st.session_state["eto_value_input"])
        with col_efficiency:
            efficiency = st.slider("Irrigation Efficiency (%)", 10, 100, 75)
        
        effective_rain_weekly = st.number_input("Avg Effective Rainfall (mm/week)", value=10.0)


    else:
        # Fallback to manual selection if no active plot is set
        st.warning("No active plot selected. Please set up and select a plot in the 'Farm Setup & Plots' tab, or use manual inputs below.")
        col_crop, col_growth, col_size = st.columns(3)
        selected_crop = col_crop.selectbox("Choose Crop", list(crop_options_detailed.keys()) + ["Other / Custom Crop"])

        if selected_crop == "Other / Custom Crop":
            st.warning("Stage-based calculation is only available for predefined crops for maximum accuracy.")
            crop_name = st.text_input("Enter crop name", "Custom Crop")
            avg_kc = st.number_input("Set average Kc", 0.1, 3.0, 1.0)
            growth_weeks = col_growth.number_input("Growth period (weeks)", 1, 52, 12)
        else:
            crop_name = selected_crop
            total_days = sum(crop_options_detailed[selected_crop]["Duration_Days"].values())
            growth_weeks = round(total_days / 7, 1)
            col_growth.markdown(f"**Growth Period (weeks):** {growth_weeks} (Fixed)")
        
        acres = col_size.number_input("Farm size (acres)", 0.1, 1000.0, 5.0)

        col_climate, col_efficiency = st.columns(2)
        with col_climate:
            eto_daily_avg = st.number_input("Average daily Evapotranspiration (ETo mm/day)", value=st.session_state["eto_value_input"])
        with col_efficiency:
            efficiency = st.slider("Irrigation Efficiency (%)", 10, 100, 75)
        
        effective_rain_weekly = st.number_input("Avg Effective Rainfall (mm/week)", value=10.0)


    # The calculation button and results section (which was moved to Supply Planner)
    # The 'Predict Water Needs' button was previously here in your code.

# ----------------------------
# 3. FARM SETUP & PLOTS (New Tab Logic)
# ----------------------------
elif page == "🏡 Farm Setup & Plots":
    st.title("🏡 My Farm & Plot Management")
    st.markdown("Define your land plots and select which one you are actively managing for water calculation.")

    # --- Initialize session state variables if missing ---
    if "plots_data" not in st.session_state:
        st.session_state["plots_data"] = {}
    if "active_plot_id" not in st.session_state:
        st.session_state["active_plot_id"] = None

    # --- Add New Plot Form ---
    with st.form("new_plot_form"):
        st.subheader("➕ Add New Plot")
        colF1, colF2, colF3 = st.columns(3)
        with colF1:
            plot_name = st.text_input("Plot Name (e.g., 'Main Field 2024')")
        with colF2:
            plot_crop = st.selectbox("Crop Type", list(crop_options_detailed.keys()))  # Only predefined crops for accuracy
        with colF3:
            plot_acres = st.number_input("Acres", min_value=0.1, value=1.0)
        
        add_plot_button = st.form_submit_button("Save Plot")
        
        if add_plot_button and plot_name and plot_crop:
            plot_id = str(uuid.uuid4())  # Generate a unique ID
            st.session_state["plots_data"][plot_id] = {
                "id": plot_id,
                "name": plot_name,
                "crop_type": plot_crop,
                "acres": plot_acres
            }
            st.success(f"Plot '{plot_name}' added successfully!")

    st.markdown("---")

    # --- Display Existing Plots ---
    st.subheader("📋 Existing Plots")

    if not st.session_state["plots_data"]:
        st.info("You have no plots saved yet. Use the form above to add one.")
    else:
        plots_list = list(st.session_state["plots_data"].values())
        
        for plot in plots_list:
            colP1, colP2, colP3, colP4 = st.columns(4)
            colP1.write(f"**{plot['name']}**")
            colP2.write(f"{plot['acres']} acres")
            colP3.write(f"{plot['crop_type']}")

            is_active = st.session_state.get("active_plot_id") == plot['id']
            if colP4.button("✅ Active" if is_active else "Set Active", key=f"activate_{plot['id']}"):
                st.session_state["active_plot_id"] = plot['id']
                # Compatible rerun for all Streamlit versions
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()

    st.markdown("---")
    st.subheader("Current Active Plot Status")
    if st.session_state.get("active_plot_id"):
        active_plot_info = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        st.success(f"Active Plot is set to: **{active_plot_info['name']}** ({active_plot_info['acres']} acres of {active_plot_info['crop_type']})")
    else:
        st.warning("No active plot selected. Please select one to use the full **Crop Water Guide** features.")


# ----------------------------
# 4. SUPPLY PLANNER (Moved functionality here)
# ----------------------------

elif page == "💧 Supply Planner":
    st.title("💧 Seasonal Water Supply Planner")
    st.markdown("Calculate total estimated water needs for the entire crop season based on the active plot.")

    # Check if an active plot is selected
    if not st.session_state.get("active_plot_id"):
        st.warning("Please select an active plot in the 'Farm Setup & Plots' tab first.")
    else:
        active_plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        crop_data = crop_options_detailed.get(active_plot['crop_type'])

        if not crop_data:
            st.error(f"Cannot calculate supply plan for {active_plot['crop_type']}. Only predefined crops are supported for seasonal planning.")
        else:
            st.info(f"Planning for Active Plot: **{active_plot['name']}** ({active_plot['acres']} acres of {active_plot['crop_type']})")

            # Inputs required for the calculation that were in your original code
            colSP1, colSP2 = st.columns(2)
            with colSP1:
                sp_eto_daily_avg = st.number_input("Average daily ETo (mm/day) for Season", value=st.session_state["eto_value_input"])
            with colSP2:
                sp_efficiency = st.slider("Irrigation Efficiency (%)", 10, 100, 75)
            
            sp_effective_rain_weekly = st.number_input("Avg Effective Rainfall (mm/week) for Season", value=10.0)

            if st.button("Calculate Seasonal Water Need"):
                total_water_liters, total_gross_irrigation_mm = calculate_stage_based_water(
                    active_plot['acres'], 
                    sp_eto_daily_avg, 
                    sp_effective_rain_weekly, 
                    sp_efficiency, 
                    crop_data
                )
                
                total_days = sum(crop_data["Duration_Days"].values())

                st.subheader("Results Overview")
                colR1, colR2, colR3 = st.columns(3)
                colR1.metric("Total Water Needed (Liters)", f"{total_water_liters:,.0f} L")
                colR2.metric("Avg Daily Need (Liters/day)", f"{total_water_liters / total_days:,.0f} L/day")
                colR3.metric("Gross Irrigation (mm/season)", f"{total_gross_irrigation_mm:,.1f} mm")
                
                st.success(f"Estimated water needed for {crop_name} over the entire season: {total_water_liters:,.0f} Liters.")

# ----------------------------
# 5. REMAINING TABS
# ----------------------------

elif page == "Payment":
    st.title("💰 Subscription payment")
    st.info("Coming Soon")

elif page == "About":
    st.title("ℹ️ About HydroScope")
    st.markdown("HydroScope is dedicated to providing precision water management tools for Kenyan farmers.")
