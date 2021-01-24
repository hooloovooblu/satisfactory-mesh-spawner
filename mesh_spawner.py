import numpy as np
import json
from scipy.spatial.transform import Rotation as R
from numpy.linalg import norm
import trimesh
import time
import subprocess


# attach to logger so trimesh messages will be printed to console
#trimesh.util.attach_to_log()

item_counts = {}

def find_item_id_offset(save_json):
    max_id = None
    for actor in save_json["actors"]:
        if actor["className"] == "/Game/FactoryGame/Resource/BP_ItemPickup_Spawnable.BP_ItemPickup_Spawnable_C":
            actor_id = int(actor["pathName"].split("_")[-1])
            if not max_id or actor_id > max_id:
                max_id = actor_id
    return max_id
    

def normal_vector_to_quat(axis_vector):
    try:
        up_vector = np.array([0,0,1])
        right_vector = np.cross(axis_vector, up_vector)
        right_vector = right_vector / norm(right_vector)
        angle = -1.0 * np.arccos(np.dot(axis_vector, up_vector))
        q = R.from_quat(np.array([right_vector[0], right_vector[1], right_vector[2], angle]))
        return q.as_quat()
    except:
        return R.identity().as_quat()

class PointWriter:
    def __init__(self,
                 save_json,
                 material,
                 item_tmpl_path="dropped_item.json"):
        self.save_json = save_json
        self.material = material
        with open(item_tmpl_path, 'rb') as f:
            self.item_tmpl = json.load(f)
            self.item_tmpl["entity"]["properties"][0]["value"]["properties"][0]["value"]["itemName"] = material

    def write_point(self, point3d, item_id, rotationQuat):
        item = json.loads(json.dumps(self.item_tmpl))
        if rotationQuat is not None:
            item["transform"]["rotation"] = [v.item() for v in rotationQuat]
        item["transform"]["translation"] = [v.item() for v in point3d]
        item["pathName"] = "Persistent_Level:PersistentLevel.BP_ItemPickup_Spawnable_C_" + str(item_id)
        save_json["actors"].append(item)
        if self.material not in item_counts:
            item_counts[self.material] = 0
        item_counts[self.material] += 1

class MeshWriter(object):
    def __init__(self, image_paths, image_materials, save_json, points_method, translation = np.array([0.,0.,0.]), scale = 1.0, rotation=np.array([0,0,0])):
        self.point_writers = [PointWriter(save_json, material) for material in image_materials]
        self.meshes = [trimesh.load(image_path) for image_path in image_paths]
        tx = trimesh.transformations.compose_matrix(scale=np.array([scale]*3), translate=translation, angles=rotation)
        for mesh in self.meshes:
            mesh.apply_transform(tx)
            mesh.fix_normals(multibody=True)
        
        self.curr_id = find_item_id_offset(save_json) + 1
        self.points_method = points_method
    
    def write_meshes(self):
        for writer, (points, rotations) in zip(self.point_writers, self.points_method(self.meshes)):
            for point, rotation in zip(points, rotations):
                writer.write_point(point, self.curr_id, rotation)
                self.curr_id += 1
            


# method 1: use the center of all mesh triangles to position points for items
def centroids(meshes):
    for mesh in meshes:
        yield mesh.triangles.mean(1), np.array([normal_vector_to_quat(v) for v in mesh.face_normals])        

# roughly how many items will be spawned
MAX_SAMPLES = 200000
max_per_mesh = 80000
# method 2: sample the surface of the mesh weighted by mesh area
def samples(meshes):
    total_area = sum(mesh.area for mesh in meshes)
    weights = [mesh.area / total_area for mesh in meshes]
    for mesh, weight in zip(meshes, weights):
        requested_samples = min(int(MAX_SAMPLES*weight), max_per_mesh)
        points, faces = trimesh.sample.sample_surface_even(mesh, requested_samples)
        quats = np.array([normal_vector_to_quat(mesh.face_normals[i]) for i in faces])
        yield points, quats


# Pick a point on the map where you want to spawn things in
translation = np.array([-183178.09375, -71177.40625, 24282.08203125 + 10000])
# Experiment with this number for your models until it looks good
scale = 200

# locations of your models, one per material type
# you can find the item name / blueprint path for most items on the wiki
teapot_paths = [
    # https://en.wikipedia.org/wiki/Utah_teapot#/media/File:Utah_teapot_(solid).stl
    'teapot.stl',
]
teapot_item_names = [
    "/Game/FactoryGame/Resource/Parts/IronPlate/Desc_IronPlate.Desc_IronPlate_C"
]

# unrelated, pls ignore
def tame_doggos(save_json):
    for actor in save_json["actors"]:
        if actor["className"] == "/Game/FactoryGame/Character/Creature/Wildlife/SpaceRabbit/Char_SpaceRabbit.Char_SpaceRabbit_C":
            actor["entity"]["properties"].append(json.loads(""" {
        "name": "mFriendActor",
        "type": "ObjectProperty",
        "index": 0,
        "value": {
          "levelName": "Persistent_Level",
          "pathName": "Persistent_Level:PersistentLevel.Char_Player_C_3"
        }
      }"""))

# prepare a save with https://github.com/ficsit-felix/satisfactory-json sav2json.js
# or with https://ficsit-felix.netlify.app/#/ (More -> Export json)
json_save_path = "debug.json"
with open(json_save_path, 'rb') as g:
    print("Loading json")
    save_json = json.load(g)
    #tame_doggos(save_json)
    print("Loading meshes")
    mw = MeshWriter(
        teapot_paths,
        teapot_item_names,
        save_json, samples,
        translation,
        scale,
        # euler xyz degrees
        rotation=np.array([0.,0.,0.]))
    print("Writing meshes")
    mw.write_meshes()

    
json_save_out_path = "debug_img.json"
with open(json_save_out_path, 'w') as f:
    # set the save time to now to bump to the top of the load list
    save_json["saveDateTime"] = str(time.time_ns())
    print("Dumping json")
    json.dump(obj=save_json, fp=f, indent="  ")

# convert back to a save with https://github.com/ficsit-felix/satisfactory-json json2sav.js
# or with https://ficsit-felix.netlify.app/#/open/json
print("Writing save")
print(subprocess.run(args=[
    "node",
    "json2sav.js",
    "debug_img.json",
    "debug_img.sav"],
               check=False, capture_output=True))

for item in item_counts:
    print(item, item_counts[item])
