from flask import Blueprint, request, jsonify

from utils.helpers import get_world, TL_STATE_MAP, ensure_control, require_carla
from utils.cache import world_cache

blueprint = Blueprint("traffic", __name__)


@blueprint.route("/traffic_lights")
@require_carla
def traffic_lights_get():
    """
    Fix 19: Single spectator fetch, cached actors — eliminates double spectator
    RPC and replaces world.get_actors().filter() with the WorldCache list.
    """
    radius   = float(request.args.get("radius", 200))
    world    = get_world()
    spec_loc = world.get_spectator().get_transform().location   # single call

    actors = world_cache.get_actors(world)
    lights = []
    
    # Get metadata from DB
    from config.db import create_connection
    try:
        conn = create_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id, direction FROM traffic_light_metadata")
        meta = {r["actor_id"]: r["direction"] for r in c.fetchall()}
        conn.close()
    except:
        meta = {}

    for tl in (a for a in actors if "traffic_light" in a.type_id):
        loc  = tl.get_transform().location
        dist = spec_loc.distance(loc)
        if dist <= radius:
            state = str(tl.get_state()).split(".")[-1].lower()
            lights.append({
                "id":       tl.id,
                "state":    state,
                "direction": meta.get(tl.id),
                "distance": round(dist, 1),
                "x":        round(loc.x, 2),
                "y":        round(loc.y, 2),
                "z":        round(loc.z, 2),
            })
    lights.sort(key=lambda l: l["distance"])
    return jsonify({"success": True, "lights": lights})


@blueprint.route("/traffic_light/set", methods=["POST"])
@ensure_control
@require_carla
def traffic_light_set():
    d        = request.json or {}
    actor_id = int(d.get("id"))
    world    = get_world()
    actor    = world.get_actor(actor_id)
    if not actor:
        return jsonify({"success": False, "error": "Actor not found"}), 404

    if state_key in TL_STATE_MAP:
        actor.set_state(TL_STATE_MAP[state_key])

    freeze = d.get("freeze", False)
    if freeze:
        actor.freeze(True)

    # Persist to DB
    try:
        from config.db import create_connection
        conn = create_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id FROM traffic_light_metadata WHERE actor_id = ?", (actor_id,))
        if c.fetchone():
            c.execute("UPDATE traffic_light_metadata SET state = ?, is_frozen = ? WHERE actor_id = ?", 
                      (state_key, 1 if freeze else 0, actor_id))
        else:
            c.execute("INSERT INTO traffic_light_metadata (actor_id, state, is_frozen) VALUES (?, ?, ?)", 
                      (actor_id, state_key, 1 if freeze else 0))
        conn.commit()
        conn.close()
    except: pass

    return jsonify({"success": True})


@blueprint.route("/traffic_light/<int:tl_id>/set/<string:state>", methods=["GET", "POST"])
@ensure_control
@require_carla
def traffic_light_set_by_url(tl_id, state):
    world = get_world()
    actor = world.get_actor(tl_id)
    if not actor or "traffic_light" not in actor.type_id:
        return jsonify({"success": False, "error": "Traffic light not found"}), 404

    state_key = state.lower()
    valid_states = {"red", "yellow", "green"}
    if state_key not in valid_states:
        return jsonify({"success": False, "error": f"Invalid state. Use one of: {', '.join(valid_states)}"}), 400

    if state_key in TL_STATE_MAP:
        actor.set_state(TL_STATE_MAP[state_key])
        # Freeze the light so it stays in the requested state
        actor.freeze(True)
        
        # Persist to DB
        try:
            from config.db import create_connection
            conn = create_connection()
            c = conn.cursor()
            c.execute("SELECT actor_id FROM traffic_light_metadata WHERE actor_id = ?", (tl_id,))
            if c.fetchone():
                c.execute("UPDATE traffic_light_metadata SET state = ?, is_frozen = 1 WHERE actor_id = ?", 
                          (state_key, tl_id))
            else:
                c.execute("INSERT INTO traffic_light_metadata (actor_id, state, is_frozen) VALUES (?, ?, 1)", 
                          (tl_id, state_key))
            conn.commit()
            conn.close()
        except: pass

    return jsonify({
        "success": True, 
        "id": tl_id, 
        "state": state_key, 
        "message": f"Traffic light {tl_id} successfully set to {state_key} (persisted)"
    })


@blueprint.route("/traffic_light/freeze_all", methods=["POST"])
@ensure_control
@require_carla
def traffic_light_freeze_all():
    d         = request.json or {}
    freeze    = d.get("freeze", True)
    state_key = d.get("state", "").lower()
    world     = get_world()
    # Use cached actors instead of world.get_actors().filter()
    actors    = world_cache.get_actors(world)
    for tl in (a for a in actors if "traffic_light" in a.type_id):
        if state_key in TL_STATE_MAP:
            tl.set_state(TL_STATE_MAP[state_key])
        tl.freeze(freeze)
    return jsonify({"success": True})


def apply_persisted_traffic_lights(world):
    """Re-applies saved states and frozen status from the DB to all traffic lights."""
    try:
        from config.db import create_connection
        from utils.helpers import TL_STATE_MAP
        conn = create_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id, state, is_frozen FROM traffic_light_metadata WHERE state IS NOT NULL OR is_frozen = 1")
        persisted = {r["actor_id"]: {"state": r["state"], "frozen": r["is_frozen"]} for r in c.fetchall()}
        conn.close()
        
        if not persisted:
            return
            
        count = 0
        for actor_id, data in persisted.items():
            tl = world.get_actor(actor_id)
            if tl and tl.is_alive:
                if data["state"] in TL_STATE_MAP:
                    tl.set_state(TL_STATE_MAP[data["state"]])
                if data["frozen"]:
                    tl.freeze(True)
                count += 1
        return count
    except Exception as e:
        print(f"Error applying persisted traffic lights: {e}")
        return 0


@blueprint.route("/traffic_light/set_direction", methods=["POST"])
@require_carla
def set_tl_direction():
    try:
        d = request.json or {}
        actor_id = int(d.get("id"))
        direction = d.get("direction") # N, S, E, W, or None
        
        from config.db import create_connection
        conn = create_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id FROM traffic_light_metadata WHERE actor_id = ?", (actor_id,))
        if c.fetchone():
            c.execute("UPDATE traffic_light_metadata SET direction = ? WHERE actor_id = ?", (direction, actor_id))
        else:
            c.execute("INSERT INTO traffic_light_metadata (actor_id, direction) VALUES (?, ?)", (actor_id, direction))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "id": actor_id, "direction": direction})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/traffic_light/api_links")
@require_carla
def traffic_light_api_links():
    """Returns a list of all traffic light API links, ordered NSEW."""
    try:
        import socket
        def get_ip():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('10.255.255.255', 1))
                IP = s.getsockname()[0]
            except Exception:
                IP = '127.0.0.1'
            finally:
                s.close()
            return IP

        ip = get_ip()
        world = get_world()
        actors = world_cache.get_actors(world)
        tl_actors = [a for a in actors if "traffic_light" in a.type_id]
        
        from config.db import create_connection
        conn = create_connection()
        c = conn.cursor()
        c.execute("SELECT actor_id, direction FROM traffic_light_metadata")
        meta = {r["actor_id"]: r["direction"] for r in c.fetchall()}
        conn.close()
        
        lights = []
        for tl in tl_actors:
            direction = meta.get(tl.id)
            loc = tl.get_transform().location
            base_url = f"http://{ip}:5000/traffic_light/{tl.id}"
            lights.append({
                "id": tl.id,
                "direction": direction,
                "x": round(loc.x, 1),
                "y": round(loc.y, 1),
                "base_url": base_url,
                "links": {
                    "red": f"{base_url}/set/red",
                    "yellow": f"{base_url}/set/yellow",
                    "green": f"{base_url}/set/green"
                }
            })

        def get_sort_key(tl):
            d = (tl.get("direction") or "").upper()
            if d == "N": return 0
            if d == "S": return 1
            if d == "E": return 2
            if d == "W": return 3
            return 99

        lights.sort(key=get_sort_key)

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Traffic Light API Hub</title>
    <style>
        :root {{
            --bg: #0a0b10;
            --card-bg: rgba(255, 255, 255, 0.03);
            --accent: #ffca28;
            --text: #e0e0e0;
            --border: rgba(255, 255, 255, 0.1);
            --red: #ff4444;
            --yellow: #ffbb33;
            --green: #00c851;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .container {{ max-width: 900px; width: 100%; }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        h1 {{ color: var(--accent); font-size: 1.5rem; text-transform: uppercase; letter-spacing: 2px; }}
        .ip-badge {{
            background: rgba(255, 202, 40, 0.1);
            color: var(--accent);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            border: 1px solid var(--accent);
        }}
        .tl-list {{ display: flex; flex-direction: column; gap: 15px; }}
        .tl-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 20px;
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        .tl-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
        }}
        .tl-name {{ font-weight: bold; color: #fff; font-size: 1.1rem; }}
        .tl-meta {{ font-size: 0.75rem; color: rgba(255,255,255,0.4); }}
        .links-row {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }}
        .link-item {{
            background: rgba(0,0,0,0.3);
            padding: 10px;
            border-radius: 6px;
            display: flex;
            flex-direction: column;
            gap: 5px;
            border: 1px solid var(--border);
        }}
        .link-label {{ font-size: 0.65rem; text-transform: uppercase; font-weight: bold; }}
        .link-url {{
            font-family: monospace;
            font-size: 0.8rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: #00d4ff;
            cursor: pointer;
        }}
        .copy-btn {{
            background: var(--border);
            color: #fff;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.6rem;
            cursor: pointer;
            text-transform: uppercase;
        }}
        .copy-btn.red {{ border-left: 3px solid var(--red); }}
        .copy-btn.yellow {{ border-left: 3px solid var(--yellow); }}
        .copy-btn.green {{ border-left: 3px solid var(--green); }}
        .copy-btn:hover {{ background: rgba(255,255,255,0.1); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Traffic Light API Hub</h1>
            <div class="ip-badge">SERVER IP: {ip}</div>
        </div>
        <div class="tl-list">
            {"".join([f'''
            <div class="tl-card">
                <div class="tl-header">
                    <div>
                        <span class="tl-name">{"[" + (t["direction"] or "?") + "] "} Traffic Light #{t["id"]}</span>
                        <div class="tl-meta">Pos: {t["x"]}, {t["y"]}</div>
                    </div>
                    <span style="font-size: 1.5rem; color: var(--accent);">🚦</span>
                </div>
                <div class="links-row">
                    <div class="link-item" style="grid-column: span 3; margin-bottom: 5px;">
                        <span class="link-label">Base API URL</span>
                        <div class="link-url" onclick="copyText('{t["base_url"]}', this)">{t["base_url"]}</div>
                    </div>
                    <div class="link-item">
                        <span class="link-label" style="color:var(--red)">Red</span>
                        <button class="copy-btn red" onclick="copyText('{t["links"]["red"]}', this)">Copy</button>
                    </div>
                    <div class="link-item">
                        <span class="link-label" style="color:var(--yellow)">Yellow</span>
                        <button class="copy-btn yellow" onclick="copyText('{t["links"]["yellow"]}', this)">Copy</button>
                    </div>
                    <div class="link-item">
                        <span class="link-label" style="color:var(--green)">Green</span>
                        <button class="copy-btn green" onclick="copyText('{t["links"]["green"]}', this)">Copy</button>
                    </div>
                </div>
            </div>
            ''' for t in lights])}
        </div>
    </div>
    <script>
        function copyText(text, el) {{
            navigator.clipboard.writeText(text).then(() => {{
                const original = el.innerText || el.textContent;
                if (el.tagName === 'BUTTON') {{
                    el.innerText = 'COPIED!';
                    setTimeout(() => el.innerText = original, 1000);
                }} else {{
                    const btn = el.nextElementSibling;
                    const oldBtnText = btn.innerText;
                    btn.innerText = 'COPIED!';
                    setTimeout(() => btn.innerText = oldBtnText, 1000);
                }}
            }});
        }}
    </script>
</body>
</html>
        """
        return html
    except Exception as e:
        return f"Error: {str(e)}", 500
