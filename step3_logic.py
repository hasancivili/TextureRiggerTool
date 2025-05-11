import maya.cmds as cmds
import os

def select_image_file():
    """
    Displays a file dialog to select an image file for texturing.
    
    Returns:
        str: Selected file path or None if cancelled
    """
    image_file = cmds.fileDialog2(
        fileMode=1,  # Single existing file
        caption="Select Texture Image",
        fileFilter="Image Files (*.jpg *.jpeg *.png *.tif *.tiff *.exr);;All Files (*.*)",
        dialogStyle=2  # Maya style dialog
    )
    
    if image_file and len(image_file) > 0:
        return image_file[0]
    return None

def select_alpha_image_file():
    """
    Displays a file dialog to select an alpha image file for texturing.
    
    Returns:
        str: Selected file path or None if cancelled
    """
    image_file = cmds.fileDialog2(
        fileMode=1,  # Single existing file
        caption="Select Alpha Texture Image",
        fileFilter="Image Files (*.jpg *.jpeg *.png *.tif *.tiff *.exr);;All Files (*.*)",
        dialogStyle=2  # Maya style dialog
    )
    
    if image_file and len(image_file) > 0:
        return image_file[0]
    return None

def find_next_available_layer(layered_texture_node):
    """
    Finds the next available input layer on a layeredTexture node.
    
    Args:
        layered_texture_node (str): The layeredTexture node name
        
    Returns:
        int: The next available input index (0, 1, 2, etc.)
    """
    index = 0
    while True:
        # Check if this input layer is already connected
        connections = cmds.listConnections(f"{layered_texture_node}.inputs[{index}].color", source=True, destination=False)
        if not connections:
            return index
        index += 1

def get_max_layer_index(layered_texture_node):
    """
    Finds the highest used layer index in a layeredTexture node.
    
    Args:
        layered_texture_node (str): The layeredTexture node name
        
    Returns:
        int: The highest used layer index, or -1 if no layers are used
    """
    index = 0
    max_found = -1
    
    # Check connections to find the highest used index
    while True:
        connections = cmds.listConnections(f"{layered_texture_node}.inputs[{index}].color", source=True, destination=False)
        if connections:
            max_found = index
        
        # We'll check a reasonable number of indices, but not infinitely
        if index > 100:  # Arbitrary limit to avoid infinite loop
            break
        index += 1
    
    return max_found

def shift_layers_down(layered_texture_node, max_index):
    """
    Shifts all layers down by one (index 0 to 1, 1 to 2, etc.) to make room for a new layer at index 0.
    Shifts both color and alpha connections.
    
    Args:
        layered_texture_node (str): The layeredTexture node name
        max_index (int): The highest currently used layer index
    """
    # We need to work from bottom to top to avoid overwriting connections
    for i in range(max_index, -1, -1):
        # Handle color connections
        color_connections = cmds.listConnections(f"{layered_texture_node}.inputs[{i}].color", source=True, destination=False, plugs=True)
        if color_connections:
            # Disconnect from current index
            cmds.disconnectAttr(color_connections[0], f"{layered_texture_node}.inputs[{i}].color")
            
            # Reconnect to new index (i+1)
            cmds.connectAttr(color_connections[0], f"{layered_texture_node}.inputs[{i+1}].color", force=True)
            print(f"Moved color connection from input[{i}] to input[{i+1}]")
        
        # Handle alpha connections
        alpha_connections = cmds.listConnections(f"{layered_texture_node}.inputs[{i}].alpha", source=True, destination=False, plugs=True)
        if alpha_connections:
            # Disconnect from current index
            cmds.disconnectAttr(alpha_connections[0], f"{layered_texture_node}.inputs[{i}].alpha")
            
            # Reconnect to new index (i+1)
            cmds.connectAttr(alpha_connections[0], f"{layered_texture_node}.inputs[{i+1}].alpha", force=True)
            print(f"Moved alpha connection from input[{i}] to input[{i+1}]")

def connect_texture_to_mesh(mesh_transform, image_file_path, name_prefix="textureRigger", bind_joint=None):
    """
    Connects the specified texture to the mesh's material using a projection node.
    If the material already has a texture, uses a layeredTexture node to layer them.
    
    Args:
        mesh_transform (str): The transform node of the mesh
        image_file_path (str): Full path to the image file
        name_prefix (str): Prefix for naming created nodes
        bind_joint (str): Name of the bind joint to connect to the place3dTexture
        
    Returns:
        tuple: (file_node, projection_node, place2d_node, place3d_node, layered_texture, material_node) or (None, None, None, None, None, None)
    """
    if not mesh_transform or not cmds.objExists(mesh_transform):
        cmds.warning(f"Mesh '{mesh_transform}' not found.")
        return None, None, None, None, None, None
        
    if not image_file_path or not os.path.exists(image_file_path):
        cmds.warning(f"Image file '{image_file_path}' not found.")
        return None, None, None, None, None, None
        
    # Get the mesh's material - Focus on finding existing materials
    material_nodes = []
    material_color_connections = []
    layered_texture_node = None
    existing_connection_to_layer = False
    material = None
    
    # Try multiple methods to find materials on the mesh to be more robust
    
    # Method 1: Check using listSets and listConnections command
    assigned_materials = []
    shading_groups = cmds.listSets(type=1, object=mesh_transform) or []
    
    for sg in shading_groups:
        mat = cmds.listConnections(sg + ".surfaceShader", source=True, destination=False)
        if mat:
            assigned_materials.extend(mat)
    
    # Method 2: Check using instObjGroups connection
    if not assigned_materials:
        try:
            shape_nodes = cmds.listRelatives(mesh_transform, shapes=True, fullPath=True) or []
            for shape in shape_nodes:
                # Check if instObjGroups[0] exists and is connected to a shading group
                inst_conn = cmds.listConnections(shape + ".instObjGroups[0]", type="shadingEngine")
                if inst_conn:
                    for sg in inst_conn:
                        mat = cmds.listConnections(sg + ".surfaceShader", source=True, destination=False)
                        if mat:
                            assigned_materials.extend(mat)
        except Exception as e:
            print(f"Error checking instObjGroups: {e}")
    
    # Method 3: Check direct connections to shading engines
    if not assigned_materials:
        shading_engines = cmds.listConnections(mesh_transform, type="shadingEngine") or []
        for sg in shading_engines:
            mat = cmds.listConnections(f"{sg}.surfaceShader", source=True, destination=False) or []
            if mat:
                assigned_materials.extend(mat)
    
    # If we found assigned materials, use them
    if assigned_materials:
        print(f"Found existing materials on mesh '{mesh_transform}': {assigned_materials}")
        material = assigned_materials[0]  # Use the first found material
    else:
        # Final attempt - try to create a list of all materials in the scene and choose the first one
        # This is a fallback in case the mesh has a material but our detection methods fail
        print(f"No existing materials found on mesh '{mesh_transform}'. Falling back to default material.")
        
        # Get initial shading engine (usually initialShadingGroup contains lambert1)
        initial_sg = cmds.ls("initialShadingGroup", exactType="shadingEngine")
        if initial_sg:
            default_materials = cmds.listConnections(initial_sg[0] + ".surfaceShader", source=True, destination=False)
            if default_materials:
                material = default_materials[0]
                print(f"Using scene's default material: {material}")
            else:
                # Create a basic default material as last resort
                material_name = f"{name_prefix}_material"
                material = cmds.shadingNode('lambert', asShader=True, name=material_name)
                shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{material}_SG")
                cmds.connectAttr(f"{material}.outColor", f"{shading_group}.surfaceShader", force=True)
                cmds.sets(mesh_transform, edit=True, forceElement=shading_group)
                print(f"Created basic material '{material}' as last resort")
        else:
            # Create a basic default material if initialShadingGroup not found
            material_name = f"{name_prefix}_material"
            material = cmds.shadingNode('lambert', asShader=True, name=material_name)
            shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{material}_SG")
            cmds.connectAttr(f"{material}.outColor", f"{shading_group}.surfaceShader", force=True)
            cmds.sets(mesh_transform, edit=True, forceElement=shading_group)
            print(f"Created basic material '{material}' as last resort")
    
    # Ensure we have a material to work with
    if not material:
        cmds.warning(f"Failed to find or create a material for mesh '{mesh_transform}'.")
        return None, None, None, None, None, None
    
    print(f"Using material '{material}' for texture connection")
    
    # Get material name for layered texture naming
    material_name = material.split('|')[-1].split(':')[-1]
    material_prefix = material_name.split('_')[0] if '_' in material_name else material_name
    layered_texture_name = f"{material_prefix}_layeredTexture"
    
    # Check if material already has a texture connected to its baseColor or color
    material_color_attr = None
    if cmds.attributeQuery('baseColor', node=material, exists=True):
        material_color_attr = f"{material}.baseColor"
    elif cmds.attributeQuery('color', node=material, exists=True):
        material_color_attr = f"{material}.color"
    elif cmds.attributeQuery('diffuseColor', node=material, exists=True):
        material_color_attr = f"{material}.diffuseColor"
    
    if not material_color_attr:
        cmds.warning(f"Cannot find color attribute on material '{material}'.")
        return None, None, None, None, None, None
    
    # Check if anything is connected to the color attribute
    material_color_connections = cmds.listConnections(material_color_attr, source=True, destination=False, plugs=True)
    
    # Check if what's connected is a layeredTexture (from previous runs of this tool)
    if material_color_connections:
        connected_node = material_color_connections[0].split('.')[0]
        if cmds.objectType(connected_node) == 'layeredTexture':
            layered_texture_node = connected_node
            existing_connection_to_layer = True
            print(f"Found existing layeredTexture node '{layered_texture_node}' connected to material")
    
    # Create a file texture node
    file_node = cmds.shadingNode('file', asTexture=True, name=f"{name_prefix}_texture")
    # Set the file path
    cmds.setAttr(f"{file_node}.fileTextureName", image_file_path, type="string")
    
    # Create a place2dTexture node for the file
    place2d_node = cmds.shadingNode('place2dTexture', asUtility=True, name=f"{name_prefix}_place2d")
    
    # Connect place2dTexture to file node
    place2d_attrs = [
        "coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV", 
        "stagger", "wrapU", "wrapV", "repeatUV", "offset", "rotateUV", 
        "noiseUV", "vertexUvOne", "vertexUvTwo", "vertexUvThree", 
        "vertexCameraOne", "outUV", "outUvFilterSize"
    ]
    
    for attr in place2d_attrs:
        if cmds.attributeQuery(attr, node=place2d_node, exists=True) and \
           cmds.attributeQuery(attr, node=file_node, exists=True):
            try:
                cmds.connectAttr(f"{place2d_node}.{attr}", f"{file_node}.{attr}", force=True)
            except:
                print(f"Failed to connect {attr}")
    
    # Create a place3dTexture node for the projection
    place3d_node = cmds.shadingNode('place3dTexture', asUtility=True, name=f"{name_prefix}_place3d")
    
    # Set the scale of place3dTexture to 0.5
    cmds.setAttr(f"{place3d_node}.scale", 0.5, 0.5, 0.5, type="double3")
    
    # Create a projection node
    projection_node = cmds.shadingNode('projection', asUtility=True, name=f"{name_prefix}_projection")
    
    # Set projection type to "planar" (1)
    cmds.setAttr(f"{projection_node}.projType", 1)
    
    # Set Wrap to off
    if cmds.attributeQuery('wrap', node=projection_node, exists=True):
        cmds.setAttr(f"{projection_node}.wrap", 0)  # 0 = off
    
    # Set defaultColor to [0, 0, 0]
    cmds.setAttr(f"{projection_node}.defaultColor", 0, 0, 0, type="double3")
    
    # Connect file node to projection node
    cmds.connectAttr(f"{file_node}.outColor", f"{projection_node}.image", force=True)
    
    # Connect place3dTexture to projection node
    cmds.connectAttr(f"{place3d_node}.worldInverseMatrix[0]", f"{projection_node}.placementMatrix", force=True)

    # New alpha handling logic starts here
    # 1. Create a new layeredTexture node for alpha
    alpha_layered_texture_node = cmds.shadingNode('layeredTexture', asTexture=True, name=f"{name_prefix}_alpha_layeredTexture")
    
    # 2. Connect main image's alpha to the new layeredTexture's inputs[0].alpha
    cmds.connectAttr(f"{file_node}.outAlpha", f"{alpha_layered_texture_node}.inputs[0].alpha", force=True)
    
    # 3. Set inputs[0].color of the new layeredTexture to white
    cmds.setAttr(f"{alpha_layered_texture_node}.inputs[0].color", 1, 1, 1, type="double3")
    
    # 4. Create a new projection node for alpha
    alpha_projection_node = cmds.shadingNode('projection', asUtility=True, name=f"{name_prefix}_alpha_projection")
    
    # Set alpha_projection_node type to "planar" (1) and wrap off, default color black
    cmds.setAttr(f"{alpha_projection_node}.projType", 1)
    if cmds.attributeQuery('wrap', node=alpha_projection_node, exists=True):
        cmds.setAttr(f"{alpha_projection_node}.wrap", 0)
    cmds.setAttr(f"{alpha_projection_node}.defaultColor", 0, 0, 0, type="double3")

    # 5. Connect the new layeredTexture to the new alpha projection node's image
    cmds.connectAttr(f"{alpha_layered_texture_node}.outColor", f"{alpha_projection_node}.image", force=True)
    
    # 6. Connect the existing place3dTexture to the new alpha projection node's placementMatrix
    cmds.connectAttr(f"{place3d_node}.worldInverseMatrix[0]", f"{alpha_projection_node}.placementMatrix", force=True)
    
    # 7. Connect the new alpha projection node's outColorR to the main projection_node's alphaOffset
    cmds.connectAttr(f"{alpha_projection_node}.outColorR", f"{projection_node}.alphaOffset", force=True)
    # End of new alpha handling logic
    
    # Handle connection to material based on whether there's an existing texture
    if material_color_connections and not existing_connection_to_layer:
        # There's an existing texture but not a layeredTexture, so create one
        layered_texture_node = cmds.shadingNode('layeredTexture', asTexture=True, name=layered_texture_name)
        
        # Connect the existing texture to layer 1 (index 1)
        existing_texture_out = material_color_connections[0]
        
        # Disconnect existing texture from material
        cmds.disconnectAttr(existing_texture_out, material_color_attr)
        
        # Connect existing texture to layer 1 (not layer 0)
        cmds.connectAttr(existing_texture_out, f"{layered_texture_node}.inputs[1].color", force=True)
        
        # Connect new projection to layer 0 (top layer)
        cmds.connectAttr(f"{projection_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
        
        # Connect projection's outAlpha to layer 0's alpha
        cmds.connectAttr(f"{projection_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
        
        # Connect layeredTexture to material
        cmds.connectAttr(f"{layered_texture_node}.outColor", material_color_attr, force=True)
        
        print(f"Created layeredTexture with existing texture at layer 1 and new projection at layer 0 (top)")
        print(f"Connected {projection_node}.outAlpha to {layered_texture_node}.inputs[0].alpha")
        
    elif existing_connection_to_layer:
        # Already have a layeredTexture, shift all existing layers down and put new one at index 0
        max_layer_index = get_max_layer_index(layered_texture_node)
        if max_layer_index >= 0:
            # Shift layers down
            shift_layers_down(layered_texture_node, max_layer_index)
            
            # Connect new projection to top layer (index 0)
            cmds.connectAttr(f"{projection_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
            
            # Connect projection's outAlpha to layer 0's alpha
            cmds.connectAttr(f"{projection_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
            
            print(f"Shifted all layers down and connected new projection to top layer (layer 0)")
            print(f"Connected {projection_node}.outAlpha to {layered_texture_node}.inputs[0].alpha")
        else:
            # If no layers found, just connect to layer 0
            cmds.connectAttr(f"{projection_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
            
            # Connect projection's outAlpha to layer 0's alpha
            cmds.connectAttr(f"{projection_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
            
            print(f"Connected new projection to layer 0 of empty layeredTexture")
            print(f"Connected {projection_node}.outAlpha to {layered_texture_node}.inputs[0].alpha")
        
    else:
        # No existing texture, create layered texture for future expansion
        layered_texture_node = cmds.shadingNode('layeredTexture', asTexture=True, name=layered_texture_name)
        
        # Connect projection to layer 0
        cmds.connectAttr(f"{projection_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
        
        # Connect projection's outAlpha to layer 0's alpha
        cmds.connectAttr(f"{projection_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
        
        # Connect layeredTexture to material
        try:
            cmds.connectAttr(f"{layered_texture_node}.outColor", material_color_attr, force=True)
            print(f"Created new layeredTexture with projection at layer 0")
            print(f"Connected {projection_node}.outAlpha to {layered_texture_node}.inputs[0].alpha")
        except Exception as e:
            cmds.warning(f"Failed to connect layered texture to material: {e}")
            # Clean up nodes if connection failed
            cmds.delete(file_node, place2d_node, place3d_node, projection_node, layered_texture_node)
            return None, None, None, None, None, None
    
    # If bind_joint is provided, set up constraints
    if bind_joint and cmds.objExists(bind_joint):
        try:
            # Match place3dTexture's position and rotation to the bind_joint
            translation = cmds.xform(bind_joint, query=True, worldSpace=True, translation=True)
            rotation = cmds.xform(bind_joint, query=True, worldSpace=True, rotation=True)
            
            # Set the place3dTexture's position and rotation
            cmds.xform(place3d_node, worldSpace=True, translation=translation)
            cmds.xform(place3d_node, worldSpace=True, rotation=rotation)
            
            # Create parent constraint
            parent_constraint = cmds.parentConstraint(bind_joint, place3d_node, maintainOffset=True)[0]
            print(f"Created parent constraint '{parent_constraint}' from '{bind_joint}' to '{place3d_node}'")
            
            # Create scale constraint
            scale_constraint = cmds.scaleConstraint(bind_joint, place3d_node, maintainOffset=True)[0]
            print(f"Created scale constraint '{scale_constraint}' from '{bind_joint}' to '{place3d_node}'")
            
        except Exception as e:
            cmds.warning(f"Failed to constrain place3dTexture to bind joint: {e}")
    
    print(f"Connected texture '{os.path.basename(image_file_path)}' to material '{material}' using projection")
    return file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material

# Removed connect_texture_with_alpha function as it's no longer needed.

def organize_scene_hierarchy(mesh_transform, follicle_transform, place3d_node, name_prefix):
    """
    Organizes the scene hierarchy according to specified requirements:
    1. Places mesh under GEO group
    2. Creates RIG group with prefix_Texture_ctrl_grp for follicle
    3. Places place3dTexture under UTIL group
    4. Sets follicle shape node visibility to off
    5. Sets UTIL group visibility to off
    
    Args:
        mesh_transform (str): The mesh transform node
        follicle_transform (str): The follicle transform node
        place3d_node (str): The place3dTexture node
        name_prefix (str): User-provided prefix for naming
    """
    if not follicle_transform or not place3d_node: # mesh_transform can be optional if not found
        print("Warning: Follicle or place3d_node not provided to organize_scene_hierarchy. Skipping.")
        return
    
    # 1. GEO group for mesh
    geo_group_name = "GEO"
    geo_group_long_name = ""
    if not cmds.objExists(geo_group_name):
        geo_group_name = cmds.group(empty=True, name=geo_group_name)
        print(f"Created GEO group: {geo_group_name}")
    geo_group_long_name = cmds.ls(geo_group_name, long=True)[0]
    
    # Check and parent mesh_transform
    if cmds.objExists(mesh_transform):
        current_mesh_parent_list = cmds.listRelatives(mesh_transform, parent=True, fullPath=True)
        is_mesh_in_geo = False
        if current_mesh_parent_list and current_mesh_parent_list[0] == geo_group_long_name:
            is_mesh_in_geo = True
        
        if not is_mesh_in_geo:
            try:
                cmds.parent(mesh_transform, geo_group_long_name)
                print(f"Moved {mesh_transform} under {geo_group_name}")
            except Exception as e:
                print(f"Could not move {mesh_transform} under {geo_group_name}: {e}")
        # else:
            # print(f"Mesh {mesh_transform} is already under {geo_group_name}.") # Optional: uncomment for debugging
    else:
        print(f"Warning: Mesh transform '{mesh_transform}' not found. Skipping GEO group organization for mesh.")
    
    # 2. RIG group with prefix_Texture_ctrl_grp for follicle
    rig_group_name = "RIG"
    rig_group_long_name = ""
    if not cmds.objExists(rig_group_name):
        rig_group_name = cmds.group(empty=True, name=rig_group_name)
        print(f"Created RIG group: {rig_group_name}")
    rig_group_long_name = cmds.ls(rig_group_name, long=True)[0]
    
    # Create prefix_Texture_ctrl_grp under RIG
    texture_ctrl_grp_name = f"{name_prefix}_Texture_ctrl_grp"
    texture_ctrl_grp_long_name = ""
    if not cmds.objExists(texture_ctrl_grp_name):
        texture_ctrl_grp_name = cmds.group(empty=True, name=texture_ctrl_grp_name, parent=rig_group_long_name)
        print(f"Created {texture_ctrl_grp_name} under {rig_group_name}")
    else: # Ensure it's under RIG if it exists
        current_texture_ctrl_grp_parent_list = cmds.listRelatives(texture_ctrl_grp_name, parent=True, fullPath=True)
        if not current_texture_ctrl_grp_parent_list or current_texture_ctrl_grp_parent_list[0] != rig_group_long_name:
            try:
                cmds.parent(texture_ctrl_grp_name, rig_group_long_name)
                print(f"Moved existing {texture_ctrl_grp_name} under {rig_group_name}")
            except Exception as e:
                print(f"Could not move existing {texture_ctrl_grp_name} under {rig_group_name}: {e}")
    texture_ctrl_grp_long_name = cmds.ls(texture_ctrl_grp_name, long=True)[0]
    
    # Move follicle under texture_ctrl_grp
    if cmds.objExists(follicle_transform):
        current_follicle_parent_list = cmds.listRelatives(follicle_transform, parent=True, fullPath=True)
        is_follicle_in_ctrl_grp = False
        if current_follicle_parent_list and current_follicle_parent_list[0] == texture_ctrl_grp_long_name:
            is_follicle_in_ctrl_grp = True

        if not is_follicle_in_ctrl_grp:
            try:
                cmds.parent(follicle_transform, texture_ctrl_grp_long_name)
                print(f"Moved {follicle_transform} under {texture_ctrl_grp_name}")
            except Exception as e:
                print(f"Could not move {follicle_transform} under {texture_ctrl_grp_name}: {e}")
        # else:
            # print(f"Follicle {follicle_transform} is already under {texture_ctrl_grp_name}.") # Optional
    else:
        print(f"Warning: Follicle transform '{follicle_transform}' not found. Skipping parenting.")

    # Set follicle shape node visibility to off
    follicle_shapes = cmds.listRelatives(follicle_transform, shapes=True, type="follicle")
    if follicle_shapes:
        for shape in follicle_shapes:
            try:
                cmds.setAttr(f"{shape}.visibility", 0)
                print(f"Set visibility of follicle shape '{shape}' to off")
            except Exception as e:
                print(f"Could not set visibility of follicle shape '{shape}': {e}")
    
    # 3. UTIL group for place3dTexture
    util_group_name = "UTIL"
    util_group_long_name = ""
    if not cmds.objExists(util_group_name):
        util_group_name = cmds.group(empty=True, name=util_group_name)
        print(f"Created UTIL group: {util_group_name}")
    util_group_long_name = cmds.ls(util_group_name, long=True)[0]
    
    # Move place3dTexture under UTIL
    if cmds.objExists(place3d_node):
        current_place3d_parent_list = cmds.listRelatives(place3d_node, parent=True, fullPath=True)
        is_place3d_in_util = False
        if current_place3d_parent_list and current_place3d_parent_list[0] == util_group_long_name:
            is_place3d_in_util = True

        if not is_place3d_in_util:
            try:
                cmds.parent(place3d_node, util_group_long_name)
                print(f"Moved {place3d_node} under {util_group_name}")
            except Exception as e:
                print(f"Could not move {place3d_node} under {util_group_name}: {e}")
        # else:
            # print(f"Node {place3d_node} is already under {util_group_name}.") # Optional
    else:
        print(f"Warning: place3dTexture node '{place3d_node}' not found. Skipping parenting.")
    
    # Set UTIL group visibility to off
    try:
        cmds.setAttr(f"{util_group_name}.visibility", 0)
        print(f"Set visibility of UTIL group to off")
    except Exception as e:
        print(f"Could not set visibility of UTIL group: {e}")

def find_bind_joint_from_follicle(follicle_transform):
    """
    Finds the _bind joint related to the follicle created in step 2.
    
    Args:
        follicle_transform (str): The transform node of the follicle
        
    Returns:
        str: Name of the bind joint or None if not found
    """
    if not follicle_transform or not cmds.objExists(follicle_transform):
        return None
    
    # Try to find the bind joint based on naming convention
    base_name = follicle_transform.split('|')[-1].split(':')[-1]
    possible_bind_joint = f"{base_name}_bind"
    
    if cmds.objExists(possible_bind_joint):
        return possible_bind_joint
    
    # If not found by name, search for a joint under the slide_ctrl
    slide_ctrl_candidates = cmds.listRelatives(follicle_transform, allDescendents=True, type="transform") or []
    
    for ctrl in slide_ctrl_candidates:
        if "_Slide_ctrl" in ctrl:
            # Check for joints under this control
            joints = cmds.listRelatives(ctrl, allDescendents=True, type="joint") or []
            joints += cmds.listRelatives(ctrl, children=True, type="joint") or []
            
            for joint in joints:
                if "_bind" in joint:
                    return joint
    
    return None

def run_step3_logic(mesh_transform, image_file_path=None, name_prefix="textureRigger", follicle_transform=None):
    """
    Step 3's main logic: Connect texture to mesh material using projection
    
    Args:
        mesh_transform (str): The transform node of the mesh
        image_file_path (str, optional): Path to image file. If None, user will be prompted to select one.
        name_prefix (str, optional): Prefix for naming created nodes
        follicle_transform (str, optional): The transform node of the follicle created in step 2
        
    Returns:
        tuple: (file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material_node) or (None, None, None, None, None, None)
    """
    if not mesh_transform or not cmds.objExists(mesh_transform):
        cmds.warning("No valid mesh transform provided for texture connection.")
        return None, None, None, None, None, None
    
    # If no image file path provided, prompt user to select one
    if not image_file_path:
        image_file_path = select_image_file()
        if not image_file_path:
            cmds.warning("No image file selected.")
            return None, None, None, None, None, None
    
    # Find the bind joint from the follicle
    bind_joint = None
    if follicle_transform:
        bind_joint = find_bind_joint_from_follicle(follicle_transform)
        if bind_joint:
            print(f"Found bind joint '{bind_joint}' to constrain place3dTexture")
        else:
            print("No bind joint found. Place3dTexture will not be constrained.")
    
    # Connect the texture to the mesh's material
    result = connect_texture_to_mesh(mesh_transform, image_file_path, name_prefix, bind_joint)
    
    # If successful, organize the scene hierarchy
    if all(result):
        file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material = result
        organize_scene_hierarchy(mesh_transform, follicle_transform, place3d_node, name_prefix)
        return file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material
    
    return None, None, None, None, None, None