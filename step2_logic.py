import maya.cmds as cmds
import maya.OpenMaya as om

def get_uv_at_point(mesh_shape, world_point_mvector):
    """
    Verilen bir dünya uzayı noktasına en yakın UV koordinatını mesh üzerinde bulur.

    Args:
        mesh_shape (str): Mesh shape düğümünün adı.
        world_point_mvector (om.MVector): Dünya uzayındaki nokta.

    Returns:
        tuple (float, float) or None: (u, v) UV koordinatları veya bulunamazsa None.
    """
    selection_list = om.MSelectionList()
    try:
        selection_list.add(mesh_shape)
    except RuntimeError:
        cmds.warning(f"Mesh shape '{mesh_shape}' seçilemedi.")
        return None

    dag_path = om.MDagPath()
    try:
        selection_list.getDagPath(0, dag_path)
    except RuntimeError:
        cmds.warning(f"Mesh shape '{mesh_shape}' için DAG path alınamadı.")
        return None

    # MPoint olarak dünya noktasını oluştur - Bu satır gereksiz çünkü world_point_mvector zaten kullanılıyor.
    # world_m_point = om.MPoint(world_point_mvector.x, world_point_mvector.y, world_point_mvector.z)

    cpos_node = None # Hata durumunda silinebilmesi için tanımla
    try:
        # En güvenilir yöntemlerden biri, `closestPointOnMesh` node'unu kullanmaktır.
        cpos_node = cmds.createNode("closestPointOnMesh")
        
        # Mesh bağlantısı
        mesh_attr_to_connect = ""
        if cmds.attributeQuery("worldMesh", node=mesh_shape, exists=True) and \
           cmds.attributeQuery("worldMesh[0]", node=mesh_shape, exists=True):
            mesh_attr_to_connect = f"{mesh_shape}.worldMesh[0]"
        elif cmds.attributeQuery("outMesh", node=mesh_shape, exists=True):
            mesh_attr_to_connect = f"{mesh_shape}.outMesh"
        else:
            cmds.warning(f"Mesh shape '{mesh_shape}' üzerinde uygun bir mesh output attribute bulunamadı (worldMesh[0] veya outMesh).")
            if cpos_node and cmds.objExists(cpos_node): cmds.delete(cpos_node)
            return None
            
        cmds.connectAttr(mesh_attr_to_connect, f"{cpos_node}.inMesh")
        
        cmds.setAttr(f"{cpos_node}.inPositionX", world_point_mvector.x)
        cmds.setAttr(f"{cpos_node}.inPositionY", world_point_mvector.y)
        cmds.setAttr(f"{cpos_node}.inPositionZ", world_point_mvector.z)
        
        u_val = cmds.getAttr(f"{cpos_node}.result.parameterU")
        v_val = cmds.getAttr(f"{cpos_node}.result.parameterV")
        
        if u_val is not None and v_val is not None:
            return float(u_val), float(v_val)
        else:
            cmds.warning(f"closestPointOnMesh node'u ile UV koordinatları alınamadı.")
            return None

    except Exception as e:
        cmds.warning(f"Dünya noktasından UV alınırken hata: {e}")
        return None
    finally:
        if cpos_node and cmds.objExists(cpos_node):
            cmds.delete(cpos_node)

def create_follicle_at_uv(mesh_shape_name, u_coord, v_coord, name_prefix="textureRigger"):
    """
    Belirtilen mesh üzerinde, verilen UV koordinatlarında bir follicle ve içinde bir null group oluşturur.
    
    Args:
        mesh_shape_name (str): Mesh shape düğümünün adı.
        u_coord (float): U koordinatı.
        v_coord (float): V koordinatı.
        name_prefix (str, optional): Follicle için isim öneki. Defaults to "textureRigger".
    
    Returns:
        tuple: (follicle_transform_name, parent_group_name) veya (None, None)
    """
    if not cmds.objExists(mesh_shape_name):
        cmds.warning(f"Follicle oluşturmak için mesh shape '{mesh_shape_name}' bulunamadı.")
        return None, None

    # İsim önekini temizle ve kullan
    clean_prefix = name_prefix if name_prefix else "textureRigger"
    follicle_name = f"{clean_prefix}_follicle#"

    # Follicle shape ve transform oluştur
    follicle_transform_name = cmds.createNode("transform", name=follicle_name)
    follicle_shape_name = cmds.createNode("follicle", name=f"{follicle_transform_name}Shape", parent=follicle_transform_name)

    # Mesh bağlantıları
    # Mesh'in worldMesh veya outMesh attribute'unu follicle'ın inputMesh'ine bağla
    if cmds.attributeQuery("worldMesh", node=mesh_shape_name, exists=True) and \
       cmds.attributeQuery("worldMesh[0]", node=mesh_shape_name, exists=True):
        cmds.connectAttr(f"{mesh_shape_name}.worldMesh[0]", f"{follicle_shape_name}.inputMesh")
    elif cmds.attributeQuery("outMesh", node=mesh_shape_name, exists=True):
        cmds.connectAttr(f"{mesh_shape_name}.outMesh", f"{follicle_shape_name}.inputMesh")
    else:
        cmds.warning(f"Mesh '{mesh_shape_name}' üzerinde follicle için uygun output attribute bulunamadı.")
        cmds.delete(follicle_transform_name)
        return None, None

    # Mesh'in worldMatrix'ini follicle'ın inputWorldMatrix'ine bağla
    mesh_transform_name = cmds.listRelatives(mesh_shape_name, parent=True, fullPath=True)[0]
    cmds.connectAttr(f"{mesh_transform_name}.worldMatrix[0]", f"{follicle_shape_name}.inputWorldMatrix")

    # Follicle'ın outTranslate ve outRotate'ını transform node'una bağla
    cmds.connectAttr(f"{follicle_shape_name}.outTranslate", f"{follicle_transform_name}.translate")
    cmds.connectAttr(f"{follicle_shape_name}.outRotate", f"{follicle_transform_name}.rotate")

    # UV değerlerini ayarla
    cmds.setAttr(f"{follicle_shape_name}.parameterU", u_coord)
    cmds.setAttr(f"{follicle_shape_name}.parameterV", v_coord)

    # Follicle içinde "parent_grp" adında bir boş grup (null group) oluştur
    parent_grp_name = cmds.group(empty=True, name=f"{clean_prefix}_parent_grp#")
    cmds.parent(parent_grp_name, follicle_transform_name)
    # Grubu sıfırla (follicle'a göre)
    cmds.setAttr(f"{parent_grp_name}.translate", 0, 0, 0)
    cmds.setAttr(f"{parent_grp_name}.rotate", 0, 0, 0)
    cmds.setAttr(f"{parent_grp_name}.scale", 1, 1, 1)

    print(f"Follicle '{follicle_transform_name}' ve parent group '{parent_grp_name}' UV ({u_coord}, {v_coord}) üzerinde oluşturuldu.")
    return follicle_transform_name, parent_grp_name

def setup_follicle_connections(follicle_transform, follicle_shape, node_prefix):
    """
    Follicle için gelişmiş bağlantılar ve kontrolör oluşturur.
    
    Args:
        follicle_transform (str): Follicle transform düğümünün adı.
        follicle_shape (str): Follicle shape düğümünün adı.
        node_prefix (str): İçeride oluşturulacak düğümler için kullanılacak isim öneki.
    
    Returns:
        tuple: (slide_ctrl_name, bind_joint_name) başarılı olursa, aksi halde (None, None)
    """
    try:
        # Node isimlerini düzenli hale getir
        # base_name = follicle_transform.split('|')[-1].split(':')[-1]  # Namespace'siz ve tam yolsuz isim
        # if not base_name: 
        #     base_name = "follicleSetup"
        #     print(f"Geçerli bir isim bulunamadı, varsayılan isim kullanılıyor: {base_name}")
        base_name = node_prefix # Gelen öneki doğrudan kullan

        compose_matrix_node = cmds.createNode("composeMatrix", name=f"{base_name}_compMat")
        mult_matrix_node = cmds.createNode("multMatrix", name=f"{base_name}_multMat")
        decompose_matrix_node = cmds.createNode("decomposeMatrix", name=f"{base_name}_decomMat")

        cmds.connectAttr(f"{follicle_shape}.outRotate", f"{compose_matrix_node}.inputRotate", force=True)
        cmds.connectAttr(f"{follicle_shape}.outTranslate", f"{compose_matrix_node}.inputTranslate", force=True)
        cmds.connectAttr(f"{compose_matrix_node}.outputMatrix", f"{mult_matrix_node}.matrixIn[0]", force=True)
        cmds.connectAttr(f"{follicle_transform}.parentInverseMatrix[0]", f"{mult_matrix_node}.matrixIn[1]", force=True)
        cmds.connectAttr(f"{mult_matrix_node}.matrixSum", f"{decompose_matrix_node}.inputMatrix", force=True)

        # Translate ve rotate kilitlerini aç
        for attr_comp in ["translate", "rotate"]:
            for axis in ["X", "Y", "Z"]:
                attr_full_name = f"{follicle_transform}.{attr_comp}{axis}"
                if cmds.getAttr(attr_full_name, lock=True):
                    cmds.setAttr(attr_full_name, lock=False)

        # Mevcut bağlantıları kaldır
        if cmds.isConnected(f"{follicle_shape}.outTranslate", f"{follicle_transform}.translate"):
            cmds.disconnectAttr(f"{follicle_shape}.outTranslate", f"{follicle_transform}.translate")
        if cmds.isConnected(f"{follicle_shape}.outRotate", f"{follicle_transform}.rotate"):
            cmds.disconnectAttr(f"{follicle_shape}.outRotate", f"{follicle_transform}.rotate")

        cmds.connectAttr(f"{decompose_matrix_node}.outputTranslate", f"{follicle_transform}.translate", force=True)
        cmds.connectAttr(f"{decompose_matrix_node}.outputRotate", f"{follicle_transform}.rotate", force=True)

        position_grp = cmds.group(empty=True, name=f"{base_name}_position_grp", parent=follicle_transform)
        invert_grp = cmds.group(empty=True, name=f"{base_name}_Invert_grp", parent=position_grp)
        slide_ctrl_result = cmds.circle(name=f"{base_name}_Slide_ctrl", normal=(0, 1, 0), radius=1)
        
        if not slide_ctrl_result:
            cmds.warning("Slide_ctrl oluşturma başarısız.")
            return None, None
            
        slide_ctrl = slide_ctrl_result[0]
        cmds.parent(slide_ctrl, invert_grp)

        cmds.addAttr(slide_ctrl, longName="Precision", attributeType="float", defaultValue=0.8)
        cmds.setAttr(f"{slide_ctrl}.Precision", keyable=True)

        translate_invert_node = cmds.createNode("multiplyDivide", name=f"{base_name}_Translate_Invert")
        cmds.setAttr(f"{translate_invert_node}.input2X", -1)
        cmds.setAttr(f"{translate_invert_node}.input2Y", -1)
        cmds.setAttr(f"{translate_invert_node}.input2Z", -1)
        cmds.connectAttr(f"{slide_ctrl}.translate", f"{translate_invert_node}.input1", force=True)
        cmds.connectAttr(f"{translate_invert_node}.output", f"{invert_grp}.translate", force=True)

        invert_v_node = cmds.createNode("multDoubleLinear", name=f"{base_name}_Invert_V")
        invert_u_node = cmds.createNode("multDoubleLinear", name=f"{base_name}_Invert_U")
        cmds.connectAttr(f"{slide_ctrl}.translateX", f"{invert_v_node}.input1", force=True)
        cmds.connectAttr(f"{slide_ctrl}.translateY", f"{invert_u_node}.input1", force=True)
        cmds.setAttr(f"{invert_v_node}.input2", 1)
        cmds.setAttr(f"{invert_u_node}.input2", 1)

        precision_v_node = cmds.createNode("multDoubleLinear", name=f"{base_name}_Precision_V")
        precision_u_node = cmds.createNode("multDoubleLinear", name=f"{base_name}_Precision_U")
        cmds.connectAttr(f"{invert_v_node}.output", f"{precision_v_node}.input1", force=True)
        cmds.connectAttr(f"{invert_u_node}.output", f"{precision_u_node}.input1", force=True)
        cmds.connectAttr(f"{slide_ctrl}.Precision", f"{precision_v_node}.input2", force=True)
        cmds.connectAttr(f"{slide_ctrl}.Precision", f"{precision_u_node}.input2", force=True)

        pos_v_node = cmds.createNode("addDoubleLinear", name=f"{base_name}_pos_U_driver")  # U için
        pos_u_node = cmds.createNode("addDoubleLinear", name=f"{base_name}_pos_V_driver")  # V için
        cmds.connectAttr(f"{precision_v_node}.output", f"{pos_v_node}.input1", force=True)
        cmds.connectAttr(f"{precision_u_node}.output", f"{pos_u_node}.input1", force=True)

        # Follicle shape'in mevcut UV değerlerini al
        param_u = cmds.getAttr(f"{follicle_shape}.parameterU")
        param_v = cmds.getAttr(f"{follicle_shape}.parameterV")

        # AddDoubleLinear input2 değerlerini ayarla (mevcut UV pozisyonları)
        cmds.setAttr(f"{pos_v_node}.input2", param_u)
        cmds.setAttr(f"{pos_u_node}.input2", param_v)

        clamp_node = cmds.createNode("clamp", name=f"{base_name}_clamp")
        cmds.connectAttr(f"{pos_v_node}.output", f"{clamp_node}.inputR", force=True)  # U için inputR
        cmds.connectAttr(f"{pos_u_node}.output", f"{clamp_node}.inputG", force=True)  # V için inputG
        cmds.setAttr(f"{clamp_node}.minR", 0)
        cmds.setAttr(f"{clamp_node}.minG", 0)
        cmds.setAttr(f"{clamp_node}.minB", 0)
        cmds.setAttr(f"{clamp_node}.maxR", 1)
        cmds.setAttr(f"{clamp_node}.maxG", 1)
        cmds.setAttr(f"{clamp_node}.maxB", 1)
        cmds.connectAttr(f"{clamp_node}.outputR", f"{follicle_shape}.parameterU", force=True)
        cmds.connectAttr(f"{clamp_node}.outputG", f"{follicle_shape}.parameterV", force=True)

        cmds.setAttr(f"{slide_ctrl}.translate", 0, 0, 0, type="double3")
        cmds.setAttr(f"{slide_ctrl}.rotate", 0, 0, 0, type="double3")
        cmds.makeIdentity(slide_ctrl, apply=True, translate=True, rotate=True, scale=False)

        cmds.setAttr(f"{position_grp}.rotateZ", 180)
        cmds.setAttr(f"{position_grp}.translateZ", 0)
        cmds.setAttr(f"{position_grp}.scale", 1, 1, 1, type="double3")

        bind_joint_result = cmds.joint(name=f"{base_name}_bind")
        if not bind_joint_result:
            cmds.warning("Bind joint oluşturma başarısız.")
            bind_joint = None
        else:
            bind_joint = bind_joint_result
            if isinstance(bind_joint_result, list):
                bind_joint = bind_joint_result[0]
                
            cmds.setAttr(f"{bind_joint}.drawStyle", 2)
            cmds.parent(bind_joint, slide_ctrl)
            cmds.setAttr(f"{bind_joint}.translate", 0, 0, 0, type="double3")
            cmds.setAttr(f"{bind_joint}.rotate", 0, 0, 0, type="double3")
            cmds.setAttr(f"{bind_joint}.jointOrient", 0, 0, 0, type="double3")

        curve_obj_shape_list = cmds.listRelatives(slide_ctrl, shapes=True, type="nurbsCurve", fullPath=True)
        if not curve_obj_shape_list:
            print(f"Slide_ctrl '{slide_ctrl}' altında NURBS curve shape bulunamadı. CV manipülasyonu atlanıyor.")
        else:
            curve_obj_shape = curve_obj_shape_list[0]
            cv_list = cmds.ls(f"{curve_obj_shape}.cv[*]", flatten=True)
            
            # Curve merkezini bul
            try:
                curve_transform = cmds.listRelatives(curve_obj_shape, parent=True, fullPath=True)[0]
                curve_center = cmds.objectCenter(curve_transform, gl=True)
            except:
                # objectCenter başarısız olursa manual hesapla
                bb = cmds.exactWorldBoundingBox(slide_ctrl)
                curve_center = [(bb[0]+bb[3])/2, (bb[1]+bb[4])/2, (bb[2]+bb[5])/2]

            # CV'leri küçült
            for cv in cv_list:
                cv_pos = cmds.pointPosition(cv, world=True)
                new_pos = [
                    (cv_pos[0] - curve_center[0]) * 0.15 + curve_center[0],
                    (cv_pos[1] - curve_center[1]) * 0.15 + curve_center[1],
                    (cv_pos[2] - curve_center[2]) * 0.15 + curve_center[2]
                ]
                cmds.xform(cv, worldSpace=True, translation=new_pos)
            
            # CV'leri rotate et
            cmds.rotate(90, 0, 0, f"{curve_obj_shape}.cv[*]", relative=True, objectSpace=True)
            cmds.move(0, 0, 0.02, f"{curve_obj_shape}.cv[*]", relative=True, objectSpace=True, worldSpaceDistance=True)
            print("Curve CV manipülasyonu başarıyla uygulandı.")

        print(f"Gelişmiş follicle setup '{follicle_transform}' için uygulandı.")
        return slide_ctrl, bind_joint
        
    except Exception as e:
        cmds.warning(f"Gelişmiş follicle bağlantıları oluşturulurken hata: {e}")
        return None, None

def run_step2_logic(mesh_shape_name, locator_name, name_prefix="textureRigger"):
    """
    Step 2'nin ana mantığını çalıştırır: Locator pozisyonundan UV al, follicle oluştur
    ve gelişmiş follicle bağlantılarını uygula.
    
    Args:
        mesh_shape_name (str): Mesh shape düğümünün adı.
        locator_name (str): Locator transform düğümünün adı.
        name_prefix (str, optional): Oluşturulacak nesnelerin isim öneki. Defaults to "textureRigger".
    
    Returns:
        tuple: (follicle_transform_name, slide_ctrl_name) veya (None, None)
    """
    if not mesh_shape_name or not cmds.objExists(mesh_shape_name):
        cmds.warning("Step 2 için geçerli bir mesh shape adı sağlanmadı veya mesh bulunamadı.")
        return None, None
    if not locator_name or not cmds.objExists(locator_name):
        cmds.warning("Step 2 için geçerli bir locator adı sağlanmadı veya locator bulunamadı.")
        return None, None

    # Locator'ın dünya uzayı pozisyonunu al
    locator_pos_list = cmds.xform(locator_name, query=True, translation=True, worldSpace=True)
    if not locator_pos_list or len(locator_pos_list) != 3:
        cmds.warning(f"Locator '{locator_name}' pozisyonu alınamadı.")
        return None, None
    
    locator_world_point = om.MVector(locator_pos_list[0], locator_pos_list[1], locator_pos_list[2])

    # Bu dünya pozisyonuna karşılık gelen UV'yi mesh üzerinde bul
    uv_coords = get_uv_at_point(mesh_shape_name, locator_world_point)

    actual_prefix = name_prefix if name_prefix else "uv"

    if uv_coords:
        u, v = uv_coords
        print(f"Locator pozisyonuna karşılık gelen UV: ({u}, {v})")
        
        # 1. Follicle ve parent_grp oluştur
        follicle_transform, initial_parent_group = create_follicle_at_uv(mesh_shape_name, u, v, name_prefix) # Pass original name_prefix for follicle creation
        if follicle_transform and initial_parent_group:
            follicle_shape_list = cmds.listRelatives(follicle_transform, shapes=True, type="follicle", fullPath=True)
            if not follicle_shape_list:
                cmds.warning(f"Follicle transform '{follicle_transform}' için follicle shape bulunamadı.")
                # Oluşturulanları temizle
                if cmds.objExists(follicle_transform): cmds.delete(follicle_transform)
                return None, None
            
            follicle_shape = follicle_shape_list[0]
            
            # 2. Gelişmiş follicle bağlantılarını uygula
            slide_ctrl, bind_joint = setup_follicle_connections(follicle_transform, follicle_shape, actual_prefix) # Pass actual_prefix for internal nodes
            
            if slide_ctrl:
                # Eğer parent_grp artık kullanılmıyorsa silinebilir
                if initial_parent_group and cmds.objExists(initial_parent_group):
                    cmds.delete(initial_parent_group)
                    print(f"İlk oluşturulan parent_grp '{initial_parent_group}' silindi.")
                
                # Slide kontrol objesini seç
                cmds.select(slide_ctrl, replace=True)
                return follicle_transform, slide_ctrl
            else:
                # Gelişmiş setup başarısız olursa, temel follicle ve parent_grp ile devam et
                cmds.select(follicle_transform, replace=True)
                return follicle_transform, initial_parent_group
        else:
            cmds.warning("Follicle ve parent group oluşturulamadı.")
            return None, None
    else:
        cmds.warning(f"Locator pozisyonu için mesh '{mesh_shape_name}' üzerinde UV koordinatı bulunamadı.")
        return None, None

