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
if "saved_supply_plan_data" not in st.session_state: st.session_state["saved_supply_plan_data"] = None # Stores temporary data for Supply Planner

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

# Helper functions for plots
def set_active_plot(plot_id):
    st.session_state["active_plot_id"] = plot_id

def delete_plot(plot_id):
    if plot_id in st.session_state["plots_data"]:
        del st.session_state["plots_data"][plot_id]
    if st.session_state["active_plot_id"] == plot_id:
        st.session_state["active_plot_id"] = None

def deactivate_plot():
    st.session_state["active_plot_id"] = None

# ----------------------------
# SIDEBAR (Revised Order)
# ----------------------------
st.sidebar.title("⚙️ HydroScope Controls")
# Use a key to manage the radio state persistently, even if the user is nudged by a button click (though buttons won't change the sidebar radio directly)
page = st.sidebar.radio("Navigate", [
    "🌤️ Weather Guide", 
    "🌱 Crop Water Guide", 
    "🏡 Farm Setup & Plots", 
    "💧 Supply Planner", 
    "subscription", 
    "About"
], key="main_navigation")

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
# 2. CROP WATER GUIDE 
# ----------------------------
elif page == "🌱 Crop Water Guide":
    st.title("🌱 Crop Water Calculator (Realistic FAO CROPWAT)")
    st.markdown("Use localized data based on FAO guidelines for accurate results.")
    
    # --- Logic for using the active plot or falling back to manual inputs ---
    if st.session_state.get("active_plot_id") and st.session_state["active_plot_id"] in st.session_state["plots_data"]:
        active_plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        st.info(f"Using Active Plot: **{active_plot['name']}** ({active_plot['acres']} acres of {active_plot['crop_type']})")
        
        selected_crop_name = active_plot['crop_type']
        default_acres = active_plot['acres']
        # If crop type is 'Other / Custom Crop', disable the calculate button until custom data is entered (logic needed)
    else:
        st.info("No active plot selected. Using manual inputs below.")
        selected_crop_name = None
        default_acres = 1.0

    with st.form(key='water_calc_form'):
        colC1, colC2 = st.columns(2)
        with colC1:
            if st.session_state.get("active_plot_id"):
                # Display active plot details, don't allow editing here if active plot is used
                acres = st.number_input("Acres", value=default_acres, disabled=True)
                crop_selection = st.selectbox("Select Crop Type", options=[selected_crop_name], disabled=True)
            else:
                # Manual inputs enabled
                acres = st.number_input("Acres", value=default_acres, min_value=0.1, step=0.1)
                crop_selection = st.selectbox("Select Crop Type", options=list(crop_options_detailed.keys()))
        
        with colC2:
            avg_daily_eto = st.number_input("Avg Daily ETo (mm/day)", value=st.session_state["eto_value_input"], min_value=0.1, step=0.1)
            effective_rain_weekly = st.number_input("Avg Effective Rain (mm/week)", value=0.0, min_value=0.0, step=1.0)
            efficiency_percent = st.number_input("Irrigation Efficiency (%)", value=80, min_value=1, max_value=100, step=1)
        
        calculate_btn = st.form_submit_button("💧 Calculate Water Needs")

    if calculate_btn:
        crop_data = crop_options_detailed.get(crop_selection)
        if crop_data and crop_data["Duration_Days"]:
            total_water_liters, total_gross_irrigation_mm = calculate_stage_based_water(acres, avg_daily_eto, effective_rain_weekly, efficiency_percent, crop_data)
            
            st.subheader(f"Total Water Required for {crop_selection} over full cycle:")
            st.success(f"{total_water_liters:,.0f} Liters ({total_water_liters / 1000:.1f} m³)")
            st.markdown(f"*(Gross Irrigation requirement: {total_gross_irrigation_mm:.1f} mm)*")

            # --- Save results to session state for the Supply Planner ---
            st.session_state["saved_supply_plan_data"] = {
                "total_water_liters": total_water_liters,
                "total_gross_irrigation_mm": total_gross_irrigation_mm,
                "acres_used": acres,
                "crop_name": crop_selection,
                "eto_value": avg_daily_eto,
                "efficiency": efficiency_percent
            }

            st.markdown("---")
            if st.button("Use these results in the Supply Planner"):
                # This doesn't change the sidebar radio visually but saves the data for the next page view
                st.session_state["main_navigation"] = "💧 Supply Planner"
                st.rerun() # Rerun the script to jump to the supply planner page using the updated session state
            
        else:
            st.warning("Please select a valid crop type or ensure custom crop data is handled.")

# ----------------------------
# 3. FARM SETUP & PLOTS (Revised with Deactivate Button)
# ----------------------------
elif page == "🏡 Farm Setup & Plots":
    st.title("🏡 Farm Setup & Plots Management")

    with st.form(key='new_plot_form'):
        st.subheader("Add a New Plot")
        colP1, colP2, colP3 = st.columns(3)
        with colP1:
            plot_name = st.text_input("Plot Name (e.g., 'Field 1')", value=f"Plot {len(st.session_state['plots_data']) + 1}")
        with colP2:
            plot_acres = st.number_input("Acres", min_value=0.1, value=1.0)
        with colP3:
            plot_crop = st.selectbox("Crop Type", options=list(crop_options_detailed.keys()))
            
        add_plot_btn = st.form_submit_button("➕ Save New Plot")

    if add_plot_btn:
        new_plot_id = str(uuid.uuid4())
        st.session_state["plots_data"][new_plot_id] = {
            "id": new_plot_id,
            "name": plot_name,
            "acres": plot_acres,
            "crop_type": plot_crop
        }
        st.success(f"Plot '{plot_name}' saved!")

    st.subheader("Your Plots")
    if not st.session_state["plots_data"]:
        st.info("You have no plots saved yet. Use the form above to add one.")
    else:
        # Display existing plots with activate/delete buttons
        for plot_id, plot_details in st.session_state["plots_data"].items():
            is_active = (st.session_state["active_plot_id"] == plot_id)
            status = "✅ Active" if is_active else "❌ Inactive"
            
            col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns([2, 1, 1, 1, 1])
            col_d1.metric("Name", plot_details["name"])
            col_d2.metric("Acres", plot_details["acres"])
            col_d3.metric("Crop", plot_details["crop_type"])
            col_d4.metric("Status", status)
            
            with col_d5:
                # Add activate/deactivate functionality
                if is_active:
                    st.button("Deactivate", key=f"deact_{plot_id}", on_click=deactivate_plot)
                else:
                    st.button("Activate", key=f"act_{plot_id}", on_click=set_active_plot, args=(plot_id,))
                
                st.button("Delete", key=f"del_{plot_id}", on_click=delete_plot, args=(plot_id,))
            st.markdown("---")

# ----------------------------
# 4. SUPPLY PLANNER (New page logic to use saved data)
# ----------------------------
elif page == "💧 Supply Planner":
    st.title("💧 Water Supply Planner")
    st.markdown("Plan your irrigation logistics based on calculated water needs.")
    
    # Check if data was transferred from the Crop Water Guide
    if st.session_state.get("saved_supply_plan_data"):
        data = st.session_state["saved_supply_plan_data"]
        st.subheader(f"Using Data from Crop Guide: {data['crop_name']} ({data['acres_used']} acres)")
        
        # Use the saved values as default inputs for the supply planner logic
        total_water_needed_liters = data["total_water_liters"]
        st.metric("Total Water Requirement Loaded", f"{total_water_needed_liters:,.0f} Liters")
        
        st.markdown("---")
        
        # Example supply planning logic
        st.subheader("Plan your supply logistics")
        
        colS1, colS2 = st.columns(2)
        with colS1:
            source_capacity_lph = st.number_input("Water source/pump capacity (Liters/hour)", min_value=1.0, value=1000.0)
        with colS2:
            # Assume a number of days to apply the full amount is needed (e.g. 7 days for a weekly cycle planning)
            days_to_apply = st.number_input("Number of days for this cycle", min_value=1, value=7)
        
        if source_capacity_lph > 0 and days_to_apply > 0:
            total_hours_needed = total_water_needed_liters / source_capacity_lph
            hours_per_day = total_hours_needed / days_to_apply
            
            st.success(f"You need to run your pump for approximately **{hours_per_day:.1f} hours per day** over {days_to_apply} days to meet the crop's total water requirement.")
        
    else:
        st.info("No saved crop water data found. Please calculate water needs in the **🌱 Crop Water Guide** first.")
        # Provide manual inputs if no data is present
        st.number_input("Enter manual total water needed (Liters):", value=0.0)

# ----------------------------
# 5. SUBSCRIPTION PAGE (Placeholder)
# ----------------------------
elif page == "subscription":
    st.title("Upgrade Your Plan")
    st.markdown("This is where subscription details would go.")

# ----------------------------
# 6. ABOUT PAGE (Placeholder)
# ----------------------------
elif page == "About":
    st.title("About HydroScope")
    st.markdown("HydroScope helps farmers manage water use efficiently using FAO guidelines.")
