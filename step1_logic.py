import maya.cmds as cmds
import maya.OpenMaya as om

def check_uv_overlap(mesh_node, u_coord, v_coord):
    """
    Belirtilen UV koordinatında birden fazla yüzey (face) olup olmadığını kontrol eder.
    (Bu fonksiyonun doğruluğu ve etkinliği daha da geliştirilebilir.)
    """
    selection_list = om.MSelectionList()
    selection_list.add(mesh_node)
    dag_path = om.MDagPath()
    try:
        selection_list.getDagPath(0, dag_path)
    except RuntimeError:
        cmds.warning(f"Mesh node '{mesh_node}' DAG path alınamadı.")
        return True # Hata durumunda işlemi durdurmak için True dönelim

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
                    uv_tuple = (round(u_coord, 4), round(v_coord, 4)) # Tolerans için yuvarlama
                    if uv_tuple not in hit_faces:
                        hit_faces[uv_tuple] = []
                    if i not in hit_faces[uv_tuple]:
                        hit_faces[uv_tuple].append(i)
        except Exception as e:
            # print(f"Yüzey {i} için UV alınırken hata: {e}")
            continue
    
    uv_tuple_check = (round(u_coord, 4), round(v_coord, 4))
    if uv_tuple_check in hit_faces and len(hit_faces[uv_tuple_check]) > 1:
        # cmds.warning(f"UV Overlap (basit kontrol): {len(hit_faces[uv_tuple_check])} yüzey ({hit_faces[uv_tuple_check]}) UV ({u_coord}, {v_coord}) paylaşıyor.")
        return True
    return False

def get_world_space_at_uv(mesh_shape_name, u_coord, v_coord):
    """
    Belirtilen UV koordinatına karşılık gelen dünya uzayı (world space) koordinatını alır.
    uvPin node'u kullanarak daha güvenilir bir sonuç elde eder.
    """
    if not cmds.objExists(mesh_shape_name):
        cmds.warning(f"Mesh shape '{mesh_shape_name}' bulunamadı.")
        return None

    mesh_transform_name_list = cmds.listRelatives(mesh_shape_name, parent=True, fullPath=True)
    if not mesh_transform_name_list:
        cmds.warning(f"Mesh shape '{mesh_shape_name}' için transform bulunamadı.")
        return None
    mesh_transform_name = mesh_transform_name_list[0]

    uv_pin_node = None
    try:
        uv_pin_node = cmds.createNode("uvPin")
        
        # worldMesh veya outMesh bağlantısı
        if cmds.attributeQuery("worldMesh", node=mesh_shape_name, exists=True) and \
           cmds.attributeQuery("worldMesh[0]", node=mesh_shape_name, exists=True):
            cmds.connectAttr(f"{mesh_shape_name}.worldMesh[0]", f"{uv_pin_node}.deformedGeometry")
        elif cmds.attributeQuery("outMesh", node=mesh_shape_name, exists=True):
             cmds.connectAttr(f"{mesh_shape_name}.outMesh", f"{uv_pin_node}.deformedGeometry")
        else:
            cmds.warning(f"Mesh shape '{mesh_shape_name}' üzerinde uygun bir mesh output attribute bulunamadı (worldMesh[0] veya outMesh).")
            if uv_pin_node and cmds.objExists(uv_pin_node): cmds.delete(uv_pin_node)
            return None

        # uvPin node'una transformun worldMatrix'ini bağla (doğru pozisyon için önemli)
        # 'originalGeometryMatrix' yerine 'inputMatrix' kullanılmalı veya uvPin'in kendi transformu ayarlanmalı.
        # Genellikle worldMatrix[0] -> inputMatrix bağlantısı yapılır.
        if cmds.attributeQuery("inputMatrix", node=uv_pin_node, exists=True):
            cmds.connectAttr(f"{mesh_transform_name}.worldMatrix[0]", f"{uv_pin_node}.inputMatrix")
        else:
            # Alternatif olarak, uvPin nodunun transformunu mesh'in transformuna eşitleyebiliriz
            # veya uvPin'i mesh'e parent edip transformlarını sıfırlayabiliriz.
            # Ancak inputMatrix en temiz yöntemdir. Eğer yoksa, uvPin'in çalışma şekli farklı olabilir.
            # Şimdilik, inputMatrix'in var olduğunu varsayıyoruz. Yoksa, bu bir sorun teşkil edebilir.
            # Maya'nın daha eski sürümlerinde bu attribute olmayabilir veya farklı olabilir.
            # Modern Maya sürümlerinde (örn. 2018+) inputMatrix olmalıdır.
            cmds.warning(f"uvPin node '{uv_pin_node}' üzerinde 'inputMatrix' attribute'u bulunamadı. Dünya pozisyonu yanlış olabilir.")
            # Bu durumda bile devam etmeyi deneyebiliriz, ancak sonuçlar yanıltıcı olabilir.

        cmds.setAttr(f"{uv_pin_node}.coordinate[0].coordinateU", u_coord)
        cmds.setAttr(f"{uv_pin_node}.coordinate[0].coordinateV", v_coord)
        
        matrix_values = cmds.getAttr(f"{uv_pin_node}.outputMatrix[0]")
        world_pos = [matrix_values[12], matrix_values[13], matrix_values[14]]
        
        return om.MPoint(world_pos[0], world_pos[1], world_pos[2])
    except Exception as e:
        cmds.warning(f"Dünya koordinatı (uvPin) alınırken hata: {e}")
        return None
    finally:
        if uv_pin_node and cmds.objExists(uv_pin_node):
            cmds.delete(uv_pin_node)

def create_locator_at_point(point, name_prefix="textureRigger"): # Changed default name_prefix
    """
    Belirtilen dünya uzayı koordinatında bir locator oluşturur.
    
    Args:
        point (om.MPoint): Locator'ın oluşturulacağı dünya uzayı koordinatı.
        name_prefix (str): Locator'ın isim öneki.
    """
    # İsim önekini kontrol et ve boş değilse locator isimlendirmesinde kullan
    locator_name = f"{name_prefix}_locator#" if name_prefix else "textureRigger_locator#" # Changed fallback prefix
    locator = cmds.spaceLocator(name=locator_name)
    cmds.xform(locator[0], translation=(point.x, point.y, point.z), worldSpace=True)
    # cmds.select(locator[0]) # Seçimi ana UI yönetsin
    print(f"Locator '{locator[0]}' oluşturuldu: ({point.x}, {point.y}, {point.z})")
    return locator[0]

def run_step1_logic(name_prefix="textureRigger"): # Changed default name_prefix
    """
    Step 1'in ana mantığını çalıştırır: Mesh seçimi, UV kontrolü ve locator oluşturma.
    
    Args:
        name_prefix (str): Locator ve diğer nesnelerin isim öneki.
    
    Returns:
        tuple: (mesh_transform, mesh_shape, locator_name) veya (None, None, None)
    """
    selected_objects = cmds.ls(selection=True, long=True, type="transform")

    if not selected_objects:
        cmds.warning("Lütfen bir polygon mesh seçin.")
        return None, None, None # 3 değer döndür

    mesh_transform = selected_objects[0]
    shapes = cmds.listRelatives(mesh_transform, shapes=True, fullPath=True, type="mesh")

    if not shapes:
        cmds.warning(f"Seçilen obje '{mesh_transform}' bir polygon mesh değil veya mesh shape'i yok.")
        return None, None, None # 3 değer döndür
    
    mesh_shape = shapes[0]

    uv_to_check_u, uv_to_check_v = 0.5, 0.5
    if check_uv_overlap(mesh_shape, uv_to_check_u, uv_to_check_v):
        cmds.warning(f"UV ({uv_to_check_u}, {uv_to_check_v}) noktasında UV overlapping tespit edildi (veya birden fazla yüzey bulundu). Lütfen UV'leri kontrol edin.")
        return None, None, None # 3 değer döndür

    world_point = get_world_space_at_uv(mesh_shape, uv_to_check_u, uv_to_check_v)
    if world_point:
        locator_name = create_locator_at_point(world_point, name_prefix)
        if locator_name: # create_locator_at_point da None dönebilir (çok olası olmasa da)
            cmds.select(locator_name, replace=True)
            return mesh_transform, mesh_shape, locator_name
        else:
            cmds.warning(f"Locator oluşturulamadı.")
            return None, None, None # 3 değer döndür
    else:
        cmds.warning(f"UV ({uv_to_check_u}, {uv_to_check_v}) noktasında dünya koordinatı alınamadı.")
        return None, None, None # 3 değer döndür

