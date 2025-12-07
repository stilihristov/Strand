import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import math
import random
import System.Collections.Generic as scg

# --- CONFIGURATION ---
GRID_UNIT = 3.75
HOLE_RATIO = 0.25
DENSITY_LIMIT = 0.9

# --- DRAINAGE CONFIGURATION ---
DRAINAGE_WIDTH = 2.0

# --- LIGHTING CONFIGURATION ---
LIGHT_DIAMETER = 0.5
LIGHT_SPACING = 1.875

# --- UNIT SETTINGS ---
# Added 'cistern' to areas and ratios
# Cistern area target ~300m2
AREAS = {
    'gather': (800, 1050),
    'living': (300, 450),
    'prod': (30, 200),
    'cistern': (100, 320) # Target ~300
}

# Ratios determine relative frequency of Prod units
UNIT_RATIOS = {'gather': 1, 'living': 3, 'prod': 7}

# --- CLUSTER SETTINGS ---
LIVING_MIN = 3
LIVING_MAX = 5

class Block:
    def __init__(self, gx, gy, gw, gh, b_type, cluster_id, attach_side=None, parent=None):
        # Back to Integer Grid Coordinates
        self.gx = int(gx); self.gy = int(gy)
        self.gw = int(gw); self.gh = int(gh)
        self.type = b_type
        self.cluster_id = cluster_id
        self.attach_side = attach_side
        self.parent = parent

        self.min_x = self.gx; self.max_x = self.gx + self.gw
        self.min_y = self.gy; self.max_y = self.gy + self.gh

    def get_outer_crv(self):
        # Calculate World Coordinates
        x = self.gx * GRID_UNIT
        y = self.gy * GRID_UNIT
        w = self.gw * GRID_UNIT
        h = self.gh * GRID_UNIT

        # ### LOGIC CHANGE: Return Circle for Cistern, Rectangle for others
        if self.type == 'cistern':
            # Center of the grid box
            center = rg.Point3d(x + w/2.0, y + h/2.0, 0)
            # Radius: We fit the circle inside the smallest dimension of the grid box
            radius = min(w, h) / 2.0
            return rg.Circle(rg.Plane.WorldXY, center, radius).ToNurbsCurve()
        else:
            return rg.Rectangle3d(rg.Plane.WorldXY, rg.Point3d(x,y,0), rg.Point3d(x+w,y+h,0)).ToNurbsCurve()

def check_overlap(new_b, existing_blocks):
    # Standard Grid Overlap Check
    for e in existing_blocks:
        if (new_b.max_x <= e.min_x or new_b.min_x >= e.max_x or new_b.max_y <= e.min_y or new_b.min_y >= e.max_y): continue
        else: return True
    return False

def get_grid_dims(u_type):
    target_area = random.uniform(*AREAS[u_type])

    # Force Cisterns to be square so the circle fits nicely
    if u_type == 'cistern':
        side_m = math.sqrt(target_area)
        # Round to nearest grid unit
        g_side = max(1, int(round(side_m / GRID_UNIT)))
        return g_side, g_side

    # Standard Rectangular logic for others
    aspect = random.uniform(0.6, 1.5)
    w_m = math.sqrt(target_area * aspect); h_m = target_area / w_m
    gw = max(1, int(round(w_m / GRID_UNIT))); gh = max(1, int(round(h_m / GRID_UNIT)))
    if random.random() > 0.5: gw, gh = gh, gw
    return gw, gh

def get_anchors_standard(parent, child_w, child_h):
    # Standard Grid Anchors (Glueing logic)
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

    # 1. Gathering Hub
    queue.append('gather')

    # 2. ### NEW: Add exactly one Cistern per cluster
    queue.append('cistern')

    # 3. Living Units
    num_living = random.randint(LIVING_MIN, LIVING_MAX)
    for i in range(num_living): queue.append('living')

    # 4. Production Units
    cluster_weight = num_living + 2 # +2 for gather and cistern
    prod_weight = UNIT_RATIOS['prod'] / float(UNIT_RATIOS['living'] + UNIT_RATIOS['gather'])
    num_prod = int(round(cluster_weight * prod_weight))
    num_prod = int(num_prod * random.uniform(0.8, 1.2))
    for i in range(num_prod): queue.append('prod')

    return queue

def generate_light_matrix(block):
    # Skip lights for cisterns? Or add them?
    # Let's keep lights for living/gather/prod, maybe skip cistern or circular pattern?
    # For simplicity, skipping lights on circular cisterns for now to keep it clean.
    if block.type == 'cistern': return []

    lights = []
    w_m = block.gw * GRID_UNIT; h_m = block.gh * GRID_UNIT
    start_x = block.gx * GRID_UNIT; start_y = block.gy * GRID_UNIT
    cols = int(w_m / LIGHT_SPACING); rows = int(h_m / LIGHT_SPACING)
    margin_x = (w_m - (cols * LIGHT_SPACING)) / 2.0
    margin_y = (h_m - (rows * LIGHT_SPACING)) / 2.0
    radius = LIGHT_DIAMETER / 2.0
    OFFSET_IDX = 1
    if cols <= (OFFSET_IDX * 2) or rows <= (OFFSET_IDX * 2): return []

    for i in range(cols):
        for j in range(rows):
            on_x_ring = (i == OFFSET_IDX or i == cols - 1 - OFFSET_IDX)
            on_y_ring = (j == OFFSET_IDX or j == rows - 1 - OFFSET_IDX)
            in_x_range = (i >= OFFSET_IDX and i <= cols - 1 - OFFSET_IDX)
            in_y_range = (j >= OFFSET_IDX and j <= rows - 1 - OFFSET_IDX)
            is_valid_perimeter = (on_x_ring and in_y_range) or (on_y_ring and in_x_range)

            if is_valid_perimeter:
                cx = start_x + margin_x + (i * LIGHT_SPACING) + (LIGHT_SPACING / 2.0)
                cy = start_y + margin_y + (j * LIGHT_SPACING) + (LIGHT_SPACING / 2.0)
                center = rg.Point3d(cx, cy, 0)
                circle = rg.Circle(rg.Plane.WorldXY, center, radius).ToNurbsCurve()
                lights.append(circle)
    return lights

def generate_unit_based_drainage(blocks):
    individual_offsets = []
    for b in blocks:
        outer_crv = b.get_outer_crv()
        # Offset logic works for Circles too
        offset_crvs = outer_crv.Offset(rg.Plane.WorldXY, DRAINAGE_WIDTH, 0.01, rg.CurveOffsetCornerStyle.Sharp)
        if offset_crvs:
            individual_offsets.extend(offset_crvs)

    final_drainage = rg.Curve.CreateBooleanUnion(individual_offsets)
    if not final_drainage: return individual_offsets
    return final_drainage

def main():
    if not 'reset' in globals() or not reset: return [], [], [], [], [], [], [], [], [], []
    if not 'boundary' in globals() or not boundary: return [], [], [], [], [], [], [], [], [], []

    random.seed(int(seed))
    boundary_geo = rs.coercecurve(boundary)
    boundary_area = rg.AreaMassProperties.Compute(boundary_geo).Area
    target_fill = boundary_area * DENSITY_LIMIT

    placed_blocks = []
    current_area_m = 0

    build_queue = []
    current_hub = None
    current_cluster_id = 0

    bbox = boundary_geo.GetBoundingBox(True)
    start_gx = int(bbox.Center.X / GRID_UNIT); start_gy = int(bbox.Center.Y / GRID_UNIT)
    seed_w, seed_h = get_grid_dims('prod')

    first_block = Block(start_gx, start_gy, seed_w, seed_h, 'prod', current_cluster_id, None, None)

    seed_crv = first_block.get_outer_crv()
    if boundary_geo.Contains(seed_crv.GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Inside:
        placed_blocks.append(first_block)
        current_area_m += (seed_w * GRID_UNIT * seed_h * GRID_UNIT)
    else: return [], [], [], [], [], [], [], [], [], []

    fails = 0

    while current_area_m < target_fill and fails < 200:
        if len(build_queue) == 0:
            build_queue = generate_cluster_queue()
            current_hub = None
            current_cluster_id += 1

        u_type = build_queue[0]
        gw, gh = get_grid_dims(u_type)

        parent_candidates = []
        # Cisterns and Gather hubs can attach to anything
        if u_type == 'gather' or u_type == 'cistern':
            parent_candidates = placed_blocks
        elif u_type == 'living':
            if current_hub: parent_candidates = [current_hub]
            else: parent_candidates = placed_blocks
        else: parent_candidates = placed_blocks

        placed = False
        parents_to_try = list(parent_candidates)
        random.shuffle(parents_to_try)
        if len(parents_to_try) > 25: parents_to_try = parents_to_try[:25]

        for parent in parents_to_try:
            # Back to Standard Anchors (glued)
            anchors = get_anchors_standard(parent, gw, gh)
            random.shuffle(anchors)
            for (nx, ny, side_idx) in anchors:
                candidate = Block(nx, ny, gw, gh, u_type, current_cluster_id, side_idx, parent)

                if check_overlap(candidate, placed_blocks): continue
                outer_crv = candidate.get_outer_crv()
                if boundary_geo.Contains(outer_crv.GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Outside: continue

                placed_blocks.append(candidate)
                # If we placed a gather hub, update current_hub
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
                build_queue = []; current_hub = None

    # --- OUTPUT ---
    o_liv, o_prod, o_gath, o_cist = [], [], [], []
    h_liv, h_prod, h_gath = [], [], []
    o_walls = []
    all_lights = []

    for b in placed_blocks:
        outer = b.get_outer_crv()
        o_walls.append(outer)

        # Add holes only for rectangular types for now
        if b.type != 'cistern':
            center = outer.GetBoundingBox(True).Center
            transform = rg.Transform.Scale(center, HOLE_RATIO)
            hole = outer.Duplicate(); hole.Transform(transform)
            if b.type == 'living': h_liv.append(hole)
            elif b.type == 'prod': h_prod.append(hole)
            elif b.type == 'gather': h_gath.append(hole)

        block_lights = generate_light_matrix(b)
        all_lights.extend(block_lights)

        if b.type == 'living': o_liv.append(outer)
        elif b.type == 'prod': o_prod.append(outer)
        elif b.type == 'gather': o_gath.append(outer)
        elif b.type == 'cistern': o_cist.append(outer)

    # Drainage
    final_drainage = generate_unit_based_drainage(placed_blocks)

    return o_liv, o_prod, o_gath, o_cist, h_liv, h_prod, h_gath, all_lights, final_drainage

# Unpack logic adjusted for new output (o_cist added, tunnels removed)
living, prod, gather, cisterns, living_holes, prod_holes, gather_holes, lights, drainage = main()
