"""
This module contains utility functions for the traffic prediction and order assignment application.
"""

import joblib
import numpy as np
import pandas as pd
import requests


from typing import Dict, Any, Tuple

# Load pre-trained Random Forest model and feature names.
# These file have been produced by running another script +++.
# These files should be in the same directory as this script.
rf_model = joblib.load("rf_model_traffic_volume.pkl")
feature_names = joblib.load("feature_names.pkl")


# Fetch weather data and predict traffic volume
def get_weather_and_traffic_from_model(
    zone_details: Dict[str, Dict[str, Any]]
) -> Dict[str, float]:
    """
    Fetches weather data for each zone and predicts the traffic volume using the random forest model.
    Args:
        zone_details (Dict[str, Dict[str, Any]]): A dictionary containing zone details.

    Returns:
        Dict[str, float]: A dictionary with traffic volume predictions for each zone.
    """
    base_url = "https://api.open-meteo.com/v1/forecast"
    traffic_data = {}

    for zone, details in zone_details.items():
        params = {
            "latitude": details["latitude"],
            "longitude": details["longitude"],
            "current_weather": "true",
            "timezone": "Europe/Athens",
        }

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            weather = response.json().get("current_weather", {})
            temperature = weather.get("temperature", 0)
            windspeed = weather.get("windspeed", 0)
            clouds = weather.get("cloudcover", 0)

            # Prepare input for the model
            current_hour = pd.Timestamp.now().hour
            current_day = pd.Timestamp.now().dayofweek
            input_features = np.zeros(len(feature_names))
            input_dict = {
                "temp": temperature,
                "clouds_all": clouds,
                "windspeed": windspeed,
                "hour": current_hour,
                "day": current_day,
            }

            for i, feature in enumerate(feature_names):
                input_features[i] = input_dict.get(feature, 0)

            input_df = pd.DataFrame([input_features], columns=feature_names)
            traffic_volume = rf_model.predict(input_df)[0]
            traffic_data[zone] = traffic_volume
        except Exception as e:
            print(f"Error fetching weather or predicting traffic for {zone}: {e}")
            traffic_data[zone] = 1.0  # Default multiplier if API fails

    return traffic_data


# Assign orders based on traffic predictions
def assign_orders_with_weather_traffic_model(
    orders_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
    deviations_df: pd.DataFrame,
    zone_details: Dict[str, Dict[str, Any]],
    traffic_data: Dict[str, float],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Assign orders based on traffic predictions.

    Args:
        orders_df (pd.DataFrame): DataFrame containing order details.
        drivers_df (pd.DataFrame): DataFrame containing driver availability.
        deviations_df (pd.DataFrame): DataFrame containing deviations.
        zone_details (Dict[str, Dict[str, Any]]): Dictionary containing zone details.
        traffic_data (Dict[str, float]): Dictionary containing traffic volume predictions for each zone.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: A tuple containing two DataFrames:
                                           one for assigned orders and one for unassigned orders.
    """
    assignments = []
    unassigned_orders = []
    max_work_time = 12 * 60  # 12 hours in minutes

    # Merge drivers with deviations
    drivers_with_deviation = (
        pd.merge(drivers_df, deviations_df, on="ΣΥΝ. ΟΜΑΔΑΣ", how="left")
        .fillna(0)
        .infer_objects(copy=False)
    )

    # Initialize a tracker for each driver's total assigned time
    driver_time_tracker = {
        driver["ΣΥΝ. ΟΜΑΔΑΣ"]: 0 for _, driver in drivers_with_deviation.iterrows()
    }

    for zone, details in zone_details.items():
        if zone not in orders_df.columns:
            continue

        zone_orders = orders_df[zone].dropna()
        if zone_orders.empty:
            continue

        for order in zone_orders:
            delivery_time = details["delivery_time"]

            # Calculate the total time considering traffic multiplier
            traffic_multiplier = 1 + (traffic_data.get(zone, 1.0) / 10000)
            total_time = int(delivery_time * traffic_multiplier)

            # Try to find an available driver
            assigned = False
            for _, driver in drivers_with_deviation.iterrows():
                driver_id = driver["ΣΥΝ. ΟΜΑΔΑΣ"]

                # Check if the driver has enough available time
                if driver_time_tracker[driver_id] + total_time <= max_work_time:
                    # Assign the order to this driver
                    assignments.append(
                        {
                            "Zone": zone,
                            "Order": order,
                            "Driver": driver_id,
                            "Delivery Time": total_time,
                            "Traffic Multiplier": traffic_multiplier,
                            "Deviation": driver.get(zone, 0),
                        }
                    )
                    # Update the driver's total assigned time
                    driver_time_tracker[driver_id] += total_time
                    assigned = True
                    break  # Stop searching for a driver once assigned

            if not assigned:
                # No available driver for this order
                unassigned_orders.append(
                    {"Zone": zone, "Order": order, "Reason": "No drivers or time limit"}
                )

    return pd.DataFrame(assignments), pd.DataFrame(unassigned_orders)


def load_data_from_excel(
    file_path: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load data from an Excel file.
    Args:
        file_path (str): The path to the Excel file.
    Returns:
        tuple: A tuple containing three DataFrames: orders_df, drivers_df, and deviations_df.
    """
    xls = pd.ExcelFile(file_path)
    orders_df = pd.read_excel(xls, "ΠΑΡΑΓΓΕΛΙΕΣ ΑΝΑ ΠΕΡΙΟΧΗ", header=1)
    drivers_df = pd.read_excel(xls, "ΔΙΑΘΕΣΙΜΟΤΗΤΑ ΟΔΗΓΩΝ")
    deviations_df = pd.read_excel(xls, "ΑΠΟΚΛΙΣΗ", header=1)
    return orders_df, drivers_df, deviations_df
