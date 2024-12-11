import tkinter as tk
from tkinter import filedialog, messagebox


from utilities import (
    get_weather_and_traffic_from_model,
    assign_orders_with_weather_traffic_model,
    load_data_from_excel,
)

# Zones with geographical coordinates and delivery/return times
from zones_data import ZONE_DETAILS


# Run assignment logic
def run_assignment():
    file_path = filedialog.askopenfilename(
        title="Select Excel File", filetypes=[("Excel Files", "*.xlsx")]
    )
    if not file_path:
        messagebox.showerror("Error", "No file selected!")
        return

    # Load data from Excel file
    orders_df, drivers_df, deviations_df = load_data_from_excel(file_path)

    # Fetch traffic predictions using weather and model
    traffic_data = get_weather_and_traffic_from_model(ZONE_DETAILS)

    # Assign orders
    assignments_df, unassigned_df = assign_orders_with_weather_traffic_model(
        orders_df, drivers_df, deviations_df, ZONE_DETAILS, traffic_data
    )

    # Save results to Excel
    assignments_df.to_excel("Assigned_Orders.xlsx", index=False)
    unassigned_df.to_excel("Unassigned_Orders.xlsx", index=False)

    # Display success message
    messagebox.showinfo(
        "Success", "Results saved to Assigned_Orders.xlsx and Unassigned_Orders.xlsx!"
    )

if __name__ == "__main__":
    # Tkinter GUI
    root = tk.Tk()
    root.title("Order Assignment System")

    label = tk.Label(
        root, text="Welcome to the Order Assignment System", font=("Arial", 14)
    )
    label.pack(pady=10)

    assign_button = tk.Button(
        root, text="Select File and Run Assignment", command=run_assignment
    )
    assign_button.pack(pady=20)

    root.mainloop()
