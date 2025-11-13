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
if "finalized_supply_plan_results" not in st.session_state: st.session_state["finalized_supply_plan_results"] = None # Stores temporary data for Supply Planner results


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

def navigate_to_supply_planner():
    st.session_state["main_navigation"] = "💧 Supply Planner"

def clear_supply_results():
    st.session_state["finalized_supply_plan_results"] = None
    st.rerun() # Clear the results display

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
        # ... [Metrics display code] ...

        if st.button("🚀 Use the Average ETo as Default"):
            avg_eto = display_weather_data["ETo (mm/day)"].mean()
            st.session_state["eto_value_input"] = avg_eto
            st.info(f"Average ETo ({avg_eto:.1f} mm/day) has been set as the default ETo.")

        # ... [Plotting code and clear log button] ...

# ----------------------------
# 2. CROP WATER GUIDE (Data Entry Only, Calculation Button Added)
# ----------------------------
elif page == "🌱 Crop Water Guide":
    st.title("🌱 Crop Water Guide (Data Entry)")
    st.markdown("Select or enter the necessary crop parameters here. Click the button below to send inputs to the **💧 Supply Planner** for calculation.")
    
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

    with st.form(key='water_calc_form'):
        colC1, colC2 = st.columns(2)
        with colC1:
            # Manual inputs enabled/disabled based on active plot status
            acres = st.number_input("Acres", value=default_acres, min_value=0.1, step=0.1, disabled=disabled_inputs)
            crop_selection = st.selectbox("Select Crop Type", options=list(crop_options_detailed.keys()), disabled=disabled_inputs, index=list(crop_options_detailed.keys()).index(selected_crop_name) if selected_crop_name else 0)
        
        with colC2:
            avg_daily_eto = st.number_input("Avg Daily ETo (mm/day)", value=st.session_state["eto_value_input"], min_value=0.1, step=0.1)
            effective_rain_weekly = st.number_input("Avg Effective Rain (mm/week)", value=0.0, min_value=0.0, step=1.0)
            efficiency_percent = st.number_input("Irrigation Efficiency (%)", value=80, min_value=1, max_value=100, step=1)
            water_source_type = st.selectbox("Water Source Type", options=["Pump", "Tank/Other"])

        st.markdown("---")
        # Add logistics inputs in this form now as requested
        colLog1, colLog2 = st.columns(2)
        with colLog1:
            source_capacity_lph = st.number_input("Source Capacity (Liters/hour)", min_value=1.0, value=1000.0, key="c_source_cap")
        with colLog2:
            days_to_apply = st.number_input("Number of days for this cycle", min_value=1, value=7, key="c_days_apply")


        calculate_btn = st.form_submit_button("👉 Calculate & Plan Supply Logistics")

    if calculate_btn:
        crop_data = crop_options_detailed.get(crop_selection)
        if crop_data and crop_data["Duration_Days"]:
            # Perform calculation here to finalize results before sending to the planner
            total_water_liters, total_gross_irrigation_mm = calculate_stage_based_water(acres, avg_daily_eto, effective_rain_weekly, efficiency_percent, crop_data)
            
            # --- Save results to session state for the Supply Planner ---
            st.session_state["finalized_supply_plan_results"] = {
                "total_water_liters": total_water_liters,
                "total_gross_irrigation_mm": total_gross_irrigation_mm,
                "acres_used": acres,
                "crop_name": crop_selection,
                "source_capacity_lph": source_capacity_lph,
                "days_to_apply": days_to_apply,
                "water_source_type": water_source_type
            }

            st.success(f"Calculation finalized! Navigating to Supply Planner...")
            # Use callback function logic to navigate immediately
            navigate_to_supply_planner()
            st.rerun()
            
        else:
            st.warning("Please select a valid crop type or ensure custom crop data is handled.")

# ----------------------------
# 3. FARM SETUP & PLOTS (Revised with Deactivate/Clear All Buttons)
# ----------------------------
elif page == "🏡 Farm Setup & Plots":
    st.title("🏡 Farm Setup & Plots Management")
    # ... [Rest of the form/plot management code is the same] ...
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
# 4. SUPPLY PLANNER (Results Display Only)
# ----------------------------
elif page == "💧 Supply Planner":
    st.title("💧 Water Supply Planner Results")
    st.markdown("View the finalized water needs and logistics plan below.")
    
    # Check if data was transferred from the Crop Water Guide
    if st.session_state.get("finalized_supply_plan_results"):
        data = st.session_state["finalized_supply_plan_results"]
        
        # Add the clear data button here as requested
        st.button("🧹 Clear Results Data", on_click=clear_supply_results)
        
        st.markdown("---")
        st.subheader(f"Plan for: {data['crop_name']} ({data['acres_used']} acres)")
        
        total_water_needed_liters = data["total_water_liters"]
        source_capacity_lph = data["source_capacity_lph"]
        days_to_apply = data["days_to_apply"]
        water_source_type = data["water_source_type"]


        # Calculations for display
        total_hours_needed = total_water_needed_liters / source_capacity_lph
        hours_per_day = total_hours_needed / days_to_apply
        
        colR1, colR2, colR3 = st.columns(3)
        colR1.metric(f"Total Water Needed", f"{total_water_needed_liters:,.0f} Liters")
        colR2.metric("Gross Irrigation Req", f"{data['total_gross_irrigation_mm']:.1f} mm")
        colR3.metric("Source Type Used", water_source_type)
        
        st.markdown("---")
        
        st.success(f"### Logistics Plan: \n You need to run your **{water_source_type}** for approximately **{hours_per_day:.1f} hours per day** over {days_to_apply} days to meet the crop's total water requirement.")
            
    else:
        st.info("No saved supply data results found. Please enter parameters and calculate water needs in the **🌱 Crop Water Guide** first.")

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
