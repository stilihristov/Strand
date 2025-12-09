import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import math
import random
import System.Collections.Generic as scg

# --- CONFIGURATION ---
GRID_UNIT = 3.75
HOLE_RATIO = 0.25
DENSITY_LIMIT = 0.90
seed = 2024  # Change this to vary the map

# --- GAP CONFIGURATION ---
# We use exactly 1 grid cell (3.75m) as the road between clusters.
LOGICAL_GAP_CELLS = 1

# --- LIGHTING CONFIGURATION ---
LIGHT_DIAMETER = 0.5
LIGHT_SPACING = 1.875

# --- UNIT SETTINGS ---
AREAS = {
    'gather': (800, 1050),
    'living': (300, 450),
    'prod': (30, 200),
    'cistern': (50, 320)
}

# --- CLUSTER SETTINGS ---
LIVING_MIN = 3
LIVING_MAX = 5
PROD_MIN = 5
PROD_MAX = 15

class Block:
    def __init__(self, gx, gy, gw, gh, b_type, cluster_id, parent=None):
        self.gx = int(gx); self.gy = int(gy)
        self.gw = int(gw); self.gh = int(gh)
        self.type = b_type
        self.cluster_id = cluster_id
        self.parent = parent

        self.min_x = self.gx; self.max_x = self.gx + self.gw
        self.min_y = self.gy; self.max_y = self.gy + self.gh

    def get_outer_crv(self):
        x = self.gx * GRID_UNIT
        y = self.gy * GRID_UNIT
        w = self.gw * GRID_UNIT
        h = self.gh * GRID_UNIT

        if self.type == 'cistern':
            center = rg.Point3d(x + w/2.0, y + h/2.0, 0)
            radius = min(w, h) / 2.0
            return rg.Circle(rg.Plane.WorldXY, center, radius).ToNurbsCurve()
        else:
            return rg.Rectangle3d(rg.Plane.WorldXY, rg.Point3d(x,y,0), rg.Point3d(x+w,y+h,0)).ToNurbsCurve()

class VoidBlock:
    def __init__(self, curve):
        self.curve = curve
        self.type = 'void'
        self.cluster_id = -1
        bbox = curve.GetBoundingBox(True)
        self.min_x = int(bbox.Min.X / GRID_UNIT)
        self.min_y = int(bbox.Min.Y / GRID_UNIT)
        self.max_x = int(math.ceil(bbox.Max.X / GRID_UNIT))
        self.max_y = int(math.ceil(bbox.Max.Y / GRID_UNIT))

    def get_outer_crv(self):
        return self.curve

def check_overlap(new_b, existing_blocks):
    """
    STRICT LOGIC:
    - Same Cluster = 0 Gap (Touch)
    - Diff Cluster = 1 Cell Gap (3.75m Road)
    """
    cistern_buffer = 0
    if new_b.type == 'cistern': cistern_buffer = 1

    for e in existing_blocks:
        required_gap = 0

        if e.type == 'void':
             required_gap = 0
        elif new_b.cluster_id == e.cluster_id:
            # Same Cluster
            if new_b.type == 'cistern' and e.type == 'cistern': required_gap = cistern_buffer
            else: required_gap = 0
        else:
            # Different Cluster
            required_gap = LOGICAL_GAP_CELLS

        if (new_b.max_x + required_gap <= e.min_x or
            new_b.min_x >= e.max_x + required_gap or
            new_b.max_y + required_gap <= e.min_y or
            new_b.min_y >= e.max_y + required_gap):
            continue
        else:
            return True # Collision
    return False

def get_grid_dims(u_type):
    target_area = random.uniform(*AREAS[u_type])
    if u_type == 'cistern':
        side_m = math.sqrt(target_area)
        g_side = max(1, int(round(side_m / GRID_UNIT)))
        return g_side, g_side
    aspect = random.uniform(0.6, 1.5)
    w_m = math.sqrt(target_area * aspect); h_m = target_area / w_m
    gw = max(1, int(round(w_m / GRID_UNIT))); gh = max(1, int(round(h_m / GRID_UNIT)))
    if random.random() > 0.5: gw, gh = gh, gw
    return gw, gh

def get_anchors_tight(parent, child_w, child_h):
    # Returns points touching the parent (Gap=0)
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

def get_anchors_gap_strict(parent, child_w, child_h):
    # Returns points EXACTLY 1 cell away.
    # Used when a new cluster is trying to attach to an old one.
    anchors = []
    gap = LOGICAL_GAP_CELLS
    anchors.append((parent.max_x + gap, parent.gy, 1))
    anchors.append((parent.min_x - child_w - gap, parent.gy, 3))
    anchors.append((parent.gx, parent.max_y + gap, 2))
    anchors.append((parent.gx, parent.min_y - child_h - gap, 0))
    return anchors

def generate_cluster_queue():
    queue = []
    queue.append('gather')
    queue.append('cistern')
    num_living = random.randint(LIVING_MIN, LIVING_MAX)
    for i in range(num_living): queue.append('living')
    num_prod = random.randint(PROD_MIN, PROD_MAX)
    for i in range(num_prod): queue.append('prod')
    return queue

def generate_light_matrix(block):
    if block.type == 'cistern' or block.type == 'void': return []
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
            if (on_x_ring and in_y_range) or (on_y_ring and in_x_range):
                cx = start_x + margin_x + (i * LIGHT_SPACING) + (LIGHT_SPACING / 2.0)
                cy = start_y + margin_y + (j * LIGHT_SPACING) + (LIGHT_SPACING / 2.0)
                lights.append(rg.Circle(rg.Plane.WorldXY, rg.Point3d(cx, cy, 0), radius).ToNurbsCurve())
    return lights

def fill_gaps_with_production(placed_blocks, boundary_geo, max_fill_passes=40):
    """
    Interlocking Pass:
    Tries to place small production blocks (2x2) that respect the
    1-cell gap rule, creating a tight 'fitted' look.
    """
    clusters = {}
    for b in placed_blocks:
        if b.type == 'void': continue
        if b.cluster_id not in clusters: clusters[b.cluster_id] = []
        clusters[b.cluster_id].append(b)

    filler_w, filler_h = 2, 2

    for i in range(max_fill_passes):
        added_this_pass = 0
        for c_id, blocks in clusters.items():
            parent = random.choice(blocks)
            anchors = get_anchors_tight(parent, filler_w, filler_h)
            random.shuffle(anchors)

            for (nx, ny, _) in anchors:
                candidate = Block(nx, ny, filler_w, filler_h, 'prod', c_id, parent)

                if boundary_geo.Contains(candidate.get_outer_crv().GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Outside:
                    continue
                if check_overlap(candidate, placed_blocks):
                    continue

                placed_blocks.append(candidate)
                blocks.append(candidate)
                added_this_pass += 1
                break
        if added_this_pass == 0: break
    return placed_blocks

def main():
    if not 'reset' in globals() or not reset: return [], [], [], [], [], [], [], [], [], []
    if not 'boundary' in globals() or not boundary: return [], [], [], [], [], [], [], [], [], []
    random.seed(int(seed))

    boundary_geo = rs.coercecurve(boundary)
    boundary_area = rg.AreaMassProperties.Compute(boundary_geo).Area
    target_fill = boundary_area * DENSITY_LIMIT

    placed_blocks = [] # Add void blocks here if needed
    current_area_m = 0
    build_queue = []
    current_cluster_id = 0
    current_cluster_blocks = []

    # 1. Place First Block (Seed 0)
    bbox = boundary_geo.GetBoundingBox(True)
    start_gx = int(bbox.Center.X / GRID_UNIT); start_gy = int(bbox.Center.Y / GRID_UNIT)
    seed_w, seed_h = get_grid_dims('prod')
    first_block = Block(start_gx, start_gy, seed_w, seed_h, 'prod', current_cluster_id, None)

    if (boundary_geo.Contains(first_block.get_outer_crv().GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Inside):
        placed_blocks.append(first_block)
        current_cluster_blocks.append(first_block)
        current_area_m += (seed_w * GRID_UNIT * seed_h * GRID_UNIT)

    consecutive_fails = 0
    total_fails = 0

    # --- MAIN LOOP ---
    while current_area_m < target_fill and total_fails < 1500:
        # Start New Cluster?
        if len(build_queue) == 0:
            build_queue = generate_cluster_queue()
            current_cluster_blocks = []
            current_cluster_id += 1

        u_type = build_queue[0]
        gw, gh = get_grid_dims(u_type)

        placed = False

        # DECISION: Grow existing cluster OR Spawn new cluster nearby
        is_new_cluster_start = (len(current_cluster_blocks) == 0)

        if is_new_cluster_start:
            # SPAWN LOGIC: Try to attach to ANY existing block with a 1-CELL GAP
            # This creates the "Tetris" fit immediately
            potential_parents = [b for b in placed_blocks if b.type != 'void']
            random.shuffle(potential_parents)

            for parent in potential_parents[:50]:
                # Special Anchors: 1 Cell Away
                anchors = get_anchors_gap_strict(parent, gw, gh)
                random.shuffle(anchors)

                for (nx, ny, _) in anchors:
                    candidate = Block(nx, ny, gw, gh, u_type, current_cluster_id, parent)

                    if boundary_geo.Contains(candidate.get_outer_crv().GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Outside: continue
                    if check_overlap(candidate, placed_blocks): continue

                    placed_blocks.append(candidate)
                    current_cluster_blocks.append(candidate)
                    current_area_m += (gw * GRID_UNIT * gh * GRID_UNIT)
                    build_queue.pop(0)
                    placed = True
                    break
                if placed: break

        else:
            # GROWTH LOGIC: Attach to Current Cluster (Touching)
            potential_parents = list(current_cluster_blocks)
            random.shuffle(potential_parents)

            for parent in potential_parents[:30]:
                anchors = get_anchors_tight(parent, gw, gh)
                random.shuffle(anchors)

                for (nx, ny, _) in anchors:
                    candidate = Block(nx, ny, gw, gh, u_type, current_cluster_id, parent)

                    if boundary_geo.Contains(candidate.get_outer_crv().GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Outside: continue
                    if check_overlap(candidate, placed_blocks): continue

                    placed_blocks.append(candidate)
                    current_cluster_blocks.append(candidate)
                    current_area_m += (gw * GRID_UNIT * gh * GRID_UNIT)
                    build_queue.pop(0)
                    placed = True
                    break
                if placed: break

        if placed:
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            total_fails += 1
            if consecutive_fails > 30 and len(build_queue) > 0:
                build_queue.pop(0); consecutive_fails = 0

    # --- FILLER PASS ---
    placed_blocks = fill_gaps_with_production(placed_blocks, boundary_geo)

    # --- OUTPUT ---
    o_liv, o_prod, o_gath, o_cist = [], [], [], []
    h_liv, h_prod, h_gath, all_lights = [], [], [], []
    clusters_dict = {}

    for b in placed_blocks:
        if b.type == 'void': continue
        outer = b.get_outer_crv()

        if b.cluster_id not in clusters_dict: clusters_dict[b.cluster_id] = []
        clusters_dict[b.cluster_id].append(outer)

        if b.type != 'cistern':
            center = outer.GetBoundingBox(True).Center
            transform = rg.Transform.Scale(center, HOLE_RATIO)
            hole = outer.Duplicate(); hole.Transform(transform)
            if b.type == 'living': h_liv.append(hole)
            elif b.type == 'prod': h_prod.append(hole)
            elif b.type == 'gather': h_gath.append(hole)

        all_lights.extend(generate_light_matrix(b))
        if b.type == 'living': o_liv.append(outer)
        elif b.type == 'prod': o_prod.append(outer)
        elif b.type == 'gather': o_gath.append(outer)
        elif b.type == 'cistern': o_cist.append(outer)

    # Generate Cluster Outlines
    cluster_outlines = []
    for cid, crvs in clusters_dict.items():
        union = rg.Curve.CreateBooleanUnion(crvs)
        if union: cluster_outlines.extend(union)
        else: cluster_outlines.extend(crvs)

    return o_liv, o_prod, o_gath, o_cist, h_liv, h_prod, h_gath, all_lights, [], cluster_outlines

# Execute
living, prod, gather, cisterns, living_holes, prod_holes, gather_holes, lights, drainage, cluster_outlines = main()
