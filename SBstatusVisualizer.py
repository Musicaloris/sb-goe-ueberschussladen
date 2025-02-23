import requests
import ttkbootstrap as ttkb
import tkinter as tk
from tkinter import ttk

refresh_time_ms = 2000
window_width = 500
display_config = {"padding_x": 10,
                  "padding_y": 10,
                  "padding_between_pies_y": 50
                  }
canvas_height = window_width + display_config["padding_between_pies_y"] + 20
pie_styles = {"PV":            {"width": 0, "fill": "yellow", "outline": "yellow"},
              "Battery_Power": {"width": 0, "fill": "green", "outline": "green"},
              "Consumption":   {"width": 0, "fill": "blue", "outline": "blue"},
              "Grid":          {"width": 0, "fill": "red", "outline": "red"},
              }
pie_coordinates = {"source":  [display_config["padding_x"],
                               display_config["padding_y"],
                               window_width - display_config["padding_x"],
                               window_width - display_config["padding_y"]],
                   "drain":   [display_config["padding_x"],
                               display_config["padding_y"] + display_config["padding_between_pies_y"],
                               window_width - display_config["padding_x"],
                               window_width - display_config["padding_y"] + display_config["padding_between_pies_y"]]
                   }
USOC_bar_position = [pie_coordinates["source"][0],
                     pie_coordinates["source"][1] + (pie_coordinates["source"][3] - pie_coordinates["source"][1]) / 2,
                     pie_coordinates["drain"][2],
                     pie_coordinates["drain"][1] + (pie_coordinates["drain"][3] - pie_coordinates["drain"][1]) / 2,]
bar_style = {"outline": "black", "width": 3}
text_position = [(pie_coordinates["source"][2] - pie_coordinates["source"][0]) / 2 + display_config["padding_x"],
                 pie_coordinates["drain"][3] + display_config["padding_y"] + 10]
arc_position: dict[str, dict[str,int]] = {"PV":            {"extent": 0, "start": -180},
                                          "Battery_Power": {"extent": 0, "start": -180},
                                          "Consumption":   {"extent": 0, "start": -180},
                                          "Grid":          {"extent": 0, "start": -180}
                                          }
bar_mapping = {"PV": "Production_W",
               "Battery_Power": "Pac_total_W",
               "Battery_SOC": "USOC",
               "Consumption": "Consumption_W",
               "Grid": "GridFeedIn_W"
               }

####### GUI functions
def set_sb_url():
    url_setting.deiconify()

def close_url_set_dialog():
    api_url.set(f"{protocol.get()}://{sb_base_url.get()}/{sb_api_endpoint.get()}")
    url_setting.withdraw() 

def refresh_diagram():
    status_text.set("Getting fresh data from API...")
    root.update_idletasks()
    state_dict = get_update_data()
    status_text.set(f"Acquired data with timestamp {state_dict["Timestamp"]}, building graphic...")
    root.update_idletasks()
    update_diagram(state_dict)
    status_text.set(f"This is data with timestamp {state_dict["Timestamp"]}")
    root.update_idletasks()
    root.after(refresh_time_ms, refresh_diagram)

def get_update_data() -> dict:
    return requests.get(api_url.get()).json()  # TODO handle error status codes and connection errors and and and...

def update_diagram(state: dict):
    energy_distribution = {"source":  {"PV": state[bar_mapping["PV"]]},
                           "drain": {"Consumption": state[bar_mapping["Consumption"]]}
                           }
    energy_distribution["source" if state[bar_mapping["Battery_Power"]] >= 0 else "drain"] |= {"Battery_Power": abs(state[bar_mapping["Battery_Power"]])}
    energy_distribution["source" if state[bar_mapping["Grid"]]           < 0 else "drain"] |= {"Grid":          abs(state[bar_mapping["Grid"]])}
    for side, value_dict in energy_distribution.items():
        side_direction_factor = 1 if side == "source" else -1
        start_value = 180
        for name, value in value_dict.items():
            arc_position[name]["start"] = start_value
            arc_position[name]["extent"] = value / sum(value_dict.values()) * 180 * side_direction_factor * -1
            energy_diagram.coords(name, *pie_coordinates[side])
            energy_diagram.itemconfigure(name, arc_position[name])
            start_value = arc_position[name]["start"] + arc_position[name]["extent"]
    chargebar_coords = energy_diagram.coords("USOC_charge")
    chargebar_coords[2] = display_config["padding_x"] + (pie_coordinates["source"][2] - pie_coordinates["source"][0]) * state[bar_mapping["Battery_SOC"]] / 100
    energy_diagram.coords("USOC_charge", *chargebar_coords)
    energy_diagram.itemconfigure("text", text="   |   ".join(f"{side}: {value_dict}" for side, value_dict in energy_distribution.items()))

####### GUI config
# root = tk.Tk(title="SonnenBatterie Status Visualizer")
root = ttkb.Window(title="SonnenBatterie Status Visualizer")

status_text = tk.StringVar(value="Starting up...")
protocol = tk.StringVar(value="http")
sb_api_endpoint = tk.StringVar(value="api/v2/status")
sb_base_url = tk.StringVar(value="sb-238729.fritz.box")
protocol_values = ("http", "https")
api_values = ("api/v2/status",)
api_url = tk.StringVar()

### GUI layout main window
ttk.Button(root, text="Refresh", command=refresh_diagram).grid(row=0, column=0, sticky="nw")
ttk.Label(root, textvariable=api_url).grid(row=0, column=1)
ttk.Button(root, text="URL setting", command=set_sb_url).grid(row=0, column=2, sticky="ne")
energy_diagram = tk.Canvas(root, width=window_width, height=canvas_height)
energy_diagram.grid(row=1, columnspan=3)
ttk.Label(root, textvariable=status_text, state="disabled").grid(row=2, columnspan=3)

for name, style in pie_styles.items():
    energy_diagram.create_arc(*pie_coordinates["source"], **style, tags=name)
energy_diagram.create_rectangle(*USOC_bar_position, tags="USOC_charge", outline="cyan", fill="cyan", width=0)
energy_diagram.create_rectangle(*USOC_bar_position, tags="USOC_base", **bar_style)
energy_diagram.create_arc(*pie_coordinates["source"], extent=180, outline="black", width=3)
energy_diagram.create_arc(*pie_coordinates["drain"], extent=-180, outline="black", width=3)
energy_diagram.create_text(*text_position, text="", anchor="center", tags="text", font=("",8))


### GUI layout URL setting dialog
url_setting = tk.Toplevel(root)
url_setting.protocol("WM_DELETE_WINDOW", close_url_set_dialog)
url_setting.title("URL setting")
ttk.Label(url_setting, text="Set Protocol").grid(row=0, column=0)
ttk.Combobox(url_setting, textvariable=protocol, values=protocol_values, width=10).grid(row=1, column=0)
ttk.Label(url_setting, text="://").grid(row=1, column=1)
ttk.Label(url_setting, text="Set Base URL").grid(row=0, column=2)
ttk.Entry(url_setting, textvariable=sb_base_url, width=30).grid(row=1, column=2)
ttk.Label(url_setting, text="/").grid(row=1, column=3)
ttk.Label(url_setting, text="Set API URL").grid(row=0, column=4)
ttk.Combobox(url_setting, textvariable=sb_api_endpoint, values=api_values, width=15).grid(row=1, column=4)
close_url_set_dialog()

refresh_diagram()

root.mainloop()
