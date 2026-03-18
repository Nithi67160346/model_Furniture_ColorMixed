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
# 📱 10. แท่นวางโทรศัพท์/แท็บเล็ต (สมมาตรเป๊ะ + พนักพิงเดิม)
# =========================================================
def generate_device_stand(w, l, h):
    blocks_used = []
    
    # ใช้งานระบบปูบล็อกตัวใหม่ที่จำกัดขนาดไว้
    pack_block = create_pack_block_func(blocks_used)

    # 1. กำหนดขนาดและปัดให้ลงล็อกเลโก้ (ไซส์ขั้นต่ำ 10x10x10 cm)
    real_w = max(10, int(w)); real_w += real_w % 2
    real_l = max(10, int(l)); real_l += real_l % 2
    real_h = max(10, int(h)); real_h += real_h % 2

    thick = 2 # ความหนาแผ่นฐาน

    # --- เริ่มประกอบร่างแท่นวาง ---

    # 🔥 คำนวณระยะซ้าย-ขวา ให้สมมาตรกันเป๊ะๆ ฝั่งละ 1 ชิ้นเท่ากัน
    side_width = (real_w - 4) // 2
    side_width -= side_width % 2
    if side_width < 2: side_width = 2

    hole_start = side_width
    hole_end = real_w - side_width

    gap_y = 4 # ระยะความลึกของช่องวางอุปกรณ์ (เว้นไว้ 4cm)

    # 1. แผ่นฐาน (Base) - ด้านหลังเป็นแผ่นทึบแบบดั้งเดิม
    pack_block(0, hole_start, 0, gap_y, 0, thick)   # ฐานหน้าซ้าย
    pack_block(hole_end, real_w, 0, gap_y, 0, thick) # ฐานหน้าขวา
    pack_block(0, real_w, gap_y, real_l, 0, thick)  # ฐานด้านหลัง (ทึบยาว)

    # 2. ขอบกั้นกันตกด้านหน้า (Front Lip) - ขวา 1 ชิ้น ซ้าย 1 ชิ้น สมมาตร
    pack_block(0, hole_start, 0, 2, thick, 2)
    pack_block(hole_end, real_w, 0, 2, thick, 2)

    # 3. พนักพิงหลังแบบไล่ระดับ (Stepped Backrest) - เอาแบบดั้งเดิม แผ่นทึบเต็ม
    steps = (real_l - gap_y) // 2
    if steps < 1: steps = 1

    available_h = real_h - thick
    step_h = available_h // steps
    step_h -= step_h % 2
    if step_h <= 0: step_h = 2

    current_z = thick
    for i in range(steps):
        y_start = gap_y + (i * 2)
        y_end = real_l
        h_step = step_h

        # ขั้นสุดท้ายให้เก็บความสูงที่เหลือทั้งหมด
        if i == steps - 1:
            h_step = real_h - current_z
            h_step -= h_step % 2

        if h_step > 0 and y_start < y_end:
            # ปูเป็นแผ่นเดียวเต็มๆ ไม่ผ่ากลาง
            pack_block(0, real_w, y_start, y_end, current_z, h_step)
            current_z += h_step

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
# 🚀 จุดทดสอบรันการทำงาน
# =========================================================
def build_device_stand(w=10, l=12, h=14):
    blocks_data, rw, rl, rh = generate_device_stand(w, l, h)
    render_3d_model(blocks_data, "Phone/Tablet Stand (Strict Blocks)", rw, rl, rh)

# ลองรันดูครับ ขวา-ซ้าย จะมี 1 ชิ้นเท่ากันเป๊ะ!
build_device_stand(w=10, l=12, h=14)