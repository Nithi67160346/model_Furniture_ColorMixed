import os
import struct
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import plotly.graph_objects as go
from collections import defaultdict
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.backends.backend_pdf import PdfPages

# =========================================================
# 🎨 1. ตั้งค่าพื้นฐาน (ไฟล์ STL, สี และน้ำหนัก)
# =========================================================
BASE_COLOR_PDF = np.array([0.97, 0.90, 0.72]) 
BASE_COLOR = "#FFF4F4"                

STL_FILES = {
    '01': 'STL/BRICKIT_01_corebrick_2x2x2_connector.stl',
    '02': 'STL/BRICKIT_02_corebrick_2x2x2_adapter.stl',
    '03': 'STL/BRICKIT_03_corebrick_2x2x4_1.stl',
    '04': 'STL/BRICKIT_04_corebrick_2x2x4_2_2adapter.stl',
    '05': 'STL/BRICKIT_05_Beam_2x6x2_connector.stl',
    '06': 'STL/BRICKIT_06_Beam_2x6x2_adapter.stl',
    '07': 'STL/BRICKIT_07_Beam_2x8x2_connecttor.stl',
    '08': 'STL/BRICKIT_08_Beam_2x8x2_adapter.stl',
    '09': 'STL/BRICKIT_09_Beam_8x6x2.stl',
    '10': 'STL/BRICKIT_10_Beam_8x8x2.stl'
}

# ⚖️ ข้อมูลน้ำหนัก Filament ต่อ 1 ชิ้น (หน่วย: กรัม) จากการคำนวณ
PART_WEIGHTS = {
    '01': 4.39,
    '02': 6.17,
    '03': 8.70,
    '04': 9.76,
    '05': 12.79,
    '06': 13.22,
    '07': 16.14,
    '08': 16.57,
    '09': 40.45,
    '10': 51.24
}

def get_btype(dx, dy, dz):
    dims = sorted([int(dx), int(dy), int(dz)])
    return f"brick_{dims[0]}x{dims[1]}x{dims[2]}"

# =========================================================
# 🧠 2. ระบบปูบล็อก (จัดโครงสร้างตู้รองเท้า)
# =========================================================
def create_pack_block_func(blocks_used_list, has_walls):
    if has_walls:
        allowed_shapes = [
            (8, 8, 2), (8, 6, 2), (6, 8, 2), 
            (2, 8, 8), (8, 2, 8), (2, 6, 8), (6, 2, 8), 
            (8, 2, 2), (2, 8, 2), (6, 2, 2), (2, 6, 2), 
            (2, 2, 8), (2, 2, 6),           
            (2, 2, 4), (2, 2, 2)            
        ]
    else:
        allowed_shapes = [
            (8, 8, 2), (8, 6, 2), (6, 8, 2), 
            (2, 8, 8), (8, 2, 8), (2, 6, 8), (6, 2, 8), 
            (8, 2, 2), (2, 8, 2), (6, 2, 2), (2, 6, 2), 
            (2, 2, 4), (2, 2, 2)            
        ]

    sorted_shapes = sorted(allowed_shapes, key=lambda x: (-x[0]*x[1]*x[2], -max(x)))

    def pack_block(start_x, end_x, start_y, end_y, start_z, target_h):
        dx, dy, dz = end_x - start_x, end_y - start_y, target_h
        if dx <= 0 or dy <= 0 or dz <= 0: return
        grid = np.zeros((dx, dy, dz), dtype=bool)
        for z in range(0, dz, 2):
            for y in range(0, dy, 2):
                for x in range(0, dx, 2):
                    if not grid[x, y, z]: 
                        for (bw, bl, bh) in sorted_shapes:
                            if x + bw <= dx and y + bl <= dy and z + bh <= dz:
                                if not np.any(grid[x:x+bw, y:y+bl, z:z+bh]):
                                    grid[x:x+bw, y:y+bl, z:z+bh] = True
                                    dims = sorted([bw, bl, bh])
                                    blocks_used_list.append({
                                        'type': f"brick_{dims[0]}x{dims[1]}x{dims[2]}", 
                                        'x': start_x + x, 'y': start_y + y, 'z': start_z + z, 
                                        'dx': bw, 'dy': bl, 'dz': bh, 'part_id': '' 
                                    })
                                    break
    return pack_block

def assign_specific_stl_parts(blocks_used, z_levels):
    max_x = max([b['x'] for b in blocks_used]) if blocks_used else 0
    max_y = max([b['y'] for b in blocks_used]) if blocks_used else 0
    
    for b in blocks_used:
        dims = sorted([b['dx'], b['dy'], b['dz']])
        if dims == [2, 8, 8]: b['part_id'] = '10'
        elif dims == [2, 6, 8]: b['part_id'] = '09'
        elif dims == [2, 2, 8]: b['part_id'] = '08' if b['x'] == 0 or b['y'] == 0 else '07'
        elif dims == [2, 2, 6]: b['part_id'] = '06' if b['x'] == 0 or b['y'] == 0 else '05'
        elif dims == [2, 2, 4]: b['part_id'] = '03' 
        elif dims == [2, 2, 2]: 
            is_bottom_corner = (b['z'] == 0) and (b['x'] == 0 or b['x'] == max_x) and (b['y'] == 0 or b['y'] == max_y)
            if is_bottom_corner: b['part_id'] = '01'
            else:                b['part_id'] = '02'

def generate_shoe_rack(w=80, l=32, h=96, has_walls=False):
    blocks_used = []
    pack_block = create_pack_block_func(blocks_used, has_walls)
    
    num_w, num_l = max(2, int(w) // 8), max(2, int(l) // 8)
    x_pillars = [0, 2 + (num_w // 2)*8, 4 + num_w*8] if num_w >= 8 else [0, 2 + num_w*8]
    y_pillars = [0, 2 + num_l*8]
    
    real_w, real_l = x_pillars[-1] + 2, y_pillars[-1] + 2
    step_z = 16 
    z_levels = list(range(6, (int(h) // 2) * 2, step_z + 2))
    real_h = z_levels[-1] + 2 

    def build_floor_layer(zl):
        for px in x_pillars:
            for py in y_pillars: pack_block(px, px+2, py, py+2, zl, 2)
        for py in y_pillars:
            for i in range(len(x_pillars)-1): pack_block(x_pillars[i]+2, x_pillars[i+1], py, py+2, zl, 2)
        for px in x_pillars:
            for j in range(len(y_pillars)-1): pack_block(px, px+2, y_pillars[j]+2, y_pillars[j+1], zl, 2)
        for i in range(len(x_pillars)-1):
            for j in range(len(y_pillars)-1): pack_block(x_pillars[i]+2, x_pillars[i+1], y_pillars[j]+2, y_pillars[j+1], zl, 2)

    for zl in z_levels: build_floor_layer(zl)
    
    for px in x_pillars:
        for py in y_pillars:
            pack_block(px, px+2, py, py+2, 0, 2) 
            z = 2
            while z < z_levels[0]:
                pack_block(px, px+2, py, py+2, z, 4 if z + 4 <= z_levels[0] else 2)
                z += 4 if z + 4 <= z_levels[0] else 2
                    
            for k in range(len(z_levels) - 1):   
                pack_block(px, px+2, py, py+2, z_levels[k] + 2, z_levels[k+1] - (z_levels[k] + 2))

    if has_walls:
        for k in range(len(z_levels) - 1):
            sz, ez = z_levels[k] + 2, z_levels[k+1]
            for j in range(len(y_pillars)-1): 
                pack_block(0, 2, y_pillars[j]+2, y_pillars[j+1], sz, ez - sz)               
                pack_block(x_pillars[-1], x_pillars[-1]+2, y_pillars[j]+2, y_pillars[j+1], sz, ez - sz) 
            for i in range(len(x_pillars)-1): 
                pack_block(x_pillars[i]+2, x_pillars[i+1], y_pillars[-1], y_pillars[-1]+2, sz, ez - sz) 

    assign_specific_stl_parts(blocks_used, z_levels)
    return blocks_used, real_w, real_l, real_h

# =========================================================
# 🚀 3. ระบบโหลดไฟล์ STL 
# =========================================================
def load_stl_mesh(filename):
    if not os.path.exists(filename): return None
    with open(filename, 'rb') as f:
        f.read(80) 
        num_triangles = struct.unpack('<I', f.read(4))[0]
        verts = []
        for _ in range(num_triangles):
            f.read(12) 
            verts.extend(struct.unpack('<3f', f.read(12)))
            verts.extend(struct.unpack('<3f', f.read(12)))
            verts.extend(struct.unpack('<3f', f.read(12)))
            f.read(2)
    return np.array(verts).reshape(-1, 3)

# =========================================================
# 🔥 4. กฎเหล็ก 3 มิติ (THE ULTIMATE HARDCODED MATRIX) 🔥
# =========================================================
def get_part_info(b, rh):
    dx, dy, dz = b['dx'], b['dy'], b['dz']
    x, y, z = b['x'], b['y'], b['z']
    part_id = b['part_id']
    
    orig_dims = {
        '01': [2,2,2], '02': [2,2,2], '03': [4,2,2], '04': [4,2,2],
        '05': [6,2,2], '06': [6,2,2], '07': [8,2,2], '08': [8,2,2],
        '09': [8,6,2], '10': [8,8,2]
    }.get(part_id, [2, 2, 2])

    R = np.eye(3)

    if dx == 2 and dy == 2 and dz == 2 and part_id in ['01', '02']:
        is_top = (z + dz >= rh) 
        if is_top:
            if x == 0 and y == 0:     R = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]])   
            elif x > 0 and y == 0:    R = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])  
            elif x == 0 and y > 0:    R = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]])  
            else:                     R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])   
        else:
            if x == 0 and y == 0:     R = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]])  
            elif x > 0 and y == 0:    R = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]])   
            elif x == 0 and y > 0:    R = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])   
            else:                     R = np.eye(3)                                      

    elif dz >= 6 and dx == 2 and dy == 2:
        if y == 0: R = np.array([[0, 0, -1], [0, -1, 0], [-1, 0, 0]])
        else:      R = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])   

    elif dz >= 4 and dx == 2 and dy == 2:
        if y == 0: R = np.array([[0, -1, 0], [0, 0, 1], [-1, 0, 0]])  
        else:      R = np.array([[0, 1, 0], [0, 0, -1], [-1, 0, 0]])  

    elif dz == 2 and dy > 2 and dx == 2:
        if x == 0: R = np.array([[0, -1, 0], [-1, 0, 0], [0, 0, -1]])
        else:      R = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]])

    elif dz == 2 and dx > 2 and dy == 2:
        if y == 0: R = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]]) 
        else:      R = np.eye(3)

    elif dy == 2 and dz > 2: 
        R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
    elif dx == 2 and dz > 2: 
        if x == 0: R = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]])  
        else:      R = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]])

    elif dz == 2 and dx > 2 and dy > 2:
        if dx != orig_dims[0]: R = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])

    return part_id, R, orig_dims

def align_stl_body(v_orig, b, rh):
    part_id, R, orig_dims = get_part_info(b, rh)
    b['part_id'] = part_id 
    v = v_orig.copy()
    
    if part_id == '03': v += np.array([40, 20, 0]) 
        
    v_rot = v @ R.T
    
    orig_dx, orig_dy, orig_dz = orig_dims
    corners = np.array([
        [0, 0, 0], [orig_dx*10, 0, 0], [0, orig_dy*10, 0], [orig_dx*10, orig_dy*10, 0],
        [0, 0, orig_dz*10], [orig_dx*10, 0, orig_dz*10], [0, orig_dy*10, orig_dz*10], [orig_dx*10, orig_dy*10, orig_dz*10]
    ])
    new_body_min = np.min(corners @ R.T, axis=0)
    
    v_rot -= new_body_min
    v_rot += np.array([b['x']*10, b['y']*10, b['z']*10])
    return v_rot

# =========================================================
# ⚙️ 5. ฟังก์ชันจัดเรียงโมเดล และเรนเดอร์ 3D
# =========================================================
def build_scene_parts(blocks_used, rh):
    meshes = {}
    for part_id, fname in STL_FILES.items():
        v = load_stl_mesh(fname)
        if v is not None: meshes[part_id] = v

    scene_parts = []
    type_counter = defaultdict(int)

    for b in blocks_used:
        if b['part_id'] not in meshes: continue
        
        v_orig = meshes[b['part_id']]
        matched_rv = align_stl_body(v_orig, b, rh)
        
        scene_parts.append((matched_rv, b['part_id']))
        type_counter[b['part_id']] += 1

    return scene_parts, type_counter

def render_3d_with_plotly(scene_parts, title, width, length, height):
    print("⏳ กำลังเรนเดอร์ 3D (Plotly)...")
    fig = go.Figure()
    all_verts = [p[0] for p in scene_parts]
    if all_verts:
        final_v = np.vstack(all_verts)
        num_tri = final_v.shape[0] // 3
        i = np.arange(0, 3*num_tri, 3)
        j = np.arange(1, 3*num_tri, 3)
        k = np.arange(2, 3*num_tri, 3)
        fig.add_trace(go.Mesh3d(x=final_v[:,0], y=final_v[:,1], z=final_v[:,2], i=i, j=j, k=k, color=BASE_COLOR_PLOTLY, flatshading=True))
    fig.update_layout(title=f"{title} | Size: {width}W x {length}D x {height}H", scene=dict(aspectmode='data'))
    fig.show()

# =========================================================
# 📄 6. โหลด STL และสร้าง PDF (รวมน้ำหนัก Filament)
# =========================================================
def draw_stl_on_axis(ax, vertices, base_color, alpha_value, light_dir):
    poly3d, face_colors = [], []
    for i in range(0, len(vertices), 3):
        v0, v1, v2 = vertices[i], vertices[i+1], vertices[i+2]
        poly3d.append([v0, v1, v2])
        normal = np.cross(v1 - v0, v2 - v0)
        norm_length = np.linalg.norm(normal)
        if norm_length > 0: normal = normal / norm_length
        intensity = max(np.dot(normal, light_dir), 0)
        shade = 0.4 + 0.6 * intensity
        rgb = mcolors.to_rgb(base_color)
        face_colors.append(np.array([rgb[0]*shade, rgb[1]*shade, rgb[2]*shade, alpha_value]))
    ax.add_collection3d(Poly3DCollection(poly3d, facecolors=face_colors, edgecolor='none'))

def export_assembly_guide_pdf(scene_parts, type_counter, filename="ShoeRack_Manual.pdf", cols=2, rows=2):
    if not scene_parts: return
    all_verts = np.vstack([p[0] for p in scene_parts])
    max_range = (all_verts.max(axis=0) - all_verts.min(axis=0)).max() / 2.0
    mid = all_verts.mean(axis=0)
    light_dir = np.array([0.5, 0.5, 1.0]) / np.linalg.norm([0.5, 0.5, 1.0])
    per_page = rows * cols
    
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    block_color_map = {pid: color_cycle[idx % len(color_cycle)] for idx, pid in enumerate(sorted(type_counter.keys()))}

    print(f"\n📖 สร้าง PDF: {filename} ...")
    with PdfPages(filename) as pdf:
        
        # --- ส่วนที่ 1: ขั้นตอนการประกอบ ---
        for start in range(0, len(scene_parts), per_page):
            fig = plt.figure(figsize=(cols * 5, rows * 5))
            for idx in range(per_page):
                hi = start + idx
                if hi >= len(scene_parts): break
                ax = fig.add_subplot(rows, cols, idx + 1, projection='3d')
                for i, (v, pid) in enumerate(scene_parts):
                    if i > hi: continue 
                    alpha = 1.0 if i == hi else 0.2
                    draw_color = block_color_map[pid] if i == hi else BASE_COLOR_PDF
                    draw_stl_on_axis(ax, v, draw_color, alpha, light_dir)
                ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
                ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
                ax.set_zlim(mid[2] - max_range, mid[2] + max_range)
                ax.set_box_aspect([1,1,1])
                ax.set_title(f"Step {hi + 1}\nAdd: {STL_FILES[scene_parts[hi][1]].replace('STL/','')}", fontsize=10)
                ax.set_axis_off()
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
            
        # --- ส่วนที่ 2: BILL OF MATERIALS (BOM) แบบ 3D พร้อมการคำนวณน้ำหนัก ---
        print("📸 กำลังเรนเดอร์หน้า Bill of Materials แบบ 3D...")
        unique_pids = sorted(type_counter.keys())
        num_items = len(unique_pids)
        bom_cols = 2
        bom_rows = int(np.ceil(num_items / bom_cols))
        
        fig = plt.figure(figsize=(bom_cols * 5, bom_rows * 4))
        fig.suptitle("BILL OF MATERIALS\n" + "="*40, fontsize=18, fontweight='bold', family='monospace')
        
        total_pcs = 0
        total_weight = 0.0
        
        for idx, pid in enumerate(unique_pids):
            count = type_counter[pid]
            part_name = STL_FILES[pid].split('/')[-1]
            unit_weight = PART_WEIGHTS.get(pid, 0.0)
            item_total_weight = count * unit_weight
            
            total_pcs += count
            total_weight += item_total_weight
            
            ax = fig.add_subplot(bom_rows, bom_cols, idx + 1, projection='3d')
            v = load_stl_mesh(STL_FILES[pid])
            if v is not None:
                v_center = v - v.mean(axis=0)
                item_max_range = (v_center.max(axis=0) - v_center.min(axis=0)).max() / 2.0 * 1.2
                draw_color = block_color_map[pid]
                draw_stl_on_axis(ax, v_center, draw_color, 1.0, light_dir)
                
                ax.set_xlim(-item_max_range, item_max_range)
                ax.set_ylim(-item_max_range, item_max_range)
                ax.set_zlim(-item_max_range, item_max_range)
                ax.set_box_aspect([1,1,1])
            
            title_str = f"{part_name}\n>>> Qty: {count} pcs | Weight: {item_total_weight:.2f} g <<<"
            ax.set_title(title_str, fontsize=10, fontweight='bold', color='#333333')
            ax.set_axis_off()
            
        plt.tight_layout(rect=[0, 0.05, 1, 0.95]) 
        
        footer_text = f"TOTAL PARTS: {total_pcs} pcs   |   ESTIMATED FILAMENT: {total_weight:.2f} g"
        fig.text(0.5, 0.02, footer_text, ha='center', fontsize=13, fontweight='bold', family='monospace', color='red')
        
        pdf.savefig(fig)
        plt.close(fig)

# =========================================================
# 📊 7. ฟังก์ชัน Print สรุปข้อมูลลง Console
# =========================================================
def print_bom_summary(type_counter):
    print("\n" + "="*60)
    print("📊 BILL OF MATERIALS SUMMARY")
    print("="*60)
    
    total_pcs = 0
    total_weight = 0.0
    
    print(f"{'PART NAME':<40} | {'QTY':<5} | {'WEIGHT (g)'}")
    print("-" * 60)
    
    for pid in sorted(type_counter.keys()):
        count = type_counter[pid]
        part_name = STL_FILES[pid].split('/')[-1]
        unit_weight = PART_WEIGHTS.get(pid, 0.0)
        item_total_weight = count * unit_weight
        
        total_pcs += count
        total_weight += item_total_weight
        
        print(f"📦 {part_name:<37} | {count:>3}   | {item_total_weight:>8.2f} g")
        
    print("=" * 60)
    print(f"🎯 TOTAL PARTS REQUIRED:    {total_pcs} pieces")
    print(f"⚖️  TOTAL FILAMENT WEIGHT:   {total_weight:.2f} grams")
    print("=" * 60 + "\n")

# =========================================================
# 🎮 จุดทดสอบการเรียกใช้งาน 
# =========================================================
def build_furniture():
    blocks_data, rw, rl, rh = generate_shoe_rack(w=16, l=16, h=46, has_walls=False)
    scene_parts, type_counter = build_scene_parts(blocks_data, rh)
    
    if scene_parts:
        # 1. Print สรุป BOM ออกหน้าจอ
        print_bom_summary(type_counter)
        
        # 2. เรนเดอร์ 3D
        render_3d_with_plotly(scene_parts, "Perfect Shoe Rack", rw, rl, rh)
        
        # 3. สร้าง PDF
        export_assembly_guide_pdf(scene_parts, type_counter, filename="ShoeRack_Flawless_Manual.pdf")
    else:
        print("⚠️ ไม่พบไฟล์ STL ในโฟลเดอร์ กรุณาตรวจสอบพาร์ทไฟล์!")

build_furniture()