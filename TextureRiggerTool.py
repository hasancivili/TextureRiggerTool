import maya.cmds as cmds
import importlib

# Import logic files
import step1_logic
import step2_logic
import step3_logic

# For reloading modules during development (optional)
importlib.reload(step1_logic)
importlib.reload(step2_logic)
importlib.reload(step3_logic)

class TextureRiggerUI: # Changed from UVToolUI
    def __init__(self):
        self.window_name = "textureRiggerMainWindow" # Changed from "uvToolMainWindow"
        self.ui_title = "Texture Rigger 0.0.2" # Changed from "UV Based Follicle Tool"

        self.selected_mesh_transform = None
        self.selected_mesh_shape = None
        
        # Data storage for multiple locators and their associated nodes
        # self.locators_data will store: {prefix: locator_name}
        self.locators_data = {}
        # self.follicles_data will store: {prefix: {'follicle': follicle_node, 'control': control_node, 'locator_at_creation': locator_node_used_for_creation}}
        self.follicles_data = {}
        # self.textures_data will store: 
        # {prefix: {'file_path': path, 'file_node': node, 'projection_node': node, 
        #           'place2d_node': node, 'place3d_node': node, 
        #           'layered_texture': node, 'material': node}}
        self.textures_data = {}
        
        self.name_prefix = "Prefix" # Default name prefix for the *next* locator

        # Variables for UI elements
        self.name_field = None

        # Step 1 UI
        self.step1_frame = None
        self.select_mesh_button = None # Changed: Button to select mesh only
        self.create_locator_button = None # New: Button to create locator with current prefix
        self.locator_list_widget = None # List to display created locators
        self.step1_status_label = None

        # Step 2 UI
        self.step2_frame = None
        self.create_follicles_button = None
        self.step2_status_label = None
        
        # Step 3 UI
        self.step3_frame = None
        self.texture_selection_layout = None # Layout for dynamic texture rows
        self.texture_path_fields = {} # {prefix: ui_textField_widget}
        self.select_texture_buttons = {} # {prefix: ui_button_widget}
        self.connect_all_textures_button = None
        self.step3_status_label = None

        self.delete_tool_nodes_button = None

    def on_window_close(self, *args):
        """
        Called when the UI window is closed by the user.
        Cleans up to reset the tool's state.
        """
        print(f"Window '{self.window_name}' closed by the user. Cleaning up tool state.")
        self.reset_tool_state()
        # If there are any, tool-specific cache cleaning operations can be done here.
        # For example, if there are any created scriptJobs, they can be terminated.

    def create_ui(self):
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name, window=True)

        self.window = cmds.window(
            self.window_name, 
            title=self.ui_title, 
            widthHeight=(450, 600), # Increased height for more UI elements
            sizeable=True,
            closeCommand=self.on_window_close  # Add window close command
        )
        
        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=10, parent=self.window)

        # --- Step 1 --- #
        self.step1_frame = cmds.frameLayout("step1_frame", label="STEP 1: Select Mesh & Create Locators", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5)
        step1_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step1_frame, rowSpacing=5)
        
        # Modified: Changed button to only select mesh, not create locator immediately
        self.select_mesh_button = cmds.button(label="Select Mesh", command=self.on_select_mesh_click, parent=step1_col_layout, height=30)
        
        # Name prefix field moved here (after mesh selection, before locator creation)
        name_row_layout = cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 80), (2, 300)], parent=step1_col_layout, rowSpacing=(1,3))
        cmds.text(label="Prefix:", align="right")
        # Ensure the changeCommand is correctly connected to on_name_changed
        self.name_field = cmds.textField(text=self.name_prefix, parent=name_row_layout, 
                                    changeCommand=self.on_name_changed)
        cmds.setParent("..") # name_row_layout
        
        # New button: Create locator (with current prefix) on the selected mesh
        self.create_locator_button = cmds.button(label="Create Locator", command=self.on_create_locator_click, parent=step1_col_layout, height=30, enable=False)
        
        cmds.text(label="Created Locators:", align="left", parent=step1_col_layout)
        self.locator_list_widget = cmds.textScrollList(numberOfRows=4, allowMultiSelection=False, parent=step1_col_layout, height=60)
        
        self.step1_status_label = cmds.text(label="Status: Waiting for mesh selection...", align="left", parent=step1_col_layout)
        cmds.setParent("..") # step1_col_layout
        cmds.setParent("..") # step1_frame

        # --- Step 2 --- #
        self.step2_frame = cmds.frameLayout("step2_frame", label="STEP 2: Create Follicles and Control Curves", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5, enable=False) # Initially disabled
        step2_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step2_frame, rowSpacing=5)
        cmds.text(label="Move the created locators to desired positions on the mesh.", align="left", parent=step2_col_layout)
        self.create_follicles_button = cmds.button(label="Create Follicles and Control Curves", command=self.on_create_follicles_click, parent=step2_col_layout, height=30)
        self.step2_status_label = cmds.text(label="Status: Waiting for locator positioning and follicle creation...", align="left", parent=step2_col_layout)
        cmds.setParent("..") # step2_col_layout
        cmds.setParent("..") # step2_frame

        # --- Step 3 --- #
        self.step3_frame = cmds.frameLayout("step3_frame", label="STEP 3: Select Textures & Connect to Materials", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5, enable=False) # Initially disabled
        step3_top_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step3_frame, rowSpacing=5)

        # This layout will be populated dynamically
        self.texture_selection_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=3, parent=step3_top_col_layout) 
        cmds.setParent("..") # texture_selection_layout (back to step3_top_col_layout)

        self.connect_all_textures_button = cmds.button(label="Connect All Selected Textures to Materials", command=self.on_connect_all_textures_click, parent=step3_top_col_layout, height=30, enable=False)
        self.step3_status_label = cmds.text(label="Status: Waiting for follicle creation to enable texture selection...", align="left", parent=step3_top_col_layout)
        cmds.setParent("..") # step3_top_col_layout
        cmds.setParent("..") # step3_frame

        # --- Cleanup --- #
        cleanup_frame = cmds.frameLayout(label="Cleanup", collapsable=True, collapse=True, parent=main_layout, marginWidth=10, marginHeight=5)
        cleanup_col_layout = cmds.columnLayout(adjustableColumn=True, parent=cleanup_frame)
        self.delete_tool_nodes_button = cmds.button(label="Delete Tool Generated Nodes", command=self.on_delete_tool_nodes_click, parent=cleanup_col_layout, height=25, backgroundColor=(0.8, 0.4, 0.4))
        cmds.setParent("..") # cleanup_col_layout
        cmds.setParent("..") # cleanup_frame

        cmds.showWindow(self.window)

    def on_name_changed(self, new_name):
        """
        Called when the name field is changed.
        Updates the self.name_prefix for the *next* locator to be created.
        """
        print(f"DEBUG: on_name_changed called with new_name = '{new_name}'")
        
        if not new_name or new_name.isspace():
            # If field is cleared, you might want a default or to prevent empty prefixes
            # For now, let's use a generic default if user clears it.
            self.name_prefix = "textureRig" 
            cmds.textField(self.name_field, edit=True, text=self.name_prefix)
            cmds.warning("Prefix cannot be empty. Using default 'textureRig'.")
        else:
            cleaned_name = ''.join(c for c in new_name if c.isalnum() or c == '_')
            if cleaned_name != new_name:
                cmds.textField(self.name_field, edit=True, text=cleaned_name)
            self.name_prefix = cleaned_name
            print(f"DEBUG: self.name_prefix updated to '{self.name_prefix}'")

    def _is_prefix_unique(self, prefix_to_check):
        return prefix_to_check not in self.locators_data

    def _update_locator_list_widget(self):
        cmds.textScrollList(self.locator_list_widget, edit=True, removeAll=True)
        for prefix, locator_name in self.locators_data.items():
            cmds.textScrollList(self.locator_list_widget, edit=True, append=f"{prefix}: {locator_name}")

    def update_step1_status(self, message, success=None):
        color = (0.9, 0.9, 0.9) # Default
        if success is True:
            color = (0.6, 0.9, 0.6) # Green
        elif success is False:
            color = (0.9, 0.6, 0.6) # Red
        cmds.text(self.step1_status_label, edit=True, label=f"Status: {message}", backgroundColor=color)

    def update_step2_status(self, message, success=None):
        color = (0.9, 0.9, 0.9) # Default
        if success is True:
            color = (0.6, 0.9, 0.6) # Green
        elif success is False:
            color = (0.9, 0.6, 0.6) # Red
        cmds.text(self.step2_status_label, edit=True, label=f"Status: {message}", backgroundColor=color)

    def update_step3_status(self, message, success=None):
        color = (0.9, 0.9, 0.9) # Default
        if success is True:
            color = (0.6, 0.9, 0.6) # Green
        elif success is False:
            color = (0.9, 0.6, 0.6) # Red
        cmds.text(self.step3_status_label, edit=True, label=f"Status: {message}", backgroundColor=color)

    def on_create_follicles_click(self, *args):
        if not self.selected_mesh_shape:
            self.update_step2_status("Mesh not selected from Step 1.", success=False)
            return

        if not self.locators_data:
            self.update_step2_status("No locators created in Step 1.", success=False)
            return

        all_successful = True
        created_count = 0
        self.follicles_data.clear() # Clear previous follicle data

        for prefix, locator_name in self.locators_data.items():
            if not cmds.objExists(self.selected_mesh_shape) or not cmds.objExists(locator_name):
                self.update_step2_status(f"Mesh or locator '{locator_name}' (prefix: '{prefix}') no longer exists.", success=False)
                all_successful = False
                # self.reset_tool_state() # Consider a more granular reset or error handling
                continue # Skip this locator
            
            # Run Step 2 logic for each locator
            follicle_transform, main_control = step2_logic.run_step2_logic(self.selected_mesh_shape, locator_name, prefix)
            
            if follicle_transform and main_control:
                self.follicles_data[prefix] = {
                    'follicle': follicle_transform, 
                    'control': main_control,
                    'locator_at_creation': locator_name # Store which locator was used
                }
                created_count += 1
                # Delete the locator used for this follicle after successful creation
                try:
                    if cmds.objExists(locator_name):
                        cmds.delete(locator_name)
                        print(f"Locator '{locator_name}' for prefix '{prefix}' deleted after follicle creation.")
                except Exception as e:
                    print(f"Could not delete locator '{locator_name}': {e}")
            else:
                all_successful = False
                self.update_step2_status(f"Failed to create follicle for prefix '{prefix}'. Check script editor.", success=False)
                # Decide if we should stop or continue with others

        # After processing all locators, update their status in self.locators_data or remove them
        # For simplicity, we'll clear locators_data as they are processed and deleted.
        # A more robust approach might mark them as processed.
        # For now, let's assume successful locators are deleted by step2_logic or above.
        # We need to update the UI list if locators are deleted one by one.
        # Let's refine locator deletion: only delete from self.locators_data if follicle was made.
        
        processed_prefixes = list(self.follicles_data.keys()) # Get prefixes for which follicles were made
        for prefix in processed_prefixes:
            if prefix in self.locators_data:
                # We already deleted the Maya node, now remove from our tracking dict
                del self.locators_data[prefix]
        self._update_locator_list_widget() # Refresh the list (should be empty or show remaining if some failed)

        if created_count > 0:
            self.update_step2_status(f"Successfully created {created_count} follicle(s)/control(s).", success=True)
            cmds.button(self.create_follicles_button, edit=True, enable=False) # Disable after use
            cmds.button(self.create_locator_button, edit=True, enable=False) # Disable creating more locators now
            cmds.textField(self.name_field, edit=True, enable=False) # Disable prefix field
            
            self._populate_texture_selection_ui() # Setup Step 3 UI
            cmds.frameLayout(self.step3_frame, edit=True, enable=True)
            self.update_step3_status(f"Select textures for {len(self.follicles_data)} prefix(es).")
            if self.follicles_data: # Enable connect button if there are follicles
                 cmds.button(self.connect_all_textures_button, edit=True, enable=True)
        elif not self.locators_data: # No locators left and none created
             self.update_step2_status("No locators available or all failed. Please restart Step 1.", success=False)
        else: # Some locators might remain if they failed
            self.update_step2_status(f"Processed locators. {created_count} created. Some may have failed or remain.", success=all_successful)

    def _populate_texture_selection_ui(self):
        # Clear previous UI elements in the dynamic layout
        children = cmds.columnLayout(self.texture_selection_layout, query=True, childArray=True) or []
        for child in children:
            cmds.deleteUI(child)
        
        self.texture_path_fields.clear()
        self.select_texture_buttons.clear()

        if not self.follicles_data:
            cmds.text(label="No follicles created. Cannot select textures.", parent=self.texture_selection_layout)
            return

        for prefix in self.follicles_data.keys():
            row_layout = cmds.rowColumnLayout(numberOfColumns=3, columnWidth=[(1, 120), (2, 200), (3, 100)], parent=self.texture_selection_layout, rowSpacing=(1,3))
            cmds.text(label=f"Texture for '{prefix}':", align="right")
            # Using a textField to display path, could be a text label if non-editable path is preferred
            path_field = cmds.textField(text="No texture selected", editable=False, width=190) 
            select_button = cmds.button(label="Select File...", command=lambda ignored_arg, p_captured=prefix: self._on_select_single_texture_click(p_captured))
            cmds.setParent("..") # row_layout

            self.texture_path_fields[prefix] = path_field
            self.select_texture_buttons[prefix] = select_button
            # Initialize texture data for this prefix
            self.textures_data[prefix] = {
                'file_path': None, 'file_node': None, 'projection_node': None, 
                'place2d_node': None, 'place3d_node': None, 
                'layered_texture': None, 'material': None
            }

    def _on_select_single_texture_click(self, prefix):
        file_paths = cmds.fileDialog2(fileMode=1, caption=f"Select Texture for Prefix: {prefix}")
        if file_paths and file_paths[0]:
            selected_file = file_paths[0]
            self.textures_data[prefix]['file_path'] = selected_file
            cmds.textField(self.texture_path_fields[prefix], edit=True, text=selected_file)
            self.update_step3_status(f"Texture for '{prefix}' selected. Ready to connect all.", success=True)
        else:
            self.update_step3_status(f"Texture selection cancelled for '{prefix}'.", success=False)

    def on_connect_all_textures_click(self, *args):
        if not self.selected_mesh_transform:
            cmds.warning("No mesh selected or initial locator created. Please complete Step 1.")
            return

        if not self.textures_data:
            cmds.warning("No textures selected or locators processed for texture connection.")
            return

        all_successful = True
        for prefix, tex_data in self.textures_data.items():
            texture_file_path = tex_data.get('file_path')
            if not texture_file_path or texture_file_path == "No texture selected":
                cmds.warning(f"No texture file selected for prefix '{prefix}'. Skipping.")
                continue

            # Ensure created_follicle_transform is correctly retrieved for the current prefix
            follicle_info = self.follicles_data.get(prefix)
            if not follicle_info:
                cmds.warning(f"Follicle data not found for prefix '{prefix}'. Cannot connect texture.")
                all_successful = False
                continue
            
            # The key should be 'follicle' instead of 'follicle_transform' to match how it's stored in on_create_follicles_click
            created_follicle_transform = follicle_info.get('follicle')
            if not created_follicle_transform:
                cmds.warning(f"Follicle transform not found for prefix '{prefix}' in on_connect_all_textures_click. Skipping texture connection.")
                all_successful = False
                continue
            
            # DEBUG LINE (can be removed once stable)
            print(f"DEBUG step3_logic call: Mesh='{self.selected_mesh_transform}', TextureFile='{texture_file_path}', Prefix='{prefix}', Follicle='{created_follicle_transform}'")

            # Call Step 3 logic, now expecting 7 return values
            # The 7th value is the (potentially updated) mesh transform path after scene organization
            file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material_node, updated_mesh_transform = step3_logic.run_step3_logic(
                mesh_transform=self.selected_mesh_transform,
                image_file_path=texture_file_path,
                name_prefix=prefix,
                follicle_transform=created_follicle_transform
            )

            if file_node:  # Check if connection was successful
                self.textures_data[prefix].update({
                    'file_node': file_node,
                    'projection_node': projection_node,
                    'place2d_node': place2d_node,
                    'place3d_node': place3d_node,
                    'layered_texture_node': layered_texture_node,
                    'material_node': material_node
                })
                # Update the class member for the selected mesh transform with the path returned
                # by step3_logic, which might have changed due to scene organization (e.g., parenting under GEO group).
                # This ensures subsequent iterations in this loop use the correct, current mesh path.
                self.selected_mesh_transform = updated_mesh_transform
                print(f"Successfully connected texture for prefix '{prefix}'. Mesh is now: {self.selected_mesh_transform}")
            else:
                cmds.warning(f"Texture connection failed for prefix '{prefix}'. Nodes not stored.")
                all_successful = False
                # If one connection fails, we might still want to continue with others,
                # but the self.selected_mesh_transform might not be updated if organization didn't run or failed.
                # However, run_step3_logic should return the original mesh_transform if it fails early.

        if all_successful:
            cmds.headsUpMessage(f"All selected textures connected and scene organized.", time=5.0)
            # Reset the tool UI to initial state so user can start with a new mesh
            self.reset_tool_state()
        else:
            cmds.warning("Some textures could not be connected. Please check the script editor for details.")

    def on_delete_tool_nodes_click(self, *args):
        nodes_to_delete = []
        
        # 1. Collect locators from self.locators_data
        for prefix, locator_name in self.locators_data.items():
            if locator_name and cmds.objExists(locator_name):
                nodes_to_delete.append(locator_name)

        # 2. Collect follicle-related nodes from self.follicles_data
        for prefix, follicle_data in self.follicles_data.items():
            control_group = follicle_data.get('control')
            if control_group and cmds.objExists(control_group):
                if control_group not in nodes_to_delete:
                    nodes_to_delete.append(control_group)
            
            follicle_node = follicle_data.get('follicle')
            if follicle_node and cmds.objExists(follicle_node):
                is_child_of_deleted_group = False
                if control_group and cmds.objExists(control_group) and control_group in nodes_to_delete:
                    try:
                        # Check if follicle is under the control group that's already marked for deletion
                        long_follicle_path = cmds.ls(follicle_node, long=True)[0]
                        long_control_group_path = cmds.ls(control_group, long=True)[0]
                        if long_follicle_path.startswith(long_control_group_path + "|"):
                            is_child_of_deleted_group = True
                    except Exception as e:
                        # print(f"Could not determine parentage for {follicle_node} under {control_group}: {e}")
                        pass # Assume not a child if check fails                
                if not is_child_of_deleted_group and follicle_node not in nodes_to_delete:
                    nodes_to_delete.append(follicle_node)

        # 3. Collect texture-related nodes from self.textures_data
        for prefix, tex_data in self.textures_data.items():
            material_name = tex_data.get('material')
            if material_name and cmds.objExists(material_name):
                if material_name not in nodes_to_delete:
                    nodes_to_delete.append(material_name)
            
            texture_nodes_keys = ['file_node', 'projection_node', 'place2d_node', 'place3d_node', 'layered_texture']
            for key in texture_nodes_keys:
                node_name = tex_data.get(key)
                if node_name and cmds.objExists(node_name):
                    if node_name not in nodes_to_delete:
                        nodes_to_delete.append(node_name)
        
        # Create a list of unique nodes to delete, preserving order (important for hierarchies)
        unique_nodes_to_delete = []
        if nodes_to_delete:
            processed_nodes = set()
            for node in nodes_to_delete:
                if node not in processed_nodes:
                    unique_nodes_to_delete.append(node)
                    processed_nodes.add(node)
        
        deleted_count = 0
        if unique_nodes_to_delete:
            print(f"Tool will attempt to delete the following nodes: {unique_nodes_to_delete}")
            for node in unique_nodes_to_delete:
                if cmds.objExists(node): # Final check before attempting deletion
                    try:
                        cmds.delete(node)
                        print(f"Successfully deleted node: {node}")
                        deleted_count += 1
                    except RuntimeError as e: 
                        print(f"Error deleting node {node}: {e}. It might be locked or part of a locked hierarchy.")
                    except Exception as e:
                        print(f"Generic error deleting node {node}: {e}")
            
            cmds.warning(f"Deleted {deleted_count} out of {len(unique_nodes_to_delete)} targeted tool-generated node(s).")
        else:
            cmds.warning("No tool-generated nodes found to delete (or they were already deleted).")
        
        self.reset_tool_state()

    def reset_step2_and_beyond(self):
        """Resets the UI and state for Step 2 and beyond."""
        cmds.frameLayout(self.step2_frame, edit=True, enable=False)
        cmds.button(self.create_follicles_button, edit=True, enable=True) # Re-enable for new set of locators
        self.update_step2_status("Waiting for locator positioning and follicle creation...")
        self.follicles_data.clear()

        # Reset Step 3
        cmds.frameLayout(self.step3_frame, edit=True, enable=False)
        # Clear dynamically created texture UI parts
        children = cmds.columnLayout(self.texture_selection_layout, query=True, childArray=True) or []
        for child in children:
            cmds.deleteUI(child)
        self.texture_path_fields.clear()
        self.select_texture_buttons.clear()
        cmds.button(self.connect_all_textures_button, edit=True, enable=False)
        self.update_step3_status("Waiting for follicle creation to enable texture selection...")
        self.textures_data.clear()

    def reset_tool_state(self):
        """Resets the entire UI and internal variables to the initial state."""
        self.selected_mesh_transform = None
        self.selected_mesh_shape = None
        
        self.locators_data.clear()
        self._update_locator_list_widget()
        
        self.reset_step2_and_beyond() # This will also clear follicle and texture data

        # Reset Step 1 UI elements to initial state
        cmds.button(self.select_mesh_button, edit=True, enable=True)
        cmds.button(self.create_locator_button, edit=True, enable=False)  # Disabled until mesh is selected
        
        # Reset prefix to default and update both internal state and UI
        default_prefix = "Prefix"
        self.name_prefix = default_prefix
        cmds.textField(self.name_field, edit=True, text=default_prefix, enable=True)
        
        self.update_step1_status("Waiting for mesh selection...")
        print("Tool state has been reset.")

    def on_select_mesh_click(self, *args):
        """Handles mesh selection only, without creating locators."""
        self.reset_step2_and_beyond()  # Clear subsequent steps
        
        # Get the selected mesh from Maya
        selected_objects = cmds.ls(selection=True, transforms=True)
        if not selected_objects:
            self.update_step1_status("No objects selected. Please select a mesh.", success=False)
            return

        # Look for a mesh in the selection
        mesh_transform = None
        mesh_shape = None
        
        for obj in selected_objects:
            shapes = cmds.listRelatives(obj, shapes=True) or []
            for shape in shapes:
                if cmds.objectType(shape, isType="mesh"):
                    mesh_transform = obj
                    mesh_shape = shape
                    break
            if mesh_transform:  # Stop after finding first mesh
                break
        
        if not mesh_transform or not mesh_shape:
            self.update_step1_status("Selected object is not a mesh. Please select a mesh.", success=False)
            return
        
        # Store the mesh for later use
        self.selected_mesh_transform = mesh_transform
        self.selected_mesh_shape = mesh_shape
        
        self.update_step1_status(f"Mesh '{mesh_transform}' selected. Choose a prefix and create locators.", success=True)
        cmds.button(self.create_locator_button, edit=True, enable=True)  # Enable locator creation now that mesh is selected
    
    def on_create_locator_click(self, *args):
        """Creates a locator on the already selected mesh using the current prefix."""
        if not self.selected_mesh_transform or not self.selected_mesh_shape:
            self.update_step1_status("No mesh selected. Please select a mesh first.", success=False)
            return

        # Get the current prefix directly from the text field to ensure we have the most recent value
        current_prefix = cmds.textField(self.name_field, query=True, text=True)
        # Also update our internal prefix member
        self.name_prefix = current_prefix
        
        print(f"DEBUG: Creating locator with prefix '{current_prefix}'")
        
        if not current_prefix or current_prefix.isspace():
            self.update_step1_status("Prefix for new locator cannot be empty.", success=False)
            return
            
        if not self._is_prefix_unique(current_prefix):
            self.update_step1_status(f"Prefix '{current_prefix}' already exists. Please use a unique prefix.", success=False)
            return
        
        # Create the locator at the UV point on the selected mesh
        _dummy_mesh_transform, _dummy_mesh_shape, locator = step1_logic.run_step1_logic(
            current_prefix, 
            self.selected_mesh_transform, 
            self.selected_mesh_shape
        )
        
        if locator:
            self.locators_data[current_prefix] = locator
            self._update_locator_list_widget()
            self.update_step1_status(f"Added locator '{locator}' (prefix: '{current_prefix}'). Position it.", success=True)
            
            # Suggest a new prefix for the next locator - better suffix logic
            if current_prefix.endswith('_1'):
                base_prefix = current_prefix[:-2]
                next_prefix = f"{base_prefix}_2"
            elif current_prefix.endswith('_2'):
                base_prefix = current_prefix[:-2]
                next_prefix = f"{base_prefix}_3"
            elif current_prefix.endswith('_3'):
                base_prefix = current_prefix[:-2]
                next_prefix = f"{base_prefix}_4"
            elif current_prefix.endswith('_4'):
                base_prefix = current_prefix[:-2]
                next_prefix = f"{base_prefix}_5"
            else:
                next_prefix = f"{current_prefix}_1"
                
            print(f"DEBUG: Suggesting next prefix: '{next_prefix}'")
            cmds.textField(self.name_field, edit=True, text=next_prefix)
            self.name_prefix = next_prefix
            
            # Enable Step 2 once we have at least one locator
            cmds.frameLayout(self.step2_frame, edit=True, enable=True)
            self.update_step2_status("Move locators. Create more locators or proceed to create follicles.")
        else:
            self.update_step1_status(f"Failed to add locator with prefix '{current_prefix}'. Check script editor.", success=False)

# To start the UI:
def show_ui():
    tool_ui = TextureRiggerUI() # Changed from UVToolUI
    tool_ui.create_ui()
    return tool_ui # If you want to access the UI object from outside

if __name__ == "__main__":
    # When this script is run directly, it opens the UI.
    ui_instance = show_ui()

