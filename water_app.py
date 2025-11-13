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
if "display_supply_results" not in st.session_state: st.session_state["display_supply_results"] = True # Flag to control display of results


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

        total_water_liters = total_gross_irrigation_mm * area_sq_meters
    return total_water_liters, total_gross_irrigation_mm

# Helper functions for plots and navigation
def set_active_plot(plot_id):
    st.session_state["active_plot_id"] = plot_id

def delete_plot(plot_id):
    if plot_id in st.session_state["plots_data"]:
        del st.session_state["plots_data"][plot_id]
    if st.session_state["active_plot_id"] == plot_id:
        st.session_state["active_plot_id"] = None
        st.rerun() # Rerun immediately if the active plot is deleted

def deactivate_plot():
    st.session_state["active_plot_id"] = None

def clear_all_plots():
    st.session_state["plots_data"] = {}
    st.session_state["active_plot_id"] = None
    st.rerun() # Rerun immediately to clear the display

# Updated clear results function to control the display flag
def clear_supply_results():
    # Set a flag to indicate results should not be shown
    st.session_state["display_supply_results"] = False


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
], key="main_navigation")

# ----------------------------
# 1. WEATHER & EVAPORATION GUIDE 
# ----------------------------
if page == "🌤️ Weather Guide":
    st.title("🌤️ Local Weather Data & ETo Guide")
    st.markdown("Log your daily weather observations to track local trends. This data helps you get accurate water needs.")

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
        st.success("Weather data logged successfully! The defaults are updated.")

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
        
        if st.button("🚀 Use the Average ETo as Default"):
            st.session_state["eto_value_input"] = avg_eto
            st.info(f"Average ETo ({avg_eto:.1f} mm/day) has been set as the default ETo.")

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
# 2. CROP WATER GUIDE (Input Only)
# ----------------------------
elif page == "🌱 Crop Water Guide":
    st.title("🌱 Crop Water Guide (Input Parameters)")
    st.markdown("Enter your parameters here. The calculation happens when you navigate to the **💧 Supply Planner**.")
    
    # --- Logic for using the active plot or falling back to manual inputs ---
    if st.session_state.get("active_plot_id") and st.session_state["active_plot_id"] in st.session_state["plots_data"]:
        active_plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        # Reduced Font size here via markdown
        st.markdown(f"###### *Using Active Plot: {active_plot['name']} ({active_plot['acres']} acres of {active_plot['crop_type']})*")
        
        selected_crop_name = active_plot['crop_type']
        default_acres = active_plot['acres']
        disabled_inputs = True
    else:
        st.markdown("###### *No active plot selected. Using manual inputs below.*")
        selected_crop_name = None
        default_acres = 1.0
        disabled_inputs = False

    # Initialize session state keys for manual inputs if they don't exist
    if "manual_acres" not in st.session_state: st.session_state["manual_acres"] = 1.0
    if "crop_selection_cw" not in st.session_state: st.session_state["crop_selection_cw"] = list(crop_options_detailed.keys())[0]
    if "avg_daily_eto_cw" not in st.session_state: st.session_state["avg_daily_eto_cw"] = st.session_state["eto_value_input"]
    if "effective_rain_weekly_cw" not in st.session_state: st.session_state["effective_rain_weekly_cw"] = 0.0
    if "efficiency_percent_cw" not in st.session_state: st.session_state["efficiency_percent_cw"] = 80
    if "c_source_cap" not in st.session_state: st.session_state["c_source_cap"] = 1000.0
    if "c_days_apply" not in st.session_state: st.session_state["c_days_apply"] = 7
    if "c_source_type" not in st.session_state: st.session_state["c_source_type"] = "Pump"


    colC1, colC2 = st.columns(2)
    with colC1:
        # We save these inputs to session state with every change in the form
        st.session_state["manual_acres"] = st.number_input("Acres", value=st.session_state["manual_acres"], min_value=0.1, step=0.1, key="cw_acres_key", disabled=disabled_inputs)
        
        current_crop_index = list(crop_options_detailed.keys()).index(selected_crop_name) if selected_crop_name else list(crop_options_detailed.keys()).index(st.session_state["crop_selection_cw"])
        st.session_state["crop_selection_cw"] = st.selectbox("Select Crop Type", options=list(crop_options_detailed.keys()), key="cw_crop_key", disabled=disabled_inputs, index=current_crop_index)
    
    with colC2:
        st.session_state["avg_daily_eto_cw"] = st.number_input("Avg Daily ETo (mm/day)", value=st.session_state["avg_daily_eto_cw"], min_value=0.1, step=0.1, key="cw_eto_key")
        st.session_state["effective_rain_weekly_cw"] = st.number_input("Avg Effective Rain (mm/week)", value=st.session_state["effective_rain_weekly_cw"], min_value=0.0, step=1.0, key="cw_rain_key")
        st.session_state["efficiency_percent_cw"] = st.number_input("Irrigation Efficiency (%)", value=st.session_state["efficiency_percent_cw"], min_value=1, max_value=100, step=1, key="cw_efficiency_key")
        st.session_state["c_source_type"] = st.selectbox("Water Source Type", options=["Pump", "Tank/Other"], key="cw_source_type_key", index=["Pump", "Tank/Other"].index(st.session_state["c_source_type"]))

    st.markdown("---")
    # Add logistics inputs in this form now as requested
    colLog1, colLog2 = st.columns(2)
    with colLog1:
        st.session_state["c_source_cap"] = st.number_input("Source Capacity (Liters/hour)", min_value=1.0, value=st.session_state["c_source_cap"], key="c_source_cap_key")
    with colLog2:
        st.session_state["c_days_apply"] = st.number_input("Number of days for this cycle", min_value=1, value=st.session_state["c_days_apply"], key="c_days_apply_key")
    
    # When inputs change, ensure the results are set to display the next time the user visits the supply planner
    st.session_state["display_supply_results"] = True


# ----------------------------
# 3. FARM SETUP & PLOTS (Revised with Deactivate/Clear All Buttons)
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
        st.button("🧹 Clear All Plots", on_click=clear_all_plots)
        for plot_id, plot_details in st.session_state["plots_data"].items():
            is_active = (st.session_state["active_plot_id"] == plot_id)
            status = "✅ Active" if is_active else "❌ Inactive"
            
            col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns(5)
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
# 4. SUPPLY PLANNER (Calculation & Results Display Only)
# ----------------------------
elif page == "💧 Supply Planner":
    st.title("💧 Water Supply Planner & Calculator")
    st.markdown("View the finalized water needs and logistics plan below using parameters from the previous tabs.")
    
    # Button to force recalculation if user switches between manual/active plot
    st.button("🔄 Recalculate Supply Plan", on_click=lambda: st.session_state.update(display_supply_results=True))


    # --- Fetch all parameters from session state ---
    if st.session_state.get("active_plot_id") and st.session_state["active_plot_id"] in st.session_state["plots_data"]:
        active_plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        acres = active_plot['acres']
        crop_name = active_plot['crop_type']
        st.markdown(f"###### *Calculating using Active Plot: {active_plot['name']}*")
    else:
        acres = st.session_state["manual_acres"]
        crop_name = st.session_state["crop_selection_cw"]
        st.markdown(f"###### *Calculating using Manual Parameters from Crop Water Guide*")
    
    # Parameters that are always manual inputs from CWG page
    avg_daily_eto = st.session_state["avg_daily_eto_cw"]
    effective_rain_weekly = st.session_state["effective_rain_weekly_cw"]
    efficiency_percent = st.session_state["efficiency_percent_cw"]
    source_capacity_lph = st.session_state["c_source_cap"]
    days_to_apply = st.session_state["c_days_apply"]
    water_source_type = st.session_state["c_source_type"]
    
    # We only show results if the flag is True
    if st.session_state.get("display_supply_results"): 
        
        # Perform calculation
        crop_data = crop_options_detailed.get(crop_name)
        if crop_data and crop_data["Duration_Days"]:
            total_water_liters, total_gross_irrigation_mm = calculate_stage_based_water(
                acres, avg_daily_eto, effective_rain_weekly, efficiency_percent, crop_data
            )
            
            # Display results
            st.markdown("---")
            st.subheader("Calculation Results")
            
            colR1, colR2, colR3 = st.columns(3)
            colR1.metric(f"Total Water Needed ({crop_name})", f"{total_water_liters:,.0f} Liters")
            colR2.metric("Gross Irrigation Req", f"{total_gross_irrigation_mm:.1f} mm")
            colR3.metric("Acres Calculated", f"{acres:.1f} Acres")

            if source_capacity_lph > 0 and days_to_apply > 0:
                total_hours_needed = total_water_liters / source_capacity_lph
                hours_per_day = total_hours_needed / days_to_apply
                
                st.markdown("---")
                st.subheader("Supply Logistics Plan")
                
                colL1, colL2, colL3 = st.columns(3)
                colL1.metric("Source Capacity", f"{source_capacity_lph:,.0f} L/hour")
                colL2.metric("Cycle Days", f"{days_to_apply} days")
                colL3.metric("Source Type", water_source_type)

                st.success(f"### Plan: \n Run your **{water_source_type}** for approximately **{hours_per_day:.1f} hours per day** over the next {days_to_apply} days.")
            
        else:
            st.warning("Cannot calculate water needs for the selected crop/plot type. Check inputs in the Crop Water Guide.")

        # Added the "Clear Data" button here
        st.markdown("---")
        st.button("🧹 Clear Results Data", on_click=clear_supply_results)
    
    else:
        st.info("Results currently cleared. Adjust inputs in the **🌱 Crop Water Guide** and click 'Recalculate Supply Plan' above to see results.")

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
