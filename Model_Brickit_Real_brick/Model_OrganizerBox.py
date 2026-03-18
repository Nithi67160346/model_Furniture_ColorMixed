import plotly.graph_objects as go
import numpy as np
import itertools
from collections import defaultdict

# =========================================================
# 🎨 ตั้งค่าสีและฟังก์ชันส่วนกลาง
# =========================================================
BASE_COLOR = "#FFF4F4"
EDGE_COLOR = "#A78F8F"

def get_btype(dx, dy, dz):
    """ฟังก์ชันจัดระเบียบชื่อบล็อกมาตรฐาน"""
    dims = sorted([int(dx), int(dy), int(dz)])
    return f"brick_{dims[0]}x{dims[1]}x{dims[2]}"

# =========================================================
# 🧠 ระบบปูบล็อกอัจฉริยะ (บังคับใช้เฉพาะ 6 ขนาด)
# =========================================================
def create_pack_block_func(blocks_used_list):
    # กำหนดขนาดที่อนุญาต (Core brick & Beam)
    allowed_base = [
        (2, 2, 2),
        (2, 2, 4),
        (2, 6, 2),
        (2, 8, 2),
        (8, 6, 2),
        (8, 8, 2)
    ]
    
    # คำนวณการหมุนบล็อก 3 มิติ (Permutations) ทุกรูปแบบ
    allowed_permutations = set()
    for b in allowed_base:
        for p in itertools.permutations(b):
            allowed_permutations.add(p)
            
    # เรียงลำดับบล็อกตามปริมาตร (พยายามใช้บล็อกใหญ่สุดก่อน)
    sorted_perms = sorted(list(allowed_permutations), key=lambda x: (-x[0]*x[1]*x[2], -max(x), -min(x)))

    def pack_block(start_x, end_x, start_y, end_y, start_z, target_h):
        dx, dy, dz = end_x - start_x, end_y - start_y, target_h
        if dx <= 0 or dy <= 0 or dz <= 0: return
        
        # สร้างตาราง Voxel จำลองเพื่อเช็คช่องว่าง
        grid = np.zeros((dx, dy, dz), dtype=bool)
        
        for z in range(0, dz, 2):
            for y in range(0, dy, 2):
                for x in range(0, dx, 2):
                    if not grid[x, y, z]: # ถ้าช่องนี้ยังว่างอยู่
                        # ลองใส่บล็อกที่อนุญาตจากใหญ่ไปเล็ก
                        for (bw, bl, bh) in sorted_perms:
                            if x + bw <= dx and y + bl <= dy and z + bh <= dz:
                                # ถ้าใส่แล้วไม่ล้นออกนอกกรอบ และไม่ทับบล็อกอื่น
                                if not np.any(grid[x:x+bw, y:y+bl, z:z+bh]):
                                    # ยึดพื้นที่นี้
                                    grid[x:x+bw, y:y+bl, z:z+bh] = True
                                    
                                    dims = sorted([bw, bl, bh])
                                    btype = f"brick_{dims[0]}x{dims[1]}x{dims[2]}"
                                    
                                    blocks_used_list.append({
                                        'type': btype, 
                                        'color': BASE_COLOR, 
                                        'x': start_x + x, 
                                        'y': start_y + y, 
                                        'z': start_z + z, 
                                        'dx': bw, 'dy': bl, 'dz': bh
                                    })
                                    break
    return pack_block

# =========================================================
# 🔌 ฟังก์ชันสร้าง "กล่องจัดระเบียบสายไฟ (Cable Box)"
# =========================================================
def generate_cable_box(w, l, h):
    blocks_used = []
    pack_block = create_pack_block_func(blocks_used)

    # 1. กำหนดขนาดและปัดให้ลงล็อกเลโก้ (ไซส์ขั้นต่ำ 20x12x10 cm)
    real_w, real_l, real_h = max(20, int(w)), max(12, int(l)), max(10, int(h))
    real_w += real_w % 2; real_l += real_l % 2; real_h += real_h % 2

    thick = 2 # ความหนาของผนังกล่อง

    # --- เริ่มประกอบร่างกล่อง ---

    # 1. แผ่นพื้นกล่อง (Base) - ปิดทึบ
    pack_block(0, real_w, 0, real_l, 0, thick)

    # 2. ผนังหน้า และ ผนังหลัง (Front & Back Walls) - ปิดทึบ
    wall_h = real_h - (thick * 2) # ความสูงของผนัง (ไม่รวมพื้นและฝา)
    pack_block(0, real_w, 0, thick, thick, wall_h) # ผนังหน้า
    pack_block(0, real_w, real_l - thick, real_l, thick, wall_h) # ผนังหลัง

    # 3. ผนังข้าง ซ้าย-ขวา (Side Walls with Slits) - เจาะช่องตรงกลางให้สายเมนลอด
    mid_y = real_l // 2
    mid_y -= mid_y % 2
    slit_w = 4 # ขนาดความกว้างของช่องลอดสายไฟ (4 cm)
    slit_start = mid_y - (slit_w // 2)
    slit_end = mid_y + (slit_w // 2)

    # ผนังซ้าย (แบ่งเป็น 2 ท่อน หน้า-หลัง เพื่อเว้นช่องตรงกลาง)
    pack_block(0, thick, thick, slit_start, thick, wall_h)
    pack_block(0, thick, slit_end, real_l - thick, thick, wall_h)

    # ผนังขวา
    pack_block(real_w - thick, real_w, thick, slit_start, thick, wall_h)
    pack_block(real_w - thick, real_w, slit_end, real_l - thick, thick, wall_h)

    # 4. ฝาปิด (Top Lid) - เว้นร่องยาวด้านหลังให้ดึงสายชาร์จขึ้นมาได้
    gap_size = 2 # ร่องสายไฟกว้าง 2 cm
    lid_end_y = real_l - thick - gap_size
    pack_block(0, real_w, 0, lid_end_y, real_h - thick, thick) # แผ่นฝาหลัก

    # เสริมขอบล็อคซ้าย-ขวา ตรงบริเวณร่องสายไฟ ให้ฝาดูแข็งแรง
    pack_block(0, thick, lid_end_y, real_l - thick, real_h - thick, thick)
    pack_block(real_w - thick, real_w, lid_end_y, real_l - thick, real_h - thick, thick)

    return blocks_used, real_w, real_l, real_h

# =========================================================
# 🎨 ฟังก์ชัน Render 3D
# =========================================================
def render_3d_model(blocks_used, title, width, length, height):
    fig = go.Figure()

    def add_mesh_box(x0, y0, z0, dx, dy, dz, color):
        x = [x0, x0+dx, x0+dx, x0, x0, x0+dx, x0+dx, x0]
        y = [y0, y0, y0+dy, y0+dy, y0, y0, y0+dy, y0+dy]
        z = [z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz]
        i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color=color, opacity=1.0, flatshading=True))

        edges_x, edges_y, edges_z = [], [], []
        for start, end in [(0,1), (1,2), (2,3), (3,0), (4,5), (5,6), (6,7), (7,4), (0,4), (1,5), (2,6), (3,7)]:
            edges_x.extend([x[start], x[end], None])
            edges_y.extend([y[start], y[end], None])
            edges_z.extend([z[start], z[end], None])
        fig.add_trace(go.Scatter3d(x=edges_x, y=edges_y, z=edges_z, mode='lines', line=dict(color=EDGE_COLOR, width=2), hoverinfo='none', showlegend=False))

    type_counter = defaultdict(int)
    for b in blocks_used:
        add_mesh_box(b['x'], b['y'], b['z'], b['dx'], b['dy'], b['dz'], b['color'])
        type_counter[b['type']] += 1

    fig.update_layout(
        title=f"{title} | Size: {width}W x {length}D x {height}H (cm)",
        scene=dict(
            aspectmode='data',
            xaxis=dict(showbackground=False, visible=True, title='Width (cm)'),
            yaxis=dict(showbackground=False, visible=True, title='Depth (cm)'),
            zaxis=dict(showbackground=False, visible=True, title='Height (cm)')
        ),
        paper_bgcolor='white', plot_bgcolor='white', showlegend=False
    )

    print(f"\n===== 📋 BILL OF MATERIALS: {title.upper()} =====")
    total_pieces = 0
    for btype, count in sorted(type_counter.items(), reverse=True):
        print(f"📦 {btype} \t-> \t{count} pieces")
        total_pieces += count
    print(f"✅ Total blocks used: {total_pieces} pieces\n")
    fig.show()

# =========================================================
# 🚀 จุดทดสอบรันการทำงาน (ปรับขนาดตรงนี้ได้เลย)
# =========================================================
def build_cable_box(w=32, l=14, h=14):
    blocks_data, rw, rl, rh = generate_cable_box(w, l, h)
    render_3d_model(blocks_data, "Cable Organizer Box (Strict Bricks)", rw, rl, rh)

# 1. กล่องไซส์มาตรฐาน (เหมาะสำหรับซ่อนปลั๊ก 3-4 ตา)
build_cable_box(w=32, l=14, h=14)

# 2. กล่องไซส์ยาวพิเศษ (เหมาะสำหรับซ่อนปลั๊ก 6 ตายาวๆ)
# build_cable_box(w=48, l=16, h=16)