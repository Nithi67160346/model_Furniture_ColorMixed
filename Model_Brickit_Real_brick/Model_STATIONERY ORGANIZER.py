import plotly.graph_objects as go
import numpy as np
import itertools
from collections import defaultdict

# =========================================================
# 🎨 ตั้งค่าพื้นฐาน
# =========================================================
BASE_COLOR = "#FFF4F4"
EDGE_COLOR = "#A78F8F"

def get_btype(dx, dy, dz):
    """จัดเรียงชื่อบล็อกมาตรฐาน"""
    dims = sorted([int(dx), int(dy), int(dz)])
    return f"brick_{dims[0]}x{dims[1]}x{dims[2]}"

# =========================================================
# 🧠 ระบบปูบล็อกอัจฉริยะ (สอดขอบ 100%)
# =========================================================
def create_pack_block_func(blocks_used_list):
    allowed_shapes = [
        (8, 8, 2), (8, 6, 2), (6, 8, 2), # แผ่นพื้น
        (2, 8, 8), (8, 2, 8), (2, 6, 8), (6, 2, 8), # แผ่นผนัง (จับตั้ง)
        (8, 2, 2), (2, 8, 2), (6, 2, 2), (2, 6, 2), # คาน
        (2, 2, 8), (2, 2, 6),           # เสา
        (2, 2, 4), (2, 2, 2)            # ข้อต่อ
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
                                        'color': BASE_COLOR, 
                                        'x': start_x + x, 'y': start_y + y, 'z': start_z + z, 
                                        'dx': bw, 'dy': bl, 'dz': bh
                                    })
                                    break
    return pack_block

# =========================================================
# ✏️ 11. ที่จัดระเบียบเครื่องเขียน (Stationery Organizer) - ฉบับ Grid 
# =========================================================
def generate_stationery_organizer(w=20, l=16, h=14):
    blocks_used = []
    pack_block = create_pack_block_func(blocks_used)
    
    # 🌟 คำนวณตาราง Grid:
    # ความกว้าง w=20 -> จะถูกแบ่งเป็น 2 ช่อง คือช่อง 8 และช่อง 6
    if w <= 20: x_cells = [8, 6]
    else: x_cells = [8, 8, 8] # ถ้า w=32 จะได้ 3 ช่อง
    
    # ความลึก l=16 -> จะถูกแบ่งเป็นช่องหน้า (ความลึก 8) และช่องหลัง (ความลึก 2 สำหรับไม้บรรทัด)
    y_cells = [8, 2]
    
    # หาพิกัดเสาตามแกน X และ Y
    x_pillars = [0]
    for c in x_cells: x_pillars.append(x_pillars[-1] + c + 2)
    y_pillars = [0]
    for c in y_cells: y_pillars.append(y_pillars[-1] + c + 2)
    
    real_w = x_pillars[-1] + 2
    real_l = y_pillars[-1] + 2
    real_h = (int(h) // 2) * 2
    
    # คำนวณความสูงแบบไล่ระดับ (ช่องหลังสูง, ช่องหน้าเตี้ย)
    back_h = real_h - 2
    front_h = max(4, real_h // 2)
    if front_h % 2 != 0: front_h += 1

    # --- 1. 🏗️ สร้างแผ่นฐาน (Base Plate) ที่ z=0 ---
    # เสาข้อต่อ 2x2
    for px in x_pillars:
        for py in y_pillars:
            blocks_used.append({'type': 'brick_2x2x2', 'color': BASE_COLOR, 'x': px, 'y': py, 'z': 0, 'dx': 2, 'dy': 2, 'dz': 2})
    # คานแนวนอน-แนวตั้ง
    for py in y_pillars:
        for i in range(len(x_pillars)-1):
            pack_block(x_pillars[i]+2, x_pillars[i+1], py, py+2, 0, 2)
    for px in x_pillars:
        for j in range(len(y_pillars)-1):
            pack_block(px, px+2, y_pillars[j]+2, y_pillars[j+1], 0, 2)
    # แผ่นพื้นสอดกลาง
    for i in range(len(x_pillars)-1):
        for j in range(len(y_pillars)-1):
            pack_block(x_pillars[i]+2, x_pillars[i+1], y_pillars[j]+2, y_pillars[j+1], 0, 2)

    # --- 2. 🧱 สร้างเสา (Pillars) ---
    def build_pillar(x, y, sz, ez):
        pack_block(x, x+2, y, y+2, sz, ez - sz)

    for px in x_pillars:
        for py in y_pillars:
            # เสาโซนหน้าสุด
            if py < y_pillars[-1]:
                build_pillar(px, py, 2, 2 + front_h)
            # เสาโซนหลังสุด
            if py == y_pillars[-1]:
                build_pillar(px, py, 2, 2 + back_h)
            # เสากั้นกลาง (ต้องต่อความสูงจากโซนหน้า ขึ้นไปเท่าโซนหลัง)
            if py == y_pillars[1]:
                build_pillar(px, py, 2 + front_h, 2 + back_h)

    # --- 3. 🚪 สร้างผนังกั้นช่อง (Walls) ---
    # โซนด้านหลัง (ช่องไม้บรรทัด สูง back_h)
    py_mid = y_pillars[1]
    py_back = y_pillars[-1]
    for i in range(len(x_pillars)-1):
        pack_block(x_pillars[i]+2, x_pillars[i+1], py_back, py_back+2, 2, back_h) # ผนังหลังสุด
        pack_block(x_pillars[i]+2, x_pillars[i+1], py_mid, py_mid+2, 2, back_h)   # ผนังกลาง (แนวนอน)
    for px in [0, x_pillars[-1]]:
        pack_block(px, px+2, py_mid+2, py_back, 2, back_h)                        # ผนังข้างโซนหลัง
        
    # โซนด้านหน้า (ช่องใส่ปากกา เตี้ยกว่า สูง front_h)
    py_front = y_pillars[0]
    for i in range(len(x_pillars)-1):
        pack_block(x_pillars[i]+2, x_pillars[i+1], py_front, py_front+2, 2, front_h) # ผนังหน้าสุด
    for px in x_pillars:
        pack_block(px, px+2, py_front+2, py_mid, 2, front_h)                         # ผนังข้าง+กั้นกลาง โซนหน้า

    return blocks_used, real_w, real_l, real_h

# =========================================================
# 🎨 ฟังก์ชัน Render 3D อเนกประสงค์
# =========================================================
def render_3d_model(blocks_used, title, width, length, height):
    fig = go.Figure()
    def add_mesh_box(b):
        x0, y0, z0, dx, dy, dz = b['x'], b['y'], b['z'], b['dx'], b['dy'], b['dz']
        x, y, z = [x0, x0+dx, x0+dx, x0, x0, x0+dx, x0+dx, x0], [y0, y0, y0+dy, y0+dy, y0, y0, y0+dy, y0+dy], [z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz]
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6], color=b['color'], flatshading=True))
        edges_x, edges_y, edges_z = [], [], []
        for s, e in [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]:
            edges_x.extend([x[s], x[e], None]); edges_y.extend([y[s], y[e], None]); edges_z.extend([z[s], z[e], None])
        fig.add_trace(go.Scatter3d(x=edges_x, y=edges_y, z=edges_z, mode='lines', line=dict(color=EDGE_COLOR, width=2), showlegend=False))

    type_counter = defaultdict(int)
    for b in blocks_used:
        add_mesh_box(b)
        type_counter[b['type']] += 1

    fig.update_layout(title=f"{title} | Size: {width}W x {length}D x {height}H (cm)", scene=dict(aspectmode='data'))
    
    print(f"\n===== 📋 BILL OF MATERIALS: {title.upper()} =====")
    for btype, count in sorted(type_counter.items(), reverse=True): print(f"📦 {btype} \t-> \t{count} pieces")
    print(f"✅ Total blocks: {sum(type_counter.values())} pieces\n")
    fig.show()

def build_stationery_organizer(w=20, l=16, h=14):
    blocks_data, rw, rl, rh = generate_stationery_organizer(w, l, h)
    render_3d_model(blocks_data, "Stationery Organizer", rw, rl, rh)

# =========================================================
# 🚀 จุดทดสอบรันการทำงาน
# =========================================================
build_stationery_organizer(w=20, l=16, h=14)