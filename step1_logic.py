import maya.cmds as cmds
import maya.OpenMaya as om

def check_uv_overlap(mesh_node, u_coord, v_coord):
    """
    Checks if there are multiple faces at the specified UV coordinate.
    (The accuracy and efficiency of this function can be further improved.)
    """
    selection_list = om.MSelectionList()
    selection_list.add(mesh_node)
    dag_path = om.MDagPath()
    try:
        selection_list.getDagPath(0, dag_path)
    except RuntimeError:
        cmds.warning(f"Could not get DAG path for mesh node '{mesh_node}'.")
        return True # Return True in case of error to stop the process

    mesh_fn = om.MFnMesh(dag_path)
    current_uv_set = mesh_fn.currentUVSetName()
    hit_faces = {}
    num_faces = mesh_fn.numPolygons()

    for i in range(num_faces):
        face_uvs_u = om.MFloatArray()
        face_uvs_v = om.MFloatArray()
        try:
            mesh_fn.getPolygonUVs(i, current_uv_set, face_uvs_u, face_uvs_v)
            for j in range(face_uvs_u.length()):
                if abs(face_uvs_u[j] - u_coord) < 0.0001 and abs(face_uvs_v[j] - v_coord) < 0.0001:
                    uv_tuple = (round(u_coord, 4), round(v_coord, 4)) # Rounding for tolerance
                    if uv_tuple not in hit_faces:
                        hit_faces[uv_tuple] = []
                    if i not in hit_faces[uv_tuple]:
                        hit_faces[uv_tuple].append(i)
        except Exception as e:
            # print(f"Error getting UVs for face {i}: {e}")
            continue
    
    uv_tuple_check = (round(u_coord, 4), round(v_coord, 4))
    if uv_tuple_check in hit_faces and len(hit_faces[uv_tuple_check]) > 1:
        # cmds.warning(f"UV Overlap (simple check): {len(hit_faces[uv_tuple_check])} faces ({hit_faces[uv_tuple_check]}) share UV ({u_coord}, {v_coord}).")
        return True
    return False

def get_world_space_at_uv(mesh_shape_name, u_coord, v_coord):
    """
    Gets the world space coordinate corresponding to the specified UV coordinate.
    Uses uvPin node for more reliable results.
    """
    if not cmds.objExists(mesh_shape_name):
        cmds.warning(f"Mesh shape '{mesh_shape_name}' not found.")
        return None

    mesh_transform_name_list = cmds.listRelatives(mesh_shape_name, parent=True, fullPath=True)
    if not mesh_transform_name_list:
        cmds.warning(f"Could not find transform for mesh shape '{mesh_shape_name}'.")
        return None
    mesh_transform_name = mesh_transform_name_list[0]

    uv_pin_node = None
    try:
        uv_pin_node = cmds.createNode("uvPin")
        
        # worldMesh or outMesh connection
        if cmds.attributeQuery("worldMesh", node=mesh_shape_name, exists=True) and \
           cmds.attributeQuery("worldMesh[0]", node=mesh_shape_name, exists=True):
            cmds.connectAttr(f"{mesh_shape_name}.worldMesh[0]", f"{uv_pin_node}.deformedGeometry")
        elif cmds.attributeQuery("outMesh", node=mesh_shape_name, exists=True):
             cmds.connectAttr(f"{mesh_shape_name}.outMesh", f"{uv_pin_node}.deformedGeometry")
        else:
            cmds.warning(f"Could not find appropriate mesh output attribute on mesh shape '{mesh_shape_name}' (worldMesh[0] or outMesh).")
            if uv_pin_node and cmds.objExists(uv_pin_node): cmds.delete(uv_pin_node)
            return None

        # Connect transform's worldMatrix to the uvPin node (important for correct position)
        # Should use 'inputMatrix' instead of 'originalGeometryMatrix', or adjust the uvPin's own transform.
        # Typically a worldMatrix[0] -> inputMatrix connection is made.
        if cmds.attributeQuery("inputMatrix", node=uv_pin_node, exists=True):
            cmds.connectAttr(f"{mesh_transform_name}.worldMatrix[0]", f"{uv_pin_node}.inputMatrix")
        else:
            # Alternatively, we could set the uvPin node's transform equal to the mesh's transform
            # or parent the uvPin to the mesh and zero out its transforms.
            # However, inputMatrix is the cleanest method. If it's missing, uvPin behavior may differ.
            # For now, we assume inputMatrix exists. If not, this could be problematic.
            # In older Maya versions this attribute might not exist or might be different.
            # In modern Maya versions (e.g., 2018+) inputMatrix should exist.
            cmds.warning(f"Could not find 'inputMatrix' attribute on uvPin node '{uv_pin_node}'. World position may be incorrect.")
            # We can still try to continue, but results may be misleading.

        cmds.setAttr(f"{uv_pin_node}.coordinate[0].coordinateU", u_coord)
        cmds.setAttr(f"{uv_pin_node}.coordinate[0].coordinateV", v_coord)
        
        matrix_values = cmds.getAttr(f"{uv_pin_node}.outputMatrix[0]")
        world_pos = [matrix_values[12], matrix_values[13], matrix_values[14]]
        
        return om.MPoint(world_pos[0], world_pos[1], world_pos[2])
    except Exception as e:
        cmds.warning(f"Error getting world coordinate (uvPin): {e}")
        return None
    finally:
        if uv_pin_node and cmds.objExists(uv_pin_node):
            cmds.delete(uv_pin_node)

def create_locator_at_point(point, name_prefix="textureRigger"): # Changed default name_prefix
    """
    Creates a locator at the specified world space coordinate.
    
    Args:
        point (om.MPoint): World space coordinate where the locator will be created.
        name_prefix (str): Name prefix for the locator.
    """
    # Check the name prefix and use it in locator naming if not empty
    locator_name = f"{name_prefix}_locator#" if name_prefix else "textureRigger_locator#" # Changed fallback prefix
    locator = cmds.spaceLocator(name=locator_name)
    cmds.xform(locator[0], translation=(point.x, point.y, point.z), worldSpace=True)
    # cmds.select(locator[0]) # Let the main UI handle selection
    print(f"Locator '{locator[0]}' created at: ({point.x}, {point.y}, {point.z})")
    return locator[0]

def run_step1_logic(name_prefix="textureRigger"): # Changed default name_prefix
    """
    Runs the main logic of Step 1: Mesh selection, UV checking, and locator creation.
    
    Args:
        name_prefix (str): Name prefix for the locator and other objects.
    
    Returns:
        tuple: (mesh_transform, mesh_shape, locator_name) or (None, None, None)
    """
    selected_objects = cmds.ls(selection=True, long=True, type="transform")

    if not selected_objects:
        cmds.warning("Please select a polygon mesh.")
        return None, None, None # Return 3 values

    mesh_transform = selected_objects[0]
    shapes = cmds.listRelatives(mesh_transform, shapes=True, fullPath=True, type="mesh")

    if not shapes:
        cmds.warning(f"Selected object '{mesh_transform}' is not a polygon mesh or has no mesh shape.")
        return None, None, None # Return 3 values
    
    mesh_shape = shapes[0]

    uv_to_check_u, uv_to_check_v = 0.5, 0.5
    if check_uv_overlap(mesh_shape, uv_to_check_u, uv_to_check_v):
        cmds.warning(f"UV overlapping detected at point ({uv_to_check_u}, {uv_to_check_v}) (or multiple faces found). Please check your UVs.")
        return None, None, None # Return 3 values

    world_point = get_world_space_at_uv(mesh_shape, uv_to_check_u, uv_to_check_v)
    if world_point:
        locator_name = create_locator_at_point(world_point, name_prefix)
        if locator_name: # create_locator_at_point can also return None (though unlikely)
            cmds.select(locator_name, replace=True)
            return mesh_transform, mesh_shape, locator_name
        else:
            cmds.warning(f"Could not create locator.")
            return None, None, None # Return 3 values
    else:
        cmds.warning(f"Could not get world coordinate at UV point ({uv_to_check_u}, {uv_to_check_v}).")
        return None, None, None # Return 3 values

