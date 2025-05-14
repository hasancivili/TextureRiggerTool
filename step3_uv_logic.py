import maya.cmds as cmds
import os
import step3_logic

def create_texture_uv_setup(prefix, follicle_transform, slide_ctrl):
    """
    Creates the UV reference setup for the given prefix.
    
    Args:
        prefix (str): The prefix for naming nodes
        follicle_transform (str): The follicle transform node
        slide_ctrl (str): The slide control node
        
    Returns:
        dict: Dictionary containing the created nodes
    """
    # Create the UV reference group and controls
    uv_ref = cmds.group(empty=True, name=f'{prefix}_UV_Ref')
    
    # Create the texture rotate group
    tex_rotate = cmds.group(empty=True, name=f'{prefix}_Texture_Rotate')
    cmds.parent(tex_rotate, uv_ref)
    cmds.setAttr(f'{tex_rotate}.translateX', 0.5)
    cmds.setAttr(f'{tex_rotate}.translateY', 0.5)
    cmds.makeIdentity(tex_rotate, apply=True, translate=True)
    
    # Create the texture reference group
    tex_ref = cmds.group(empty=True, name=f'{prefix}_Texture_Ref')
    cmds.parent(tex_ref, tex_rotate)
    cmds.setAttr(f'{tex_ref}.translateX', -0.5)
    cmds.setAttr(f'{tex_ref}.translateY', -0.5)
    
    # Create the texture control group
    tex_ctrl = cmds.group(empty=True, name=f'{prefix}_Texture_Control')
    cmds.parent(tex_ctrl, uv_ref)
    
    # Create constraints
    parent_constraint = cmds.parentConstraint(tex_ctrl, tex_ref, maintainOffset=True, name=f'{prefix}_ParentConstraint')[0]
    scale_constraint = cmds.scaleConstraint(tex_ctrl, tex_ref, maintainOffset=True, name=f'{prefix}_ScaleConstraint')[0]
    orient_constraint = cmds.orientConstraint(tex_ctrl, tex_rotate, maintainOffset=True, name=f'{prefix}_OrientConstraint')[0]
    
    # Group constraints
    constraints_grp = cmds.group(empty=True, name=f'{prefix}_Constraints')
    cmds.parent([parent_constraint, scale_constraint, orient_constraint], constraints_grp)
    cmds.parent(constraints_grp, uv_ref)
    
    # Add custom attributes
    custom_attrs = [
        'TranslateU', 'TranslateV',
        'ScaleU', 'ScaleV',
        'RotateFrame'
    ]
    
    for attr in custom_attrs:
        if not cmds.objExists(f'{tex_ref}.{attr}'):
            cmds.addAttr(tex_ref, longName=attr, attributeType='double', keyable=True)
    
    # Connect attributes
    cmds.connectAttr(f'{tex_ref}.translateX', f'{tex_ref}.TranslateU', force=True)
    cmds.connectAttr(f'{tex_ref}.translateY', f'{tex_ref}.TranslateV', force=True)
    cmds.connectAttr(f'{tex_ref}.scaleX', f'{tex_ref}.ScaleU', force=True)
    cmds.connectAttr(f'{tex_ref}.scaleY', f'{tex_ref}.ScaleV', force=True)
    
    # Create reverse rotation connection
    md_node = cmds.createNode('multiplyDivide', name=f'{prefix}_ReverseRotate_md')
    cmds.setAttr(f'{md_node}.input2X', -1)
    cmds.connectAttr(f'{tex_rotate}.rotateZ', f'{md_node}.input1X', force=True)
    cmds.connectAttr(f'{md_node}.outputX', f'{tex_ref}.RotateFrame', force=True)
    
    # Hide original transform attributes
    for attr in ['translateX', 'translateY', 'translateZ',
                 'rotateX', 'rotateY', 'rotateZ',
                 'scaleX', 'scaleY', 'scaleZ']:
        cmds.setAttr(f'{tex_ref}.{attr}', keyable=False, channelBox=False)
    
    # Connect follicle UV parameters to texture control
    follicle_shapes = cmds.listRelatives(follicle_transform, shapes=True, type="follicle") or []
    if follicle_shapes:
        follicle_shape = follicle_shapes[0]
        cmds.connectAttr(f'{follicle_shape}.parameterU', f'{tex_ctrl}.translateX', force=True)
        cmds.connectAttr(f'{follicle_shape}.parameterV', f'{tex_ctrl}.translateY', force=True)
    
    # Connect slide control to texture control
    if cmds.objExists(slide_ctrl):
        # Connect rotation directly
        cmds.connectAttr(f'{slide_ctrl}.rotateZ', f'{tex_ctrl}.rotateZ', force=True)
        
        # Connect scale through multiply node
        scale_md = cmds.createNode('multiplyDivide', name=f'{prefix}_ScaleFactor_md')
        cmds.setAttr(f'{scale_md}.input2X', 0.1)
        cmds.setAttr(f'{scale_md}.input2Y', 0.1)
        cmds.setAttr(f'{scale_md}.input2Z', 0.1)
        
        cmds.connectAttr(f'{slide_ctrl}.scale', f'{scale_md}.input1', force=True)
        cmds.connectAttr(f'{scale_md}.output', f'{tex_ctrl}.scale', force=True)
    
    return {
        'uv_ref': uv_ref,
        'tex_rotate': tex_rotate,
        'tex_ref': tex_ref,
        'tex_ctrl': tex_ctrl,
        'constraints_grp': constraints_grp
    }

def connect_texture_using_uvs(mesh_transform, image_file_path, name_prefix, follicle_transform=None):
    """
    Connects texture using UV-based method instead of projection.
    
    Args:
        mesh_transform (str): The transform node of the mesh
        image_file_path (str): Full path to the image file
        name_prefix (str): Prefix for naming created nodes
        follicle_transform (str): Name of the follicle transform node
        
    Returns:
        tuple: (file_node, place2d_node, tex_ref_setup, layered_texture, material_node, uv_ref_group)
    """
    if not mesh_transform or not cmds.objExists(mesh_transform):
        cmds.warning(f"Mesh '{mesh_transform}' not found.")
        return None, None, None, None, None, None
    
    if not image_file_path or not os.path.exists(image_file_path):
        cmds.warning(f"Image file '{image_file_path}' not found.")
        return None, None, None, None, None, None
    
    # Find material on mesh - reuse the same logic from step3_logic to find materials
    # This will return None, None, None, None, None, None if no material found
    material = None
    
    # Get the mesh's material - Focus on finding existing materials
    material = None # This will store the final material to be used.
    assigned_materials = [] # This list will store materials found on the mesh.

    # Try multiple methods to find materials on the mesh to be more robust
    if cmds.objExists(mesh_transform):
        # Method 1: Using listSets to find shading groups directly on the transform, then get their surfaceShader connection.
        shading_groups_from_sets = cmds.listSets(type=1, object=mesh_transform) or []
        for sg in shading_groups_from_sets:
            if cmds.attributeQuery('surfaceShader', node=sg, exists=True):
                mat_conns = cmds.listConnections(f"{sg}.surfaceShader", source=True, destination=False, plugs=False)
                if mat_conns:
                    for mat_node in mat_conns:
                        if cmds.ls(mat_node, materials=True) and mat_node not in assigned_materials:
                            assigned_materials.append(mat_node)

        # Method 2: If no materials found via listSets, check connections on the mesh's shape node(s).
        if not assigned_materials:
            shapes = cmds.listRelatives(mesh_transform, shapes=True, noIntermediate=True, fullPath=True) or []
            for shape in shapes:
                # SGs can be connected to shapes via instObjGroups or directly
                sgs_from_shape = cmds.listConnections(shape, type='shadingEngine')
                if sgs_from_shape:
                    for sg_shape in list(set(sgs_from_shape)): # Unique SGs
                        if cmds.attributeQuery('surfaceShader', node=sg_shape, exists=True):
                            mat_conns = cmds.listConnections(f"{sg_shape}.surfaceShader", source=True, destination=False, plugs=False)
                            if mat_conns:
                                for mat_node in mat_conns:
                                    if cmds.ls(mat_node, materials=True) and mat_node not in assigned_materials:
                                        assigned_materials.append(mat_node)
    
    # If we found assigned materials, use the first one.
    if assigned_materials:
        print(f"Found existing material(s) on mesh '{mesh_transform}': {assigned_materials}")
        material = assigned_materials[0]
    else:
        # Fallback: No existing materials found directly on the mesh.
        print(f"No existing materials found on mesh '{mesh_transform}'. Attempting to use or create a default material.")
        
        lambert1_as_fallback = None
        initial_sg_list = cmds.ls("initialShadingGroup", type="shadingEngine")
        if initial_sg_list:
            initial_sg = initial_sg_list[0]
            # Check if mesh is a member of initialShadingGroup
            members = cmds.sets(initial_sg, query=True) or []
            is_member = False
            if mesh_transform in members:
                is_member = True
            else:
                shapes = cmds.listRelatives(mesh_transform, shapes=True, noIntermediate=True, fullPath=True) or []
                for shape_node in shapes: # Renamed variable to avoid conflict
                    if shape_node in members:
                        is_member = True
                        break
            
            mat_conns_initial_sg = cmds.listConnections(f"{initial_sg}.surfaceShader", source=True, destination=False)
            if mat_conns_initial_sg and cmds.ls(mat_conns_initial_sg[0], materials=True):
                lambert1_as_fallback = mat_conns_initial_sg[0]

            if is_member and lambert1_as_fallback:
                material = lambert1_as_fallback
                print(f"Mesh '{mesh_transform}' is part of initialShadingGroup. Using its material: '{material}'.")
        
        if not material: # If not found via initialShadingGroup membership or other issues
            print(f"Creating a new Lambert material and assigning it to '{mesh_transform}'.")
            mesh_base_name = mesh_transform.split('|')[-1].split(':')[-1] # Clean name for new nodes
            new_material_node = None
            new_sg_node = None
            try:
                new_material_node = cmds.shadingNode('lambert', asShader=True, name=f"{mesh_base_name}_autoMat#")
                new_sg_node = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{new_material_node}SG#")
                
                cmds.connectAttr(f"{new_material_node}.outColor", f"{new_sg_node}.surfaceShader", force=True)
                cmds.sets(mesh_transform, edit=True, forceElement=new_sg_node)
                material = new_material_node
                print(f"Successfully created and assigned material '{material}' with SG '{new_sg_node}' to '{mesh_transform}'.")
            except RuntimeError as e:
                print(f"Error creating/assigning new material for '{mesh_transform}': {e}")
                if new_sg_node and cmds.objExists(new_sg_node): cmds.delete(new_sg_node)
                if new_material_node and cmds.objExists(new_material_node): cmds.delete(new_material_node)
                material = None
    
    # Ensure we have a material to work with
    if not material:
        cmds.warning(f"Failed to find, create, or assign a suitable material for mesh '{mesh_transform}'. Cannot connect texture.")
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
    
    # Initialize variables before they are used
    existing_connection_to_layer = False
    layered_texture_node = None
    
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
    # Set defaultColor to [0, 0, 0]
    cmds.setAttr(f"{file_node}.defaultColor", 0, 0, 0, type="double3")
    
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
    
    # Find the slide_ctrl
    slide_ctrl = None
    if follicle_transform and cmds.objExists(follicle_transform):
        all_descendants = cmds.listRelatives(follicle_transform, allDescendents=True, type="transform") or []
        for desc in all_descendants:
            if "_Slide_ctrl" in desc:
                slide_ctrl = desc
                break
    
    # Create UV reference setup
    tex_ref_setup = None
    if slide_ctrl:
        tex_ref_setup = create_texture_uv_setup(name_prefix, follicle_transform, slide_ctrl)
        
        # Connect the tex_ref attributes to the place2d node
        tex_ref = tex_ref_setup['tex_ref']
        
        # Connect the RotateFrame attribute
        cmds.connectAttr(f"{tex_ref}.RotateFrame", f"{place2d_node}.rotateFrame", force=True)
        
        # Connect the ScaleU to CoverageU and ScaleV to CoverageV
        cmds.connectAttr(f"{tex_ref}.ScaleU", f"{place2d_node}.coverageU", force=True)
        cmds.connectAttr(f"{tex_ref}.ScaleV", f"{place2d_node}.coverageV", force=True)
        
        # Connect TranslateU to translateFrameU and TranslateV to translateFrameV
        cmds.connectAttr(f"{tex_ref}.TranslateU", f"{place2d_node}.translateFrameU", force=True)
        cmds.connectAttr(f"{tex_ref}.TranslateV", f"{place2d_node}.translateFrameV", force=True)
    else:
        print(f"Warning: No slide_ctrl found for {name_prefix}. UV reference setup skipped.")
    
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
        
        # Connect new file texture to layer 0 (top layer)
        cmds.connectAttr(f"{file_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
        
        # Connect file's outAlpha to layer 0's alpha
        cmds.connectAttr(f"{file_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
        
        # Connect layeredTexture to material
        cmds.connectAttr(f"{layered_texture_node}.outColor", material_color_attr, force=True)
        
        print(f"Created layeredTexture with existing texture at layer 1 and new texture at layer 0 (top)")
        
    elif existing_connection_to_layer:
        # Already have a layeredTexture, shift all existing layers down and put new one at index 0
        max_layer_index = step3_logic.get_max_layer_index(layered_texture_node)
        if max_layer_index >= 0:
            # Shift layers down
            step3_logic.shift_layers_down(layered_texture_node, max_layer_index)
            
            # Connect new file texture to top layer (index 0)
            cmds.connectAttr(f"{file_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
            
            # Connect file's outAlpha to layer 0's alpha
            cmds.connectAttr(f"{file_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
            
            print(f"Shifted all layers down and connected new texture to top layer (layer 0)")
        else:
            # If no layers found, just connect to layer 0
            cmds.connectAttr(f"{file_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
            
            # Connect file's outAlpha to layer 0's alpha
            cmds.connectAttr(f"{file_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
            
            print(f"Connected new texture to layer 0 of empty layeredTexture")
    else:
        # No existing texture, create layered texture for future expansion
        layered_texture_node = cmds.shadingNode('layeredTexture', asTexture=True, name=layered_texture_name)
        
        # Connect file texture to layer 0
        cmds.connectAttr(f"{file_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
        
        # Connect file's outAlpha to layer 0's alpha
        cmds.connectAttr(f"{file_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
        
        # Connect layeredTexture to material
        try:
            cmds.connectAttr(f"{layered_texture_node}.outColor", material_color_attr, force=True)
            print(f"Created new layeredTexture with texture at layer 0")
        except Exception as e:
            cmds.warning(f"Failed to connect layered texture to material: {e}")
            # Clean up nodes if connection failed
            cmds.delete(file_node, place2d_node)
            if tex_ref_setup and 'uv_ref' in tex_ref_setup:
                cmds.delete(tex_ref_setup['uv_ref'])
            if cmds.objExists(layered_texture_node):
                cmds.delete(layered_texture_node)
            return None, None, None, None, None, None
    
    # Place UV_Ref group under the Texture_ctrl_grp if it exists
    if tex_ref_setup and 'uv_ref' in tex_ref_setup:
        texture_ctrl_grp_name = f"{name_prefix}_Texture_ctrl_grp"
        if cmds.objExists(texture_ctrl_grp_name):
            cmds.parent(tex_ref_setup['uv_ref'], texture_ctrl_grp_name)
    
    print(f"Connected texture '{os.path.basename(image_file_path)}' to material '{material}' using UV-based method")
    
    # Return tuple for the run_step3_logic function to use
    uv_ref_group = tex_ref_setup['uv_ref'] if tex_ref_setup else None
    return file_node, place2d_node, tex_ref_setup, layered_texture_node, material, uv_ref_group

def run_step3_uv_logic(mesh_transform, image_file_path=None, name_prefix="textureRigger", follicle_transform=None, is_sequence=False):
    """
    Main logic for Step 3 UV-based texture connection: Connects texture using UVs and organizes scene.
    
    Args:
        mesh_transform (str): Mesh transform node name
        image_file_path (str, optional): Path to image file
        name_prefix (str, optional): Prefix for node names
        follicle_transform (str, optional): Follicle transform node name
        is_sequence (bool, optional): Whether the texture is a sequence
        
    Returns:
        tuple: (file_node, None, place2d_node, None, layered_texture, material_node, updated_mesh_transform)
        or (None, None, None, None, None, None, original_mesh_transform_if_failed)
    """
    if not image_file_path:
        cmds.warning("No image file path provided for texture connection.")
        return None, None, None, None, None, None, mesh_transform
    
    file_node, place2d_node, tex_ref_setup, layered_texture, material, uv_ref_group = connect_texture_using_uvs(
        mesh_transform, 
        image_file_path, 
        name_prefix,
        follicle_transform=follicle_transform
    )

    updated_mesh_path_after_organization = mesh_transform 

    if not file_node: 
        cmds.warning(f"Texture connection failed for prefix '{name_prefix}'.")
        return None, None, None, None, None, None, mesh_transform

    # Find slide_ctrl for the follicle
    slide_ctrl = None
    if follicle_transform and cmds.objExists(follicle_transform):
        all_descendants = cmds.listRelatives(follicle_transform, allDescendents=True, type="transform") or []
        for desc in all_descendants:
            if "_Slide_ctrl" in desc:
                slide_ctrl = desc
                break
    
    # Setup sequence texture if needed
    if is_sequence and slide_ctrl and file_node:
        step3_logic.setup_sequence_texture(file_node, slide_ctrl, is_sequence)

    # Hide slide_ctrl attributes if needed
    if slide_ctrl:
        step3_logic.hide_slide_ctrl_attributes(slide_ctrl)
    
    # Use the same organizing function but with None for place3d_node
    if follicle_transform: 
        place3d_node_substitute = None  # No place3dTexture for UV-based method
        updated_mesh_path_after_organization = step3_logic.organize_scene_hierarchy(mesh_transform, follicle_transform, place3d_node_substitute, name_prefix)
        
        # Move the UV_Ref group under the Texture_ctrl_grp AFTER scene organization
        if tex_ref_setup and 'uv_ref' in tex_ref_setup and cmds.objExists(tex_ref_setup['uv_ref']):
            texture_ctrl_grp_name = f"{name_prefix}_Texture_ctrl_grp"
            # Find the group in the RIG hierarchy
            rig_group = "RIG"
            if cmds.objExists(rig_group) and cmds.objExists(texture_ctrl_grp_name):
                # Get the full path of the texture control group to ensure proper parenting
                texture_ctrl_grp_path = cmds.ls(texture_ctrl_grp_name, long=True)[0]
                
                # Parent the UV_Ref under the texture control group
                try:
                    cmds.parent(tex_ref_setup['uv_ref'], texture_ctrl_grp_path)
                    print(f"Parented {tex_ref_setup['uv_ref']} under {texture_ctrl_grp_path}")
                except Exception as e:
                    cmds.warning(f"Failed to parent UV_Ref under Texture_ctrl_grp: {e}")
    else:
        cmds.warning(f"Skipping scene organization for prefix '{name_prefix}' due to missing follicle node.")
            
    # Return None for projection_node and place3d_node since we're not using them in the UV-based method
    return file_node, None, place2d_node, None, layered_texture, material, updated_mesh_path_after_organization
