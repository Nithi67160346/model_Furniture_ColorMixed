import os
import struct
import numpy as np
import plotly.graph_objects as go
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.backends.backend_pdf import PdfPages

# =========================================================
# 🎨 1. ตั้งค่าพื้นฐาน (ไฟล์ STL และ สี)
# =========================================================
BASE_COLOR_PDF = np.array([0.97, 0.90, 0.72]) 
BASE_COLOR_PLOTLY = "#FFF4F4"             
EDGE_COLOR = "#A78F8F" # สีเส้นขอบสำหรับ Plotly 3D

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

# ⚖️ ข้อมูลน้ำหนัก Filament ต่อ 1 ชิ้น (หน่วย: กรัม)
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

# =========================================================
# 🧠 2. ระบบ AI หาแผ่นปูพื้นและเสาโต๊ะ 
# =========================================================
def get_optimal_tiling(length):
    if length == 28:
        return [8, 6, 6, 8]
    for n8 in range(length // 8, -1, -1):
        rem = length - n8 * 8
        if rem % 6 == 0:
            return [8] * n8 + [6] * (rem // 6)
    res, rem = [], length
    for s in [8, 6, 4, 2]:
        res.extend([s] * (rem // s))
        rem %= s
    return res

def get_leg_tiling(length, is_bottom=False):
    res, rem = [], length
    if is_bottom and rem >= 2:
        res.append(2)
        rem -= 2
    while rem >= 4:
        res.append(4)
        rem -= 4
    while rem >= 2:
        res.append(2)
        rem -= 2
    return res

# =========================================================
# 🏗️ 3. อัลกอริทึมประกอบร่างแบบโครงสร้างสมบูรณ์
# =========================================================
def generate_smart_tiled_shelf(w=32, l=20, h=16):
    blocks_used = []

    real_w = max(8, int(w)); real_w += real_w % 2
    real_l = max(8, int(l)); real_l += real_l % 2
    real_h = max(4, int(h)); real_h += real_h % 2

    thickness = 2

    bottom_z = max(2, int(real_h / 4))
    bottom_z -= bottom_z % 2 
    top_z = real_h - thickness

    if real_h <= 8:
        z_levels = [top_z]
    else:
        num_shelves = max(2, int(real_h / 16) + 1)
        if num_shelves == 2:
            z_levels = [bottom_z, top_z]
        else:
            raw_levels = np.linspace(bottom_z, top_z, num_shelves)
            z_levels = [int(round(z / 2.0)) * 2 for z in raw_levels]

    x_legs = [0]
    num_x_spans = max(1, int(real_w / 32))
    step_x = (real_w - 2) / num_x_spans
    
    for i in range(1, num_x_spans):
        pos = int(round(i * step_x / 2.0)) * 2
        x_legs.append(pos)
    x_legs.append(real_w - 2)
    x_legs = sorted(list(set(x_legs)))

    y_legs = [0, real_l - 2]
    leg_positions = [(x, y) for x in x_legs for y in y_legs]

    def get_btype(dx, dy, dz):
        dims = sorted([int(dx), int(dy), int(dz)])
        return f"brick_{dims[0]}x{dims[1]}x{dims[2]}"

    def pack_block(sx, ex, sy, ey, sz, ez, **kwargs):
        dx, dy, dz = ex - sx, ey - sy, ez - sz
        if dx <= 0 or dy <= 0 or dz <= 0: return
        block = {
            'type': get_btype(dx, dy, dz), 'color': BASE_COLOR_PLOTLY,
            'x': sx, 'y': sy, 'z': sz,
            'dx': dx, 'dy': dy, 'dz': dz
        }
        block.update(kwargs)
        blocks_used.append(block)

    def pack_legs(start_z, target_h, is_bottom=False):
        for cx, cy in leg_positions:
            current_z = start_z
            for dz in get_leg_tiling(target_h, is_bottom):
                pack_block(cx, cx+2, cy, cy+2, current_z, current_z+dz)
                current_z += dz

    def pack_shelf(z_level, is_top=False):
        for cx, cy in leg_positions:
            if is_top:
                pack_block(cx, cx+2, cy, cy+2, z_level, z_level+2, is_top_corner=True)
            else:
                pack_block(cx, cx+2, cy, cy+2, z_level, z_level+4, is_middle_corner=True)

        for y in y_legs:
            for i in range(len(x_legs)-1):
                cx = x_legs[i]+2
                for dx in get_optimal_tiling(x_legs[i+1] - cx):
                    pack_block(cx, cx+dx, y, y+2, z_level, z_level+thickness)
                    cx += dx

        for x in x_legs:
            for j in range(len(y_legs)-1):
                cy = y_legs[j]+2
                for dy in get_optimal_tiling(y_legs[j+1] - cy):
                    pack_block(x, x+2, cy, cy+dy, z_level, z_level+thickness)
                    cy += dy

        for i in range(len(x_legs)-1):
            for j in range(len(y_legs)-1):
                start_x, end_x = x_legs[i]+2, x_legs[i+1]
                start_y, end_y = y_legs[j]+2, y_legs[j+1]
                
                cx = start_x
                for dx in get_optimal_tiling(end_x - start_x):
                    cy = start_y
                    for dy in get_optimal_tiling(end_y - start_y):
                        if (dx == 8 and dy == 8) or (dx == 8 and dy == 6) or (dx == 6 and dy == 8):
                            pack_block(cx, cx+dx, cy, cy+dy, z_level, z_level+thickness)
                        else:
                            curr_y = cy
                            while curr_y < cy + dy:
                                pack_block(cx, cx+dx, curr_y, curr_y+2, z_level, z_level+thickness)
                                curr_y += 2
                        cy += dy
                    cx += dx

    num_shelves = len(z_levels)
    for i in range(num_shelves):
        is_top = (i == num_shelves - 1)
        shelf_z = z_levels[i] if is_top else z_levels[i] - 2
        
        pack_shelf(shelf_z, is_top)
        
        if i == 0:
            start_z = 0
            is_bottom = True
        else:
            prev_shelf_z = z_levels[i-1] - 2
            start_z = prev_shelf_z + 4
            is_bottom = False
            
        target_h = shelf_z - start_z
        pack_legs(start_z, target_h, is_bottom)

    return blocks_used, real_w, real_l, real_h

# =========================================================
# ⚙️ 4. กฎเหล็กข้อต่อและหันเดือย (STL Orientation Matrix)
# =========================================================
def R_x(deg):
    th = np.radians(deg)
    return np.round(np.array([[1, 0, 0], [0, np.cos(th), -np.sin(th)], [0, np.sin(th), np.cos(th)]])).astype(int)

def R_y(deg):
    th = np.radians(deg)
    return np.round(np.array([[np.cos(th), 0, np.sin(th)], [0, 1, 0], [-np.sin(th), 0, np.cos(th)]])).astype(int)

def R_z(deg):
    th = np.radians(deg)
    return np.round(np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])).astype(int)

def get_part_info(b, rh, rw, rl):
    dx, dy, dz = b['dx'], b['dy'], b['dz']
    x, y, z = b['x'], b['y'], b['z']
    
    if b.get('part_id'):
        part_id = b['part_id']
    else:
        dims = sorted([dx, dy, dz])
        if dims == [2, 8, 8]: part_id = '10'
        elif dims == [2, 6, 8]: part_id = '09'
        elif dims == [2, 2, 8]: part_id = '08' if x == 0 or x == rw-2 or y == 0 or y == rl-2 else '07'
        elif dims == [2, 2, 6]: part_id = '06' if x == 0 or x == rw-2 or y == 0 or y == rl-2 else '05'
        elif dims == [2, 2, 4]: 
            if b.get('is_middle_corner'): part_id = '04' 
            else:                         part_id = '03'
        elif dims == [2, 2, 2]:
            if b.get('is_top_corner'):    part_id = '02'
            else:                         part_id = '01'
        else: part_id = '01' 

    orig_dims = {
        '01': [2,2,2], '02': [2,2,2], '03': [4,2,2], '04': [4,2,2],
        '05': [6,2,2], '06': [6,2,2], '07': [8,2,2], '08': [8,2,2],
        '09': [6,8,2], '10': [8,8,2] 
    }.get(part_id, [2, 2, 2])

    R = np.eye(3)

    if part_id == '01':
        if z == 0: R = np.eye(3) 
        else:      R = np.eye(3) 
            
    elif part_id == '02':
        flat_top_R = R_x(-180) 
        if x == 0 and y == 0:
            R = R_z(-90) @ flat_top_R
        elif x > 0 and y == 0:
            R = flat_top_R
        elif x == 0 and y > 0:
            R = R_z(180) @ flat_top_R
        else:
            R = R_z(90) @ flat_top_R

    elif dz >= 4 and dx == 2 and dy == 2:
        if x == 0 and y == 0:        
            R = np.array([[0, 0, 1], [0, -1, 0], [1, 0, 0]])     
        elif x > 0 and y == 0:       
            R = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]])    
        elif x == 0 and y > 0:       
            R = np.array([[0, -1, 0], [0, 0, -1], [1, 0, 0]])    
        else:                        
            R = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])   

    elif dz == 2 and dy >= 4 and dx == 2: 
        if x == 0: R = R_z(90)  
        else:      R = R_z(-90) 

    elif dz == 2 and dx >= 4 and dy == 2: 
        if y == 0: R = R_z(180) 
        else:      R = np.eye(3) 
        
    elif dz == 2 and dx >= 6 and dy >= 6:
        if dx != orig_dims[0]: R = R_z(90)
        else:                  R = np.eye(3)

    return part_id, R, orig_dims

# =========================================================
# ⚙️ 5. ฟังก์ชันอ่านและประกอบไฟล์ STL แบบ Zero-Gap
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

def align_stl_body(v_orig, b, rh, rw, rl):
    part_id, R, orig_dims = get_part_info(b, rh, rw, rl)
    b['part_id'] = part_id 
    v_rot = v_orig.copy()
    
    if part_id == '03':
        v_rot += np.array([40, 20, 0])
        v_rot[:, 1:] -= 10
        v_rot = v_rot @ R_x(90).T
        v_rot[:, 1:] += 10
        
    v_rot = v_rot @ R.T
    
    orig_dx, orig_dy, orig_dz = orig_dims
    corners = np.array([
        [0, 0, 0], [orig_dx*10, 0, 0], [0, orig_dy*10, 0], [orig_dx*10, orig_dy*10, 0],
        [0, 0, orig_dz*10], [orig_dx*10, 0, orig_dz*10], [0, orig_dy*10, orig_dz*10], [orig_dx*10, orig_dy*10, orig_dz*10]
    ])
    new_body_min = np.min(corners @ R.T, axis=0)
    
    v_rot -= new_body_min
    v_rot += np.array([b['x']*10, b['y']*10, b['z']*10])
    return v_rot

def build_scene_parts(blocks_used, rh, rw, rl):
    meshes = {pid: load_stl_mesh(fname) for pid, fname in STL_FILES.items()}
    scene_parts, type_counter = [], defaultdict(int)

    for b in blocks_used:
        temp_id, _, _ = get_part_info(b, rh, rw, rl)
        if temp_id not in meshes or meshes[temp_id] is None: continue
        
        v_orig = meshes[temp_id]
        matched_rv = align_stl_body(v_orig, b, rh, rw, rl)
        scene_parts.append((matched_rv, b['part_id']))
        type_counter[b['part_id']] += 1

    return scene_parts, type_counter

# =========================================================
# 🚀 6. ฟังก์ชันเรนเดอร์ STL 3D Plotly (🔥เพิ่ม Edge ของ Bounding Box)
# =========================================================
def render_3d_with_plotly(scene_parts, blocks_used, title, width, length, height):
    print("⏳ กำลังเรนเดอร์ 3D STL (Plotly)...")
    fig = go.Figure()
    
    all_x, all_y, all_z, all_i, all_j, all_k = [], [], [], [], [], []
    offset = 0
    
    # 1. รวบรวมข้อมูลโมเดล 3D แบบทึบ
    for v_rot, _ in scene_parts:
        all_x.extend(v_rot[:, 0])
        all_y.extend(v_rot[:, 1])
        all_z.extend(v_rot[:, 2])
        
        num_tri = v_rot.shape[0] // 3
        all_i.extend(np.arange(0, 3*num_tri, 3) + offset)
        all_j.extend(np.arange(1, 3*num_tri, 3) + offset)
        all_k.extend(np.arange(2, 3*num_tri, 3) + offset)
        offset += v_rot.shape[0]
        
    if all_x:
        fig.add_trace(go.Mesh3d(x=all_x, y=all_y, z=all_z, i=all_i, j=all_j, k=all_k, color=BASE_COLOR_PLOTLY, flatshading=True, name='Bricks'))
        
    # 🔥 2. สร้างเส้นขอบ (Edge) เฉพาะเหลี่ยมมุมของแต่ละชิ้นส่วน
    edge_x, edge_y, edge_z = [], [], []
    for b in blocks_used:
        xmin, xmax = b['x']*10, (b['x']+b['dx'])*10
        ymin, ymax = b['y']*10, (b['y']+b['dy'])*10
        zmin, zmax = b['z']*10, (b['z']+b['dz'])*10
        
        # กรอบล่าง
        edge_x.extend([xmin, xmax, None, xmax, xmax, None, xmax, xmin, None, xmin, xmin, None])
        edge_y.extend([ymin, ymin, None, ymin, ymax, None, ymax, ymax, None, ymax, ymin, None])
        edge_z.extend([zmin, zmin, None, zmin, zmin, None, zmin, zmin, None, zmin, zmin, None])
        
        # กรอบบน
        edge_x.extend([xmin, xmax, None, xmax, xmax, None, xmax, xmin, None, xmin, xmin, None])
        edge_y.extend([ymin, ymin, None, ymin, ymax, None, ymax, ymax, None, ymax, ymin, None])
        edge_z.extend([zmax, zmax, None, zmax, zmax, None, zmax, zmax, None, zmax, zmax, None])
        
        # เสาแนวตั้ง 4 มุม
        edge_x.extend([xmin, xmin, None, xmax, xmax, None, xmax, xmax, None, xmin, xmin, None])
        edge_y.extend([ymin, ymin, None, ymin, ymin, None, ymax, ymax, None, ymax, ymax, None])
        edge_z.extend([zmin, zmax, None, zmin, zmax, None, zmin, zmax, None, zmin, zmax, None])

    fig.add_trace(go.Scatter3d(x=edge_x, y=edge_y, z=edge_z, mode='lines', line=dict(color=EDGE_COLOR, width=2.5), hoverinfo='none', name='Edges'))
    
    fig.update_layout(title=f"{title} | Size: {width}W x {length}D x {height}H", scene=dict(aspectmode='data'), showlegend=False)
    fig.show()

# =========================================================
# 📄 7. ฟังก์ชันพิมพ์ Report เป็นไฟล์ PDF (ไม่มีเส้นขอบ)
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
        
        if isinstance(base_color, str):
            rgb = mcolors.to_rgb(base_color)
        else:
            rgb = base_color
            
        face_colors.append(np.array([rgb[0]*shade, rgb[1]*shade, rgb[2]*shade, alpha_value]))
        
    ax.add_collection3d(Poly3DCollection(poly3d, facecolors=face_colors, edgecolor='none'))

def export_assembly_guide_pdf(scene_parts, type_counter, filename="Brickit_Assembly_Manual.pdf", cols=2, rows=2):
    if not scene_parts: return
    
    all_verts = np.vstack([p[0] for p in scene_parts])
    max_range = (all_verts.max(axis=0) - all_verts.min(axis=0)).max() / 2.0
    mid = all_verts.mean(axis=0)
    light_dir = np.array([0.5, 0.5, 1.0]) / np.linalg.norm([0.5, 0.5, 1.0])
    per_page = rows * cols
    
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    block_color_map = {pid: color_cycle[idx % len(color_cycle)] for idx, pid in enumerate(sorted(type_counter.keys()))}

    print(f"\n📖 กำลังสร้าง PDF Report: {filename} ... โปรดรอสักครู่")
    with PdfPages(filename) as pdf:
        
        # --- 1. Assembly Steps ---
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
                
                part_name = STL_FILES[scene_parts[hi][1]].split('/')[-1]
                ax.set_title(f"Step {hi + 1}\nAdd: {part_name}", fontsize=10)
                ax.set_axis_off()
                
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
            
        # --- 2. BILL OF MATERIALS (BOM) & ESTIMATED WEIGHT ---
        print("📸 กำลังเรนเดอร์หน้า Bill of Materials แบบ 3D...")
        unique_pids = sorted(type_counter.keys())
        num_items = len(unique_pids)
        bom_cols = 2
        bom_rows = int(np.ceil(num_items / bom_cols))
        
        fig = plt.figure(figsize=(bom_cols * 5, bom_rows * 4.5))
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
                
            ax.set_title(f"{part_name}\n>>> Qty: {count} pcs | Weight: {item_total_weight:.2f} g <<<", fontsize=11, fontweight='bold', color='#333333')
            ax.set_axis_off()
            
        plt.tight_layout(rect=[0, 0.05, 1, 0.93]) 
        
        footer_text = f"TOTAL PARTS: {total_pcs} pcs   |   TOTAL ESTIMATED FILAMENT: {total_weight:.2f} g"
        fig.text(0.5, 0.02, footer_text, ha='center', fontsize=14, fontweight='bold', family='monospace', color='red')
        
        pdf.savefig(fig)
        plt.close(fig)

# =========================================================
# 📊 8. ฟังก์ชัน Print สรุปข้อมูลลง Console
# =========================================================
def print_bom_summary(type_counter):
    print("\n" + "="*50)
    print("📊 BILL OF MATERIALS SUMMARY (Console Report)")
    print("="*50)
    
    total_pcs = 0
    total_weight = 0.0
    
    print(f"{'PART NAME':<45} | {'QTY':<5} | {'WEIGHT (g)'}")
    print("-" * 70)
    
    for pid in sorted(type_counter.keys()):
        count = type_counter[pid]
        part_name = STL_FILES[pid].split('/')[-1]
        unit_weight = PART_WEIGHTS.get(pid, 0.0)
        item_total_weight = count * unit_weight
        
        total_pcs += count
        total_weight += item_total_weight
        
        print(f"📦 {part_name:<42} | {count:>3}   | {item_total_weight:>8.2f} g")
        
    print("=" * 70)
    print(f"🎯 TOTAL PARTS REQUIRED:    {total_pcs} pieces")
    print(f"⚖️  TOTAL FILAMENT WEIGHT:   {total_weight:.2f} grams")
    print("=" * 70 + "\n")

# =========================================================
# 🎮 ตัวควบคุมขนาด (DIMENSION CONTROLLER)
# =========================================================
def build_custom_model(w, l, h):
    blocks_data, new_w, new_l, new_h = generate_smart_tiled_shelf(w, l, h)
    scene_parts, type_counter = build_scene_parts(blocks_data, new_h, new_w, new_l)
    
    if scene_parts:
        title_text = f"Ultimate BRICKIT Furniture Assembly"
        
        # 1. Print สรุป BOM ออกทางหน้าจอ
        print_bom_summary(type_counter)
        
        # 2. เรนเดอร์จอ 3D Plotly (ส่ง blocks_data ไปเพื่อวาดขอบ)
        render_3d_with_plotly(scene_parts, blocks_data, title_text, new_w, new_l, new_h)
        
        # 3. สร้าง Report PDF (คู่มือประกอบ)
        export_assembly_guide_pdf(scene_parts, type_counter, filename="Brickit_Assembly_Manual.pdf")
    else:
        print("⚠️ ไม่พบไฟล์ STL ในโฟลเดอร์ กรุณาตรวจสอบพาร์ทไฟล์!")

# ---------------------------------------------------------
# 🚀 รันการทำงาน
# ---------------------------------------------------------
build_custom_model(w=32, l=20, h=16)