import maya.cmds as cmds
import importlib

# Logic dosyalarını import et
import step1_logic
import step2_logic
import step3_logic

# Geliştirme sırasında modülleri yeniden yüklemek için (opsiyonel)
importlib.reload(step1_logic)
importlib.reload(step2_logic)
importlib.reload(step3_logic)

class TextureRiggerUI: # Changed from UVToolUI
    def __init__(self):
        self.window_name = "textureRiggerMainWindow" # Changed from "uvToolMainWindow"
        self.ui_title = "Texture Rigger 0.0.1" # Changed from "UV Based Follicle Tool"

        self.selected_mesh_transform = None
        self.selected_mesh_shape = None
        self.created_locator = None
        self.created_follicle = None
        self.parent_group_in_follicle = None
        self.name_prefix = "Prefix" # Varsayılan isim öneki - Changed from "uv"
        
        # Step 3 için eklendi - Updated with all texture-related nodes including layeredTexture
        self.selected_texture_file = None
        self.created_file_node = None
        self.created_projection_node = None
        self.created_place2d_node = None
        self.created_place3d_node = None
        self.created_layered_texture = None
        self.connected_material = None

        # UI elemanları için değişkenler
        self.step1_frame = None
        self.select_mesh_button = None
        self.step1_status_label = None

        self.step2_frame = None
        self.create_follicle_button = None
        self.step2_status_label = None
        
        # Step 3 UI elemanları için değişkenler
        self.step3_frame = None
        self.select_texture_button = None
        self.connect_texture_button = None
        self.texture_path_label = None
        self.step3_status_label = None

        self.delete_tool_nodes_button = None
        self.name_field = None # İsim alanı için değişken

    def on_window_close(self, *args):
        """
        UI penceresi kullanıcı tarafından kapatıldığında çağrılır.
        Aracın durumunu sıfırlamak için temizlik yapar.
        """
        print(f"Pencere '{self.window_name}' kullanıcı tarafından kapatıldı. Araç durumu temizleniyor.")
        self.reset_tool_state()
        # Burada varsa, araca özel diğer önbellek temizleme işlemleri yapılabilir.
        # Örneğin, oluşturulmuş scriptJob'lar varsa onlar sonlandırılabilir.

    def create_ui(self):
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name, window=True)

        self.window = cmds.window(
            self.window_name, 
            title=self.ui_title, 
            widthHeight=(400, 400), 
            sizeable=True,
            closeCommand=self.on_window_close  # Pencere kapatma komutunu ekle
        )
        
        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=10, parent=self.window)

        # --- Name Prefix --- #
        name_frame = cmds.frameLayout("name_frame", label="Name Prefix", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5)
        name_layout = cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 100), (2, 280)], parent=name_frame)
        cmds.text(label="Prefix:", align="right", parent=name_layout)
        self.name_field = cmds.textField(text=self.name_prefix, parent=name_layout, 
                                        changeCommand=self.on_name_changed)
        cmds.setParent("..") # name_layout
        cmds.setParent("..") # name_frame

        # --- Step 1 --- #
        self.step1_frame = cmds.frameLayout("step1_frame", label="STEP 1: Select Mesh & Create Locator", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5)
        step1_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step1_frame, rowSpacing=5)
        self.select_mesh_button = cmds.button(label="Select Mesh and Create Locator", command=self.on_select_mesh_click, parent=step1_col_layout, height=30)
        self.step1_status_label = cmds.text(label="Status: Waiting for mesh selection...", align="left", parent=step1_col_layout)
        cmds.setParent("..") # step1_col_layout
        cmds.setParent("..") # step1_frame

        # --- Step 2 --- #
        self.step2_frame = cmds.frameLayout("step2_frame", label="STEP 2: Create Follicle and  Control Curve", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5, enable=False) # Başlangıçta disable
        step2_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step2_frame, rowSpacing=5)
        cmds.text(label="Move the created locator to the desired position on the mesh.", align="left", parent=step2_col_layout)
        self.create_follicle_button = cmds.button(label="Create Control Curve", command=self.on_create_follicle_click, parent=step2_col_layout, height=30)
        self.step2_status_label = cmds.text(label="Status: Waiting for locator positioning and follicle creation...", align="left", parent=step2_col_layout)
        cmds.setParent("..") # step2_col_layout
        cmds.setParent("..") # step2_frame

        # --- Step 3 --- #
        self.step3_frame = cmds.frameLayout("step3_frame", label="STEP 3: Select Texture & Connect to Material", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5, enable=False) # Başlangıçta disable
        step3_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step3_frame, rowSpacing=5)
        self.select_texture_button = cmds.button(label="Select Texture File", command=self.on_select_texture_click, parent=step3_col_layout, height=30)
        self.texture_path_label = cmds.text(label="Selected Texture: None", align="left", parent=step3_col_layout)
        self.connect_texture_button = cmds.button(label="Connect Texture to Material", command=self.on_connect_texture_click, parent=step3_col_layout, height=30, enable=False)
        self.step3_status_label = cmds.text(label="Status: Waiting for texture selection...", align="left", parent=step3_col_layout)
        cmds.setParent("..") # step3_col_layout
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
        İsim alanı değiştirildiğinde çağrılır.
        """
        if not new_name or new_name.isspace():
            self.name_prefix = "textureRigger" # Eğer boş ise varsayılan değeri kullan - Changed from "uv"
            cmds.textField(self.name_field, edit=True, text=self.name_prefix)
        else:
            # Özel karakterleri ve boşlukları temizle
            cleaned_name = ''.join(c for c in new_name if c.isalnum() or c == '_')
            if cleaned_name != new_name:
                cmds.textField(self.name_field, edit=True, text=cleaned_name)
            self.name_prefix = cleaned_name

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

    def on_select_mesh_click(self, *args):
        self.reset_step2_and_beyond() # Önceki steplerden kalanları temizle
        
        mesh_transform, mesh_shape, locator = step1_logic.run_step1_logic(self.name_prefix)
        if mesh_transform and mesh_shape and locator:
            self.selected_mesh_transform = mesh_transform
            self.selected_mesh_shape = mesh_shape
            self.created_locator = locator
            self.update_step1_status(f"Locator '{locator}' created for mesh '{mesh_transform}'. Position the locator.", success=True)
            cmds.frameLayout(self.step2_frame, edit=True, enable=True) # Step 2'yi aktif et
            cmds.button(self.select_mesh_button, edit=True, enable=False) # Step 1 butonunu pasif et
            self.update_step2_status("Move the locator and click 'Create Follicle'.")
        else:
            self.selected_mesh_transform = None
            self.selected_mesh_shape = None
            self.created_locator = None
            self.update_step1_status("Failed to create locator. Check script editor for details.", success=False)
            cmds.frameLayout(self.step2_frame, edit=True, enable=False)

    def on_create_follicle_click(self, *args):
        if not self.selected_mesh_shape or not self.created_locator:
            self.update_step2_status("Missing mesh or locator from Step 1. Please restart Step 1.", success=False)
            return

        if not cmds.objExists(self.selected_mesh_shape) or not cmds.objExists(self.created_locator):
            self.update_step2_status("Mesh or locator from Step 1 no longer exists in the scene.", success=False)
            self.reset_tool_state()
            return

        # Locator adını sakla, çünkü step2_logic içinde silinebilir veya işlem sonrası silinecek
        locator_to_delete_after_success = self.created_locator 

        # Step 2 logic'i çalıştır - isim önekini de gönder
        follicle_transform, main_control = step2_logic.run_step2_logic(self.selected_mesh_shape, locator_to_delete_after_success, self.name_prefix)
        
        if follicle_transform and main_control:
            self.created_follicle = follicle_transform
            self.parent_group_in_follicle = main_control # Ana kontrol objesi 

            self.update_step2_status(f"Follicle '{follicle_transform}' ve kontrol '{main_control}' oluşturuldu ve ayarlandı.", success=True)
            cmds.button(self.create_follicle_button, edit=True, enable=False) # Step 2 butonunu pasif et
            
            # Step 1'de oluşturulan locator'ı sil
            if locator_to_delete_after_success and cmds.objExists(locator_to_delete_after_success):
                try:
                    cmds.delete(locator_to_delete_after_success)
                    print(f"Initial locator '{locator_to_delete_after_success}' deleted.")
                    if self.created_locator == locator_to_delete_after_success:
                         self.created_locator = None # UI state'ini güncelle
                except Exception as e:
                    print(f"Could not delete initial locator '{locator_to_delete_after_success}': {e}")
            
            # Eğer self.created_locator zaten None ise veya silinenle aynıysa None yap
            if self.created_locator == locator_to_delete_after_success:
                self.created_locator = None

            # Step 3'ü aktif et
            cmds.frameLayout(self.step3_frame, edit=True, enable=True)
            self.update_step3_status("Select a texture file and connect it to the material.")
        else:
            self.update_step2_status("Failed to create follicle. Check script editor for details.", success=False)

    def on_select_texture_click(self, *args):
        # Kullanıcıdan dosya seçmesini iste
        file_path = cmds.fileDialog2(fileMode=1, caption="Select Texture File")
        if file_path:
            self.selected_texture_file = file_path[0]
            cmds.text(self.texture_path_label, edit=True, label=f"Selected Texture: {self.selected_texture_file}")
            cmds.button(self.connect_texture_button, edit=True, enable=True)
            self.update_step3_status("Texture file selected. Click 'Connect Texture to Material'.", success=True)
        else:
            self.update_step3_status("No texture file selected.", success=False)

    def on_connect_texture_click(self, *args):
        if not self.selected_texture_file:
            self.update_step3_status("No texture file selected. Please select a texture file first.", success=False)
            return

        if not self.selected_mesh_transform:
            self.update_step3_status("No mesh selected from Step 1. Please restart the tool.", success=False)
            return

        # Step 3 logic'i çalıştır - isim önekini ve follicle transform'u gönder
        # Alpha texture ile ilgili kısım kaldırıldı. Sadece run_step3_logic çağrılacak.
        file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material = step3_logic.run_step3_logic(
            self.selected_mesh_transform, 
            self.selected_texture_file, 
            self.name_prefix,
            self.created_follicle  # Pass the follicle transform for binding to _bind joint
        )
            
        if file_node and projection_node and material:
            self.created_file_node = file_node
            self.created_projection_node = projection_node
            self.created_place2d_node = place2d_node
            self.created_place3d_node = place3d_node
            self.created_layered_texture = layered_texture_node
            self.connected_material = material

            # Organize scene hierarchy - Bu kısım değişmeden kalabilir, place3d_node hala organize edilecek.
            if self.created_place3d_node and self.created_follicle:
                step3_logic.organize_scene_hierarchy(self.selected_mesh_transform, self.created_follicle, self.created_place3d_node, self.name_prefix)
            
        else:
            self.update_step3_status("Failed to connect texture to material. Check script editor for details.", success=False)
            return
                
        # Status message about layered textures
        if self.created_layered_texture:
            connections = cmds.listConnections(f"{self.created_layered_texture}.inputs[*].color", source=True, destination=False)
            texture_count = len(connections) if connections else 0
            
            message = f"Texture connected to material '{self.connected_material}' using projection. {texture_count} textures in layer."
        else:
            message = f"Texture connected to material '{self.connected_material}' using projection."
            
        self.update_step3_status(message, success=True)
        
        # Reset buttons to allow the user to repeat the process
        cmds.button(self.select_mesh_button, edit=True, enable=True) # Step 1 butonunu aktif et
        cmds.button(self.create_follicle_button, edit=True, enable=True) # Step 2 butonunu aktif et
        cmds.button(self.select_texture_button, edit=True, enable=True) # Texture seçme butonunu aktif et
        cmds.button(self.connect_texture_button, edit=True, enable=True) # Connect butonunu aktif et
        
        # Update all step statuses to indicate user can proceed again
        self.update_step1_status("Ready to select another mesh or continue with current one.", success=True)
        self.update_step2_status("Ready to create another follicle.", success=True)
        self.update_step3_status(f"Texture connected successfully. You can select another texture.", success=True)

    def on_delete_tool_nodes_click(self, *args):
        nodes_to_delete = []
        if self.created_locator and cmds.objExists(self.created_locator):
            nodes_to_delete.append(self.created_locator)
            
        # Check for texture control group node based on prefix
        texture_ctrl_grp = f"{self.name_prefix}_Texture_ctrl_grp"
        if cmds.objExists(texture_ctrl_grp):
            nodes_to_delete.append(texture_ctrl_grp)
        else:
            # If control group doesn't exist, try to delete follicle directly
            if self.created_follicle and cmds.objExists(self.created_follicle):
                nodes_to_delete.append(self.created_follicle)
            
        # Step 3 temizliği için tüm texture node'larını ekle
        if self.created_file_node and cmds.objExists(self.created_file_node):
            nodes_to_delete.append(self.created_file_node)
        if self.created_projection_node and cmds.objExists(self.created_projection_node):
            nodes_to_delete.append(self.created_projection_node)
        if self.created_place2d_node and cmds.objExists(self.created_place2d_node):
            nodes_to_delete.append(self.created_place2d_node)
        if self.created_place3d_node and cmds.objExists(self.created_place3d_node):
            nodes_to_delete.append(self.created_place3d_node)
            
        # Only delete created materials, not existing ones that were used
        if self.connected_material and cmds.objExists(self.connected_material):
            # Check if the material name starts with the prefix and ends with "_material"
            # This indicates it was created by our tool rather than being a pre-existing material
            material_name = self.connected_material.split('|')[-1].split(':')[-1]
            if material_name.startswith(f"{self.name_prefix}_material"):
                nodes_to_delete.append(self.connected_material)
                print(f"Deleting created material: {self.connected_material}")
            else:
                print(f"Preserving existing material: {self.connected_material}")
        
        if nodes_to_delete:
            deleted_count = 0
            for node in nodes_to_delete:
                if cmds.objExists(node):
                    try:
                        cmds.delete(node)
                        deleted_count +=1
                    except Exception as e:
                        print(f"Error deleting node {node}: {e}")
            
            print(f"Deleted {deleted_count} tool-generated node(s).")
            cmds.warning(f"Deleted {deleted_count} tool-generated node(s).")
        else:
            cmds.warning("No tool-generated nodes found to delete (or they were already deleted).")
        
        self.reset_tool_state()

    def reset_step2_and_beyond(self):
        """Step 2 ve sonrasındaki UI ve state'i sıfırlar."""
        cmds.frameLayout(self.step2_frame, edit=True, enable=False)
        cmds.button(self.create_follicle_button, edit=True, enable=True)
        self.update_step2_status("Waiting for locator positioning and follicle creation...")
        self.created_follicle = None
        self.parent_group_in_follicle = None

        # Step 3'ü sıfırla
        cmds.frameLayout(self.step3_frame, edit=True, enable=False)
        cmds.button(self.select_texture_button, edit=True, enable=True)
        cmds.button(self.connect_texture_button, edit=True, enable=False)
        cmds.text(self.texture_path_label, edit=True, label="Selected Texture: None")
        self.update_step3_status("Waiting for texture selection...")
        self.selected_texture_file = None
        self.created_file_node = None
        self.connected_material = None

    def reset_tool_state(self):
        """Tüm arayüzü ve iç değişkenleri başlangıç durumuna sıfırlar."""
        self.selected_mesh_transform = None
        self.selected_mesh_shape = None
        if self.created_locator and cmds.objExists(self.created_locator):
            # Kullanıcı manuel silmiş olabilir, kontrol et
            pass # Silme butonuna bırakalım
        # self.created_locator = None # Silme butonuyla yönetiliyor
        
        self.reset_step2_and_beyond()

        cmds.button(self.select_mesh_button, edit=True, enable=True)
        self.update_step1_status("Waiting for mesh selection...")
        print("Tool state has been reset.")

# UI'ı başlatmak için:
def show_ui():
    tool_ui = TextureRiggerUI() # Changed from UVToolUI
    tool_ui.create_ui()
    return tool_ui # Eğer UI objesine dışarıdan erişmek isterseniz

if __name__ == "__main__":
    # Bu script doğrudan çalıştırıldığında UI'ı açar.
    ui_instance = show_ui()

