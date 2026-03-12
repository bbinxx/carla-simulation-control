# d:\DEV\CodeBase\MAIN_PRO\AI_TRAFFIC\CARLA_CONTROL\get_labels.py
import carla
import json

labels = [x for x in dir(carla.CityObjectLabel) if not x.startswith('_')]
with open("labels.json", "w") as f:
    json.dump(labels, f)
