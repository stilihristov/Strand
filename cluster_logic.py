import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import math
import random

# --- CONFIGURATION ---
GRID_UNIT = 3.75
HOLE_RATIO = 0.25
DENSITY_LIMIT = 0.85

# --- LIGHTING CONFIGURATION ---
LIGHT_DIAMETER = 0.5
LIGHT_SPACING = 1.875

# Ratios determine how many PROD units follow a CLUSTER
UNIT_RATIOS = {'gather': 1, 'living': 3, 'prod': 15}
AREAS = {'gather': (800, 1050), 'living': (300, 600), 'prod': (20, 200)}

# --- CLUSTER SETTINGS ---
LIVING_MIN = 3
LIVING_MAX = 5

class Block:
    def __init__(self, gx, gy, gw, gh, b_type, attach_side=None, parent=None):
        self.gx = int(gx); self.gy = int(gy)
        self.gw = int(gw); self.gh = int(gh)
        self.type = b_type
        self.attach_side = attach_side
        self.parent = parent

        self.min_x = self.gx; self.max_x = self.gx + self.gw
        self.min_y = self.gy; self.max_y = self.gy + self.gh

    def get_outer_crv(self):
        x = self.gx * GRID_UNIT; y = self.gy * GRID_UNIT
        w = self.gw * GRID_UNIT; h = self.gh * GRID_UNIT
        return rg.Rectangle3d(rg.Plane.WorldXY, rg.Point3d(x,y,0), rg.Point3d(x+w,y+h,0)).ToNurbsCurve()

    def get_tunnel_crv(self):
        if self.attach_side is None: return None

        target_block = self
        side = self.attach_side

        # LOGIC: Living units cut into the Gathering Hub (Parent)
        if self.type == 'living':
            if self.parent is None: return None
            target_block = self.parent
            tx, ty, tw, th = 0,0,0,0

            # Tunnel logic shifting into parent
            if side == 0: tx = self.gx; ty = self.gy + self.gh; tw = self.gw; th = 1
            elif side == 1: tx = self.gx - 1; ty = self.gy; tw = 1; th = self.gh
            elif side == 2: tx = self.gx; ty = self.gy - 1; tw = self.gw; th = 1
            elif side == 3: tx = self.gx + self.gw; ty = self.gy; tw = 1; th = self.gh

        else:
            # Standard logic for Prod/Gather connecting to things
            tx, ty, tw, th = 0,0,0,0
            if side == 0: tx = self.gx; ty = self.gy + self.gh - 1; tw = self.gw; th = 1
            elif side == 1: tx = self.gx; ty = self.gy; tw = 1; th = self.gh
            elif side == 2: tx = self.gx; ty = self.gy; tw = self.gw; th = 1
            elif side == 3: tx = self.gx + self.gw - 1; ty = self.gy; tw = 1; th = self.gh

        x = tx * GRID_UNIT; y = ty * GRID_UNIT
        w = tw * GRID_UNIT; h = th * GRID_UNIT
        return rg.Rectangle3d(rg.Plane.WorldXY, rg.Point3d(x,y,0), rg.Point3d(x+w,y+h,0)).ToNurbsCurve()

def check_overlap(new_b, existing_blocks):
    for e in existing_blocks:
        if (new_b.max_x <= e.min_x or new_b.min_x >= e.max_x or new_b.max_y <= e.min_y or new_b.min_y >= e.max_y): continue
        else: return True
    return False

def get_grid_dims(u_type):
    target_area = random.uniform(*AREAS[u_type]); aspect = random.uniform(0.6, 1.5)
    w_m = math.sqrt(target_area * aspect); h_m = target_area / w_m
    gw = max(1, int(round(w_m / GRID_UNIT))); gh = max(1, int(round(h_m / GRID_UNIT)))
    if random.random() > 0.5: gw, gh = gh, gw
    return gw, gh

def get_anchors_with_sides(parent, child_w, child_h):
    anchors = []
    anchors.append((parent.max_x, parent.max_y - child_h, 1))
    anchors.append((parent.max_x, parent.min_y, 1))
    anchors.append((parent.min_x - child_w, parent.max_y - child_h, 3))
    anchors.append((parent.min_x - child_w, parent.min_y, 3))
    anchors.append((parent.min_x, parent.max_y, 2))
    anchors.append((parent.max_x - child_w, parent.max_y, 2))
    anchors.append((parent.min_x, parent.min_y - child_h, 0))
    anchors.append((parent.max_x - child_w, parent.min_y - child_h, 0))
    return anchors

def generate_cluster_queue():
    queue = []
    queue.append('gather')
    num_living = random.randint(LIVING_MIN, LIVING_MAX)
    for i in range(num_living): queue.append('living')
    cluster_weight = num_living + 1
    prod_weight = UNIT_RATIOS['prod'] / float(UNIT_RATIOS['living'] + UNIT_RATIOS['gather'])
    num_prod = int(round(cluster_weight * prod_weight))
    num_prod = int(num_prod * random.uniform(0.8, 1.2))
    for i in range(num_prod): queue.append('prod')
    return queue

# --- UPDATED FUNCTION: LIGHTS INSET BY 3.75m ---
def generate_light_matrix(block):
    # 1. FILTER: Only allow Living and Gather
    if block.type not in ['living', 'gather']: return []

    lights = []

    # Dimensions
    w_m = block.gw * GRID_UNIT
    h_m = block.gh * GRID_UNIT
    start_x = block.gx * GRID_UNIT
    start_y = block.gy * GRID_UNIT

    # Grid Calculations
    # LIGHT_SPACING is 1.875m
    cols = int(w_m / LIGHT_SPACING)
    rows = int(h_m / LIGHT_SPACING)

    # Center the grid
    margin_x = (w_m - (cols * LIGHT_SPACING)) / 2.0
    margin_y = (h_m - (rows * LIGHT_SPACING)) / 2.0
    radius = LIGHT_DIAMETER / 2.0

    # 3.75m / 1.875m = 2. So we want the lights at Index 2.
    OFFSET_IDX = 1

    # Safety: If room is too small to have a ring at index 2, return empty
    # We need at least 5 cells (0,1,2,3,4) to have a ring at 2 with space in middle
    if cols <= (OFFSET_IDX * 2) or rows <= (OFFSET_IDX * 2):
        return []

    for i in range(cols):
        for j in range(rows):

            # Identify the target ring indices
            # Left/Right boundaries
            on_x_ring = (i == OFFSET_IDX or i == cols - 1 - OFFSET_IDX)
            # Top/Bottom boundaries
            on_y_ring = (j == OFFSET_IDX or j == rows - 1 - OFFSET_IDX)

            # Identify the valid ranges (to ensure corners connect and we don't draw lines extending out)
            in_x_range = (i >= OFFSET_IDX and i <= cols - 1 - OFFSET_IDX)
            in_y_range = (j >= OFFSET_IDX and j <= rows - 1 - OFFSET_IDX)

            # Logic:
            # 1. Be on the X-ring AND within the Y-limits
            # 2. OR be on the Y-ring AND within the X-limits
            is_valid_perimeter = (on_x_ring and in_y_range) or (on_y_ring and in_x_range)

            if is_valid_perimeter:
                cx = start_x + margin_x + (i * LIGHT_SPACING) + (LIGHT_SPACING / 2.0)
                cy = start_y + margin_y + (j * LIGHT_SPACING) + (LIGHT_SPACING / 2.0)

                center = rg.Point3d(cx, cy, 0)
                circle = rg.Circle(rg.Plane.WorldXY, center, radius).ToNurbsCurve()
                lights.append(circle)

    return lights

def main():
    if not 'reset' in globals() or not reset: return [], [], [], [], [], [], [], [], []
    if not 'boundary' in globals() or not boundary: return [], [], [], [], [], [], [], [], []

    random.seed(int(seed))
    boundary_geo = rs.coercecurve(boundary)
    boundary_area = rg.AreaMassProperties.Compute(boundary_geo).Area
    target_fill = boundary_area * DENSITY_LIMIT

    placed_blocks = []
    current_area_m = 0

    build_queue = []
    current_hub = None

    bbox = boundary_geo.GetBoundingBox(True)
    start_gx = int(bbox.Center.X / GRID_UNIT); start_gy = int(bbox.Center.Y / GRID_UNIT)
    seed_w, seed_h = get_grid_dims('prod')
    first_block = Block(start_gx, start_gy, seed_w, seed_h, 'prod', None, None)

    seed_crv = first_block.get_outer_crv()
    if boundary_geo.Contains(seed_crv.GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Inside:
        placed_blocks.append(first_block)
        current_area_m += (seed_w * GRID_UNIT * seed_h * GRID_UNIT)
    else: return [], [], [], [], [], [], [], [], []

    fails = 0

    while current_area_m < target_fill and fails < 200:
        if len(build_queue) == 0:
            build_queue = generate_cluster_queue()
            current_hub = None

        u_type = build_queue[0]
        gw, gh = get_grid_dims(u_type)

        parent_candidates = []
        if u_type == 'gather': parent_candidates = placed_blocks
        elif u_type == 'living':
            if current_hub: parent_candidates = [current_hub]
            else: parent_candidates = placed_blocks
        else: parent_candidates = placed_blocks

        placed = False
        parents_to_try = list(parent_candidates)
        random.shuffle(parents_to_try)
        if len(parents_to_try) > 25: parents_to_try = parents_to_try[:25]

        for parent in parents_to_try:
            anchors = get_anchors_with_sides(parent, gw, gh)
            random.shuffle(anchors)
            for (nx, ny, side_idx) in anchors:
                candidate = Block(nx, ny, gw, gh, u_type, side_idx, parent)
                if check_overlap(candidate, placed_blocks): continue
                outer_crv = candidate.get_outer_crv()
                if boundary_geo.Contains(outer_crv.GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Outside: continue

                placed_blocks.append(candidate)
                if u_type == 'gather': current_hub = candidate
                current_area_m += (gw * GRID_UNIT * gh * GRID_UNIT)
                placed = True
                build_queue.pop(0)
                break
            if placed: break

        if placed: fails = 0
        else:
            fails += 1
            if u_type == 'living':
                build_queue = []; current_hub = None; build_queue.append('prod')

    # --- OUTPUT ---
    o_liv, o_prod, o_gath = [], [], []
    h_liv, h_prod, h_gath = [], [], []
    o_walls, raw_tunnel_crvs = [], []

    # NEW LIST FOR LIGHTS
    all_lights = []

    for b in placed_blocks:
        outer = b.get_outer_crv()
        o_walls.append(outer)

        # 1. TUNNELS (Old Logic)
        tunnel = b.get_tunnel_crv()
        if tunnel: raw_tunnel_crvs.append(tunnel)

        # 2. ROOM VOIDS (For standard cutout)
        center = outer.GetBoundingBox(True).Center
        transform = rg.Transform.Scale(center, HOLE_RATIO)
        hole = outer.Duplicate(); hole.Transform(transform)

        # 3. LIGHTS (New Logic: Perimeter of Gather/Living only)
        block_lights = generate_light_matrix(b)
        all_lights.extend(block_lights)

        if b.type == 'living': o_liv.append(outer); h_liv.append(hole)
        elif b.type == 'prod': o_prod.append(outer); h_prod.append(hole)
        elif b.type == 'gather': o_gath.append(outer); h_gath.append(hole)

    if len(raw_tunnel_crvs) > 0:
        o_tunnels = rg.Curve.CreateBooleanUnion(raw_tunnel_crvs)
        if not o_tunnels: o_tunnels = raw_tunnel_crvs
    else: o_tunnels = []

    return o_liv, o_prod, o_gath, h_liv, h_prod, h_gath, o_walls, o_tunnels, all_lights

living, prod, gather, living_holes, prod_holes, gather_holes, walls, tunnels, lights = main()
