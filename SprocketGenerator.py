import adsk.core, adsk.fusion
import math
import traceback
from typing import NamedTuple

# ── Module-level state (prevents garbage collection of event handlers) ──────
_app      = None
_ui       = None
_handlers = []
_ctrl     = None   # toolbar control, kept for cleanup in stop()

class ChainSpec(NamedTuple):
    code: str
    pitch_mm: float
    roller_mm: float
    inner_width_mm: float
    label: str


# pitch_mm, roller_mm, inner_width_mm
# Sources: ANSI B29.1, JIS B1801, common motorcycle chain catalogs.
CHAIN_SPECS = [
    ChainSpec('415',  12.700,  7.770,  4.880, 'JIS motorcycle light-duty'),
    ChainSpec('420',  12.700,  7.750,  6.350, 'Motorcycle / mini-bike / ATV'),
    ChainSpec('420H', 12.700,  7.750,  6.350, 'Motorcycle heavy-duty variant'),
    ChainSpec('428',  12.700,  8.510,  7.750, 'Motorcycle 125-250 cc'),
    ChainSpec('428H', 12.700,  8.510,  7.750, 'Motorcycle heavy-duty variant'),
    ChainSpec('520',  15.875, 10.160,  6.350, 'Motorcycle 250-400 cc'),
    ChainSpec('520H', 15.875, 10.160,  6.350, 'Motorcycle heavy-duty variant'),
    ChainSpec('525',  15.875, 10.160,  7.940, 'Motorcycle 400-750 cc'),
    ChainSpec('525H', 15.875, 10.160,  7.940, 'Motorcycle heavy-duty variant'),
    ChainSpec('530',  15.875, 10.160,  9.525, 'Motorcycle 600 cc+'),
    ChainSpec('530H', 15.875, 10.160,  9.525, 'Motorcycle heavy-duty variant'),
    ChainSpec('25',    6.350,  3.300,  3.180, 'ANSI #25 industrial'),
    ChainSpec('35',    9.525,  5.080,  4.760, 'ANSI #35 industrial'),
    ChainSpec('40',   12.700,  7.920,  7.850, 'ANSI #40 industrial'),
    ChainSpec('41',   12.700,  7.770,  6.350, 'ANSI #41 industrial lightweight'),
    ChainSpec('50',   15.875, 10.160,  9.530, 'ANSI #50 industrial'),
    ChainSpec('60',   19.050, 11.910, 12.570, 'ANSI #60 industrial'),
]

CHAIN_BY_CODE = {spec.code: spec for spec in CHAIN_SPECS}
SERIES_LIST = [spec.code for spec in CHAIN_SPECS]
SERIES_LABELS = [
    f'{spec.code:<4} - {spec.label} (pitch {spec.pitch_mm:.3f} mm)'
    for spec in CHAIN_SPECS
]
DEFAULT_SERIES_CODE = '520'
DEFAULT_SERIES_IDX = SERIES_LIST.index(DEFAULT_SERIES_CODE)


# ── Entry point (add-in: called once at load time) ──────────────────────────
def run(_context: str):
    global _app, _ui, _ctrl
    _app = adsk.core.Application.get()
    _ui  = _app.userInterface
    try:
        # Remove any leftover command definition from a previous load
        cmdDefs  = _ui.commandDefinitions
        existing = cmdDefs.itemById('SprocketGeneratorDlg')
        if existing:
            existing.deleteMe()

        cmdDef = cmdDefs.addButtonDefinition(
            'SprocketGeneratorDlg',
            'Sprocket Generator',
            'Generate a roller-chain sprocket (ANSI B29.1 / JIS B1801)'
        )

        onCreate = _CreatedHandler()
        cmdDef.commandCreated.add(onCreate)
        _handlers.append(onCreate)

        # Add button to the Solid > Create panel in the Design workspace
        panel = _ui.allToolbarPanels.itemById('SolidCreatePanel')
        _ctrl = panel.controls.addCommand(cmdDef, 'SolidSolidSpurGearCommand', False)
        _ctrl.isPromotedByDefault = True

    except Exception:
        if _ui:
            _ui.messageBox('Startup error:\n' + traceback.format_exc())


# ── Exit point (add-in: called when add-in is unloaded / Fusion closes) ──────
def stop(_context: str):
    global _ctrl
    try:
        if _ctrl and _ctrl.isValid:
            _ctrl.deleteMe()
        cmdDefs = _ui.commandDefinitions
        existing = cmdDefs.itemById('SprocketGeneratorDlg')
        if existing:
            existing.deleteMe()
        _handlers.clear()
    except Exception:
        pass


# ── Dialog: command created ──────────────────────────────────────────────────
class _CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd  = args.command
            cmd.isExecutedWhenPreEmpted = False
            inps = cmd.commandInputs

            # Integer spinner for tooth count
            inps.addIntegerSpinnerCommandInput(
                'toothCount', 'Tooth Count',
                6,     # min (6 teeth is absolute minimum for a sprocket)
                99,    # max
                1,     # step
                15     # default
            )

            # Dropdown for chain series
            dd = inps.addDropDownCommandInput(
                'chainSeries', 'Chain Series',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            for i, label in enumerate(SERIES_LABELS):
                dd.listItems.add(label, i == DEFAULT_SERIES_IDX)

            onExec    = _ExecuteHandler()
            onDestroy = _DestroyHandler()
            cmd.execute.add(onExec)
            cmd.destroy.add(onDestroy)
            _handlers.append(onExec)
            _handlers.append(onDestroy)

        except Exception:
            if _ui:
                _ui.messageBox('Dialog error:\n' + traceback.format_exc())


# ── Dialog: execute (OK clicked) ────────────────────────────────────────────
class _ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            design = adsk.fusion.Design.cast(_app.activeProduct)
            if not design:
                _ui.messageBox('Please open a Fusion 360 design first.')
                return
            inps   = args.command.commandInputs
            N      = inps.itemById('toothCount').value
            idx    = inps.itemById('chainSeries').selectedItem.index
            series_code = SERIES_LIST[idx]
            _build_sprocket(N, series_code)
        except Exception:
            if _ui:
                _ui.messageBox('Build error:\n' + traceback.format_exc())


# ── Dialog: destroy (dialog closed for any reason) ──────────────────────────
class _DestroyHandler(adsk.core.CommandEventHandler):
    def notify(self, _args):
        pass  # add-in persists; nothing to do on dialog close


def _pt(x, y):
    return adsk.core.Point3D.create(x, y, 0.0)


def _arc_mid_ccw(cx, cy, radius, a_start, a_end):
    if a_end < a_start:
        a_end += 2.0 * math.pi
    a_mid = (a_start + a_end) / 2.0
    return (cx + radius * math.cos(a_mid), cy + radius * math.sin(a_mid))


def _mirror_about_axis(x, y, axis_angle):
    cos_2a = math.cos(2.0 * axis_angle)
    sin_2a = math.sin(2.0 * axis_angle)
    return (x * cos_2a + y * sin_2a, x * sin_2a - y * cos_2a)


def _circle_circle_intersections(cx1, cy1, r1, cx2, cy2, r2):
    d = math.hypot(cx2 - cx1, cy2 - cy1)
    if d <= 1e-9:
        raise ValueError('Degenerate circle intersection: centers coincide.')
    if d > (r1 + r2) + 1e-9:
        raise ValueError('No circle intersection: circles are separate.')
    if d < abs(r1 - r2) - 1e-9:
        raise ValueError('No circle intersection: one circle is inside another.')

    a = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    h_sq = max(r1 * r1 - a * a, 0.0)
    h = math.sqrt(h_sq)

    mx = cx1 + a * (cx2 - cx1) / d
    my = cy1 + a * (cy2 - cy1) / d
    dx = h * (cy2 - cy1) / d
    dy = h * (cx2 - cx1) / d
    return [(mx + dx, my - dy), (mx - dx, my + dy)]


def _largest_profile(sketch):
    profiles = sketch.profiles
    best_profile = None
    best_area = 0.0
    for index in range(profiles.count):
        profile = profiles.item(index)
        area = profile.areaProperties().area
        if area > best_area:
            best_area = area
            best_profile = profile
    return best_profile


def _set_or_add_mm_parameter(user_parameters, name, value_mm, comment):
    expr = f'{value_mm:.6f} mm'
    existing = user_parameters.itemByName(name)
    if existing:
        existing.expression = expr
    else:
        user_parameters.add(name, adsk.core.ValueInput.createByString(expr), 'mm', comment)


def _create_output_component(root, series_code, tooth_count):
    occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = f'Sprocket_{series_code}_{tooth_count}T'
    return component


def _compute_tooth_geometry(tooth_count, pitch_mm, roller_mm):
    pitch_cm = pitch_mm / 10.0
    roller_cm = roller_mm / 10.0

    pitch_radius = (pitch_cm / 2.0) / math.sin(math.pi / tooth_count)
    seat_radius = 0.505 * roller_cm + 0.0345 * (roller_cm ** (1.0 / 3.0))
    profile_radius = 0.12 * roller_cm * (tooth_count + 2)
    tip_diameter = 2.0 * pitch_radius + (1.0 - 1.6 / tooth_count) * pitch_cm - roller_cm
    tip_radius = tip_diameter / 2.0
    inner_radius = tip_radius - roller_cm
    bore_radius = 0.60 * inner_radius

    half_tooth_angle = math.pi / tooth_count
    contact_angle = math.radians(130.0) - (math.pi / 2.0) / tooth_count

    seat_center_x = pitch_radius + seat_radius - roller_cm / 2.0
    p0 = (seat_center_x - seat_radius, 0.0)

    p1_angle = math.pi - contact_angle / 2.0
    p1 = (
        seat_center_x + seat_radius * math.cos(p1_angle),
        seat_radius * math.sin(p1_angle),
    )

    seat_mid_angle = math.pi - contact_angle / 4.0
    seat_mid = (
        seat_center_x + seat_radius * math.cos(seat_mid_angle),
        seat_radius * math.sin(seat_mid_angle),
    )

    profile_center_x = pitch_radius - math.cos(contact_angle / 2.0) * (profile_radius + seat_radius)
    profile_center_y = math.sin(contact_angle / 2.0) * (profile_radius + seat_radius)
    profile_radius_actual = math.hypot(profile_center_x - p1[0], profile_center_y - p1[1])

    intersections = _circle_circle_intersections(
        profile_center_x,
        profile_center_y,
        profile_radius_actual,
        0.0,
        0.0,
        tip_radius,
    )
    d0 = math.hypot(intersections[0][0] - p1[0], intersections[0][1] - p1[1])
    d1 = math.hypot(intersections[1][0] - p1[0], intersections[1][1] - p1[1])
    p2 = intersections[0] if d0 < d1 else intersections[1]

    a1 = math.atan2(p1[1] - profile_center_y, p1[0] - profile_center_x)
    a2 = math.atan2(p2[1] - profile_center_y, p2[0] - profile_center_x)
    profile_mid = _arc_mid_ccw(profile_center_x, profile_center_y, profile_radius_actual, a1, a2)

    p3 = (tip_radius * math.cos(half_tooth_angle), tip_radius * math.sin(half_tooth_angle))

    p1_m = _mirror_about_axis(p1[0], p1[1], half_tooth_angle)
    p2_m = _mirror_about_axis(p2[0], p2[1], half_tooth_angle)
    p0_m = _mirror_about_axis(p0[0], p0[1], half_tooth_angle)
    seat_mid_m = _mirror_about_axis(seat_mid[0], seat_mid[1], half_tooth_angle)
    profile_mid_m = _mirror_about_axis(profile_mid[0], profile_mid[1], half_tooth_angle)

    inner_start = (
        inner_radius * math.cos(2.0 * half_tooth_angle),
        inner_radius * math.sin(2.0 * half_tooth_angle),
    )
    inner_mid = (
        inner_radius * math.cos(half_tooth_angle),
        inner_radius * math.sin(half_tooth_angle),
    )
    inner_end = (inner_radius, 0.0)

    return {
        'pitch_radius': pitch_radius,
        'seat_radius': seat_radius,
        'profile_radius': profile_radius,
        'tip_radius': tip_radius,
        'root_radius': pitch_radius - roller_cm / 2.0,
        'inner_radius': inner_radius,
        'bore_radius': bore_radius,
        'contact_angle': contact_angle,
        'p0': p0,
        'p1': p1,
        'p2': p2,
        'p3': p3,
        'p0_m': p0_m,
        'p1_m': p1_m,
        'p2_m': p2_m,
        'seat_mid': seat_mid,
        'seat_mid_m': seat_mid_m,
        'profile_mid': profile_mid,
        'profile_mid_m': profile_mid_m,
        'inner_start': inner_start,
        'inner_mid': inner_mid,
        'inner_end': inner_end,
    }


def _draw_tooth_profile(component, geometry):
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = 'SprocketToothProfile'

    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines

    def point(name):
        return _pt(*geometry[name])

    arcs.addByThreePoints(point('p0'), point('seat_mid'), point('p1'))
    arcs.addByThreePoints(point('p1'), point('profile_mid'), point('p2'))
    arcs.addByThreePoints(point('p2'), point('p3'), point('p2_m'))
    arcs.addByThreePoints(point('p2_m'), point('profile_mid_m'), point('p1_m'))
    arcs.addByThreePoints(point('p1_m'), point('seat_mid_m'), point('p0_m'))
    lines.addByTwoPoints(point('p0_m'), point('inner_start'))
    arcs.addByThreePoints(point('inner_start'), point('inner_mid'), point('inner_end'))
    lines.addByTwoPoints(point('inner_end'), point('p0'))
    return sketch


def _build_sprocket(tooth_count, series_code):
    design = adsk.fusion.Design.cast(_app.activeProduct)
    root = design.rootComponent
    spec = CHAIN_BY_CODE[series_code]

    face_width_mm = spec.inner_width_mm * 0.95
    geometry = _compute_tooth_geometry(tooth_count, spec.pitch_mm, spec.roller_mm)

    component = _create_output_component(root, series_code, tooth_count)
    sketch = _draw_tooth_profile(component, geometry)
    profile = _largest_profile(sketch)
    if profile is None:
        _ui.messageBox('No closed profile found - check geometry.')
        return

    extrude_features = component.features.extrudeFeatures
    extrude_input = extrude_features.createInput(
        profile,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    extrude_input.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByString(f'{face_width_mm:.4f} mm'),
    )
    tooth_body = extrude_features.add(extrude_input)
    tooth_body.name = 'SprocketTooth'

    patterned_bodies = adsk.core.ObjectCollection.create()
    patterned_bodies.add(tooth_body)
    pattern_input = component.features.circularPatternFeatures.createInput(
        patterned_bodies,
        component.zConstructionAxis,
    )
    pattern_input.quantity = adsk.core.ValueInput.createByString(str(tooth_count))
    pattern_input.totalAngle = adsk.core.ValueInput.createByString('360 deg')
    pattern_input.isSymmetric = False
    pattern_input.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
    pattern = component.features.circularPatternFeatures.add(pattern_input)
    pattern.name = 'SprocketPattern'

    bodies = component.bRepBodies
    if bodies.count > 1:
        base_body = bodies.item(0)
        tool_bodies = adsk.core.ObjectCollection.create()
        for index in range(1, bodies.count):
            tool_bodies.add(bodies.item(index))
        combine_input = component.features.combineFeatures.createInput(base_body, tool_bodies)
        combine_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
        combine_input.isKeepToolBodies = False
        combine = component.features.combineFeatures.add(combine_input)
        combine.name = 'Sprocket'

    user_parameters = design.userParameters
    _set_or_add_mm_parameter(user_parameters, 'Spr_Pitch', spec.pitch_mm, 'Chain pitch')
    _set_or_add_mm_parameter(user_parameters, 'Spr_RollerD', spec.roller_mm, 'Roller diameter')
    _set_or_add_mm_parameter(user_parameters, 'Spr_SeatR', geometry['seat_radius'] * 10.0, 'Seating arc radius')
    _set_or_add_mm_parameter(user_parameters, 'Spr_ProfileR', geometry['profile_radius'] * 10.0, 'Profile arc radius')
    _set_or_add_mm_parameter(user_parameters, 'Spr_PitchD', geometry['pitch_radius'] * 20.0, 'Pitch circle diameter')
    _set_or_add_mm_parameter(user_parameters, 'Spr_RootD', geometry['root_radius'] * 20.0, 'Root circle diameter')
    _set_or_add_mm_parameter(user_parameters, 'Spr_TipD', geometry['tip_radius'] * 20.0, 'Tip circle diameter')
    _set_or_add_mm_parameter(user_parameters, 'Spr_InnerR', geometry['inner_radius'] * 10.0, 'Inner closing radius')
    _set_or_add_mm_parameter(user_parameters, 'Spr_Width', face_width_mm, 'Face width')
    _set_or_add_mm_parameter(user_parameters, 'Spr_BoreD', geometry['bore_radius'] * 20.0, 'Bore placeholder diameter')

    print('=' * 58)
    print('  Roller Sprocket - ANSI B29.1 / JIS B1801')
    print(f'  Chain series     : {series_code}')
    print(f'  Tooth count      : {tooth_count}')
    print(f'  Pitch            : {spec.pitch_mm:.3f} mm')
    print(f'  Roller diameter  : {spec.roller_mm:.3f} mm')
    print(f"  Pitch circle OD  : {geometry['pitch_radius'] * 20.0:.3f} mm")
    print(f"  Root circle OD   : {geometry['root_radius'] * 20.0:.3f} mm")
    print(f"  Tip circle OD    : {geometry['tip_radius'] * 20.0:.3f} mm")
    print(f"  Seat radius      : {geometry['seat_radius'] * 10.0:.4f} mm")
    print(f"  Profile radius   : {geometry['profile_radius'] * 10.0:.3f} mm")
    print(f"  Contact angle    : {math.degrees(geometry['contact_angle']):.2f} deg")
    print(f'  Face width       : {face_width_mm:.3f} mm')
    print(f"  Bore OD default  : {geometry['bore_radius'] * 20.0:.3f} mm")
    print('=' * 58)