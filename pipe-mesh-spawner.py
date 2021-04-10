import numpy as np
import json
import trimesh
import time
import subprocess

# your source save file
# convert to json with https://ficsit-felix.netlify.app/#/ or
# https://github.com/ficsit-felix/satisfactory-json
json_save_path = "debug.json"
with open(json_save_path, 'rb') as f:
    save_json = json.load(f)
template = """
                {{
                  "properties": [
                    {{
                      "name": "Location",
                      "type": "StructProperty",
                      "index": 0,
                      "value": {{
                        "type": "Vector",
                        "x": {lx},
                        "y": {ly},
                        "z": {lz}
                      }}
                    }},
                    {{
                      "name": "ArriveTangent",
                      "type": "StructProperty",
                      "index": 0,
                      "value": {{
                        "type": "Vector",
                        "x": {atx},
                        "y": {aty},
                        "z": {atz}
                      }}
                    }},
                    {{
                      "name": "LeaveTangent",
                      "type": "StructProperty",
                      "index": 0,
                      "value": {{
                        "type": "Vector",
                        "x": {ltx},
                        "y": {lty},
                        "z": {ltz}
                      }}
                    }}
                  ]
                }}

"""

class Placer:
    template_path = "pipe_template.json"
    id_names = ["circle_top", "circle_bottom"]
    def __init__(self, id_offset, x, y, z):
        with open(self.template_path, "r") as t:
            template_s = t.read()
            ids = {}
            buffer_0_id = None
            for i, id_name in enumerate(self.id_names):
                new_id = id_offset + i
                template_s = template_s.replace("{{"+id_name+"}}", str(new_id))
                if id_name == self.id_names[0]:
                    buffer_0_id = new_id
                    
        self.template_json = json.loads(template_s)
        self.actors = []
        self.components = []
        for actor in self.template_json:
            if actor["type"] == 1:
                actor["transform"]["translation"][0] = x
                actor["transform"]["translation"][1] = y
                actor["transform"]["translation"][2] = z
                self.actors.append(actor)
            else:
                self.components.append(actor)
                
    def write_shape_points(self, points, arrive_tangents, leave_tangents):
        for actor in self.actors:
            actor["entity"]["properties"][0]["value"]["values"].clear()
            for c,at,lt in zip(points, arrive_tangents, leave_tangents):
                s = json.loads(template.format(lx=c[0], ly=c[1], lz=c[2], atx=at[0], aty=at[1], atz=at[2], ltx=lt[0], lty=lt[1], ltz=lt[2]))
                actor["entity"]["properties"][0]["value"]["values"].append(s)
    
    def write(self, save_json):
        save_json["actors"].extend(self.actors)
        save_json["components"].extend(self.components)


def tangents(points):
    diffs = (points[1:] - points[:-1]) / 2
    leave_tangents = np.append(diffs, np.array([0.,0.,0.]))
    arrive_tangents = np.insert(diffs, 0, np.array([0.,0.,0.]))
    return arrive_tangents.reshape((len(points), 3)), leave_tangents.reshape((len(points), 3))
    

def find_item_id_offset(save_json):
    max_id = None
    for actor in save_json["actors"]:
        if actor["className"] == "/Game/FactoryGame/Buildable/Factory/Pipeline/Build_Pipeline.Build_Pipeline_C":
            actor_id = int(actor["pathName"].split("_")[-1])
            if not max_id or actor_id > max_id:
                max_id = actor_id
    return max_id

# 3D model to spawn
model_path = "teapot.stl"
# Where in the game to spawn
translation = np.array([-183178.09375, -71177.40625, 24282.08203125 + 10000])
# How much to scale the model, play with this value until it looks good
scale = 2000.

model = trimesh.load(model_path)
model.rezero()
tx = trimesh.transformations.compose_matrix(scale=np.array([scale]*3))
model.apply_transform(tx)
s_heights = np.arange(min(model.bounds[1][-1], model.bounds[0][-1]), max(model.bounds[1][-1], model.bounds[0][-1]), 50.)
sections = model.section_multiplane(model.bounds[0], np.array([0.,0.,1.]), s_heights)
item_id = find_item_id_offset(save_json) + 1
placers = []
for i, section in enumerate(sections):
    if not section:
        continue
    path3d = section.to_3D()
    for points in path3d.discrete:
        path_loc = path3d.centroid
        arrive_tangents, leave_tangents = tangents(points)
        placer = Placer(item_id, translation[0], translation[1], translation[2])
        item_id += 1
        placers.append(placer)
        placer.write_shape_points(points, arrive_tangents, leave_tangents)

for placer in placers:
    placer.write(save_json)
print("n pipes", len(placers))

# convert back to a save with
# https://ficsit-felix.netlify.app/#/ or
# https://github.com/ficsit-felix/satisfactory-json
"""
json_save_out_path = "debug-curve.json"
with open(json_save_out_path, 'w') as f:
    json.dump(obj=save_json, fp=f)
import subprocess
print(subprocess.run(args=["node", "json2sav.js", "debug-curve.json","debug-curve.sav"], check=False, capture_output=True))
    
"""    
