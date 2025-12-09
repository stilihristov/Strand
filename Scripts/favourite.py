import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import math
import random
import System.Collections.Generic as scg

# --- CONFIGURATION ---
GRID_UNIT = 3.75
HOLE_RATIO = 0.25
DENSITY_LIMIT = 0.90

# --- DRAINAGE CONFIGURATION ---
DRAINAGE_WIDTH = 2.0
# Gap = 2m (Cluster A) + 2m (Cluster B) = 4m total gap.
REQUIRED_GAP_METERS = DRAINAGE_WIDTH * 2
BUFFER_CELLS = int(math.ceil(REQUIRED_GAP_METERS / GRID_UNIT))

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
    def __init__(self, gx, gy, gw, gh, b_type, cluster_id, attach_side=None, parent=None):
        self.gx = int(gx); self.gy = int(gy)
        self.gw = int(gw); self.gh = int(gh)
        self.type = b_type
        self.cluster_id = cluster_id
        self.attach_side = attach_side
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
    cistern_buffer = 0
    if new_b.type == 'cistern':
        cistern_buffer = 1

    for e in existing_blocks:
        current_buffer = 0

        # Case 1: Parent/Child connection (Internal to a cluster)
        if new_b.parent == e or e.parent == new_b:
            current_buffer = 0

        # Case 2: Different Clusters (Neighbor check)
        elif new_b.cluster_id != e.cluster_id and e.type != 'void':
            current_buffer = BUFFER_CELLS

        # Case 3: Same Cluster (Internal packing)
        else:
            if new_b.type == 'cistern' and e.type == 'cistern':
                current_buffer = cistern_buffer
            else:
                current_buffer = 0

        if (new_b.max_x + current_buffer <= e.min_x or
            new_b.min_x >= e.max_x + current_buffer or
            new_b.max_y + current_buffer <= e.min_y or
            new_b.min_y >= e.max_y + current_buffer):
            continue
        else:
            return True
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

def get_anchors_standard(parent, child_w, child_h):
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

def get_anchors_distanced(parent, child_w, child_h, gap):
    anchors = []
    anchors.append((parent.max_x + gap, parent.max_y - child_h, 1))
    anchors.append((parent.max_x + gap, parent.min_y, 1))
    anchors.append((parent.min_x - child_w - gap, parent.max_y - child_h, 3))
    anchors.append((parent.min_x - child_w - gap, parent.min_y, 3))
    anchors.append((parent.min_x, parent.max_y + gap, 2))
    anchors.append((parent.max_x - child_w, parent.max_y + gap, 2))
    anchors.append((parent.min_x, parent.min_y - child_h - gap, 0))
    anchors.append((parent.max_x - child_w, parent.min_y - child_h - gap, 0))
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
    if block.type == 'cistern' or block.type == 'tunnel' or block.type == 'void': return []
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

def generate_cluster_geometry(placed_blocks):
    clusters = {}
    for b in placed_blocks:
        if b.type == 'void': continue
        if b.cluster_id not in clusters:
            clusters[b.cluster_id] = []
        clusters[b.cluster_id].append(b.get_outer_crv())

    all_outlines = []
    all_drainage = []

    for c_id, crvs in clusters.items():
        if not crvs: continue
        cluster_union = rg.Curve.CreateBooleanUnion(crvs)
        if not cluster_union: cluster_union = crvs

        for crv in cluster_union: all_outlines.append(crv)

        for crv in cluster_union:
            offsets = crv.Offset(rg.Plane.WorldXY, DRAINAGE_WIDTH, 0.01, rg.CurveOffsetCornerStyle.Sharp)
            if offsets: all_drainage.extend(offsets)

    return all_outlines, all_drainage

def main():
    if not 'reset' in globals() or not reset: return [], [], [], [], [], [], [], [], [], []
    if not 'boundary' in globals() or not boundary: return [], [], [], [], [], [], [], [], [], []
    random.seed(int(seed))

    boundary_brep = rs.coercebrep(boundary)
    boundary_geo = None
    void_blocks = []
    if boundary_brep:
        for loop in boundary_brep.Loops:
            curve = loop.To3dCurve()
            if loop.LoopType == rg.BrepLoopType.Outer: boundary_geo = curve
            elif loop.LoopType == rg.BrepLoopType.Inner: void_blocks.append(VoidBlock(curve))
    else:
        boundary_geo = rs.coercecurve(boundary)
    if not boundary_geo: return [], [], [], [], [], [], [], [], [], []

    boundary_area = rg.AreaMassProperties.Compute(boundary_geo).Area
    target_fill = boundary_area * DENSITY_LIMIT

    placed_blocks = []
    placed_blocks.extend(void_blocks)
    current_area_m = 0
    build_queue = []
    current_hub = None
    current_cluster_id = 0
    current_cluster_prods = []

    cistern_retry_mode = False

    bbox = boundary_geo.GetBoundingBox(True)
    start_gx = int(bbox.Center.X / GRID_UNIT); start_gy = int(bbox.Center.Y / GRID_UNIT)
    seed_w, seed_h = get_grid_dims('prod')
    first_block = Block(start_gx, start_gy, seed_w, seed_h, 'prod', current_cluster_id, None, None)

    if (boundary_geo.Contains(first_block.get_outer_crv().GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Inside
        and not check_overlap(first_block, placed_blocks)):
        placed_blocks.append(first_block)
        current_area_m += (seed_w * GRID_UNIT * seed_h * GRID_UNIT)
        current_cluster_prods.append(first_block)

    # --- SAFETY COUNTERS FOR LOOP ---
    consecutive_fails = 0
    total_fails = 0
    MAX_TOTAL_FAILS = 1000 # Hard Stop to prevent hanging

    while current_area_m < target_fill and total_fails < MAX_TOTAL_FAILS:
        if len(build_queue) == 0:
            build_queue = generate_cluster_queue()
            current_hub = None
            current_cluster_prods = []
            current_cluster_id += 1
            cistern_retry_mode = False

        u_type = build_queue[0]

        if u_type == 'cistern' and cistern_retry_mode:
             gw, gh = 2, 2
        else:
             gw, gh = get_grid_dims(u_type)

        parent_candidates = []
        valid_blocks = [b for b in placed_blocks if b.type != 'void']

        if u_type == 'gather':
            parent_candidates = valid_blocks
        elif u_type == 'cistern':
            if current_hub: parent_candidates = [current_hub]
            else: parent_candidates = []
        elif u_type == 'living':
            if current_hub: parent_candidates = [current_hub]
            else: parent_candidates = valid_blocks
        elif u_type == 'prod':
            if current_hub: parent_candidates = [current_hub]
            parent_candidates.extend(current_cluster_prods)
            if not parent_candidates: parent_candidates = valid_blocks

        placed = False

        random.shuffle(parent_candidates)
        # Limit search depth to prevent lag on huge maps
        for parent in parent_candidates[:50]:
            anchors = []
            if u_type == 'gather':
                anchors = get_anchors_distanced(parent, gw, gh, BUFFER_CELLS)
            else:
                anchors = get_anchors_standard(parent, gw, gh)

            random.shuffle(anchors)
            for (nx, ny, side_idx) in anchors:
                candidate = Block(nx, ny, gw, gh, u_type, current_cluster_id, side_idx, parent)

                if check_overlap(candidate, placed_blocks): continue
                if boundary_geo.Contains(candidate.get_outer_crv().GetBoundingBox(True).Center, rg.Plane.WorldXY, 0.1) == rg.PointContainment.Outside: continue

                placed_blocks.append(candidate)
                if u_type == 'gather': current_hub = candidate
                if u_type == 'prod': current_cluster_prods.append(candidate)
                current_area_m += (gw * GRID_UNIT * gh * GRID_UNIT)
                placed = True; build_queue.pop(0); break
            if placed: break

        if placed:
            consecutive_fails = 0
            if u_type == 'cistern' and cistern_retry_mode:
                cistern_retry_mode = False
        else:
            # FAILURE HANDLING
            consecutive_fails += 1
            total_fails += 1 # Increments forever, eventually killing the loop

            if u_type == 'cistern' and not cistern_retry_mode:
                cistern_retry_mode = True
                continue

            if u_type == 'cistern':
                blocks_to_remove = [b for b in placed_blocks if b.cluster_id == current_cluster_id]
                placed_blocks = [b for b in placed_blocks if b.cluster_id != current_cluster_id]
                area_to_remove = 0
                for b in blocks_to_remove: area_to_remove += (b.gw * GRID_UNIT * b.gh * GRID_UNIT)
                current_area_m -= area_to_remove
                build_queue = []
                current_hub = None
                current_cluster_prods = []
                cistern_retry_mode = False

            # Skip difficult block logic
            if consecutive_fails > 50 and len(build_queue) > 0:
                build_queue.pop(0)
                consecutive_fails = 0

    # --- OUTPUT GENERATION ---
    o_liv, o_prod, o_gath, o_cist = [], [], [], []
    h_liv, h_prod, h_gath, all_lights = [], [], [], []

    for b in placed_blocks:
        if b.type == 'void': continue
        outer = b.get_outer_crv()

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

    cluster_outlines, final_drainage = generate_cluster_geometry(placed_blocks)

    return o_liv, o_prod, o_gath, o_cist, h_liv, h_prod, h_gath, all_lights, final_drainage, cluster_outlines

# Execute
living, prod, gather, cisterns, living_holes, prod_holes, gather_holes, lights, drainage, cluster_outlines = main()
