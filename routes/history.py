"""
routes/history.py
=================
DB-only routes: saved hosts, saved locations, camera setups.
Connection lifecycle (connect/disconnect/status) has been moved to routes/connection.py.
"""
from flask import Blueprint, request, jsonify
import json

from config.db import get_db

blueprint = Blueprint("history", __name__)


@blueprint.route("/history", methods=["GET"])
def get_history():
    try:
        with get_db() as conn:
            hosts = [{"host": r["host"], "port": r["port"]}
                     for r in conn.execute(
                         "SELECT host, port FROM hosts ORDER BY last_used DESC LIMIT 10"
                     ).fetchall()]

            locations = {r["name"]: {
                            "x": r["x"], "y": r["y"], "z": r["z"],
                            "pitch": r["pitch"], "yaw": r["yaw"], "roll": r["roll"]
                         }
                         for r in conn.execute(
                             "SELECT * FROM locations ORDER BY name"
                         ).fetchall()}

            camera_setups = [{"name": r["name"],
                               "config": json.loads(r["config"])}
                             for r in conn.execute(
                                 "SELECT name, config FROM camera_setups ORDER BY created_at DESC"
                             ).fetchall()]

            last_conn = conn.execute(
                "SELECT host, port FROM last_connection WHERE id = 1"
            ).fetchone()
            last = {"host": last_conn["host"], "port": last_conn["port"]} \
                   if last_conn else None

        return jsonify({
            "success": True,
            "hosts":         hosts,
            "locations":     locations,
            "camera_setups": camera_setups,
            "last_connection": last,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/history/host", methods=["POST"])
def save_host():
    try:
        d    = request.json or {}
        host = d.get("host")
        port = int(d.get("port", 2000))
        if not host:
            return jsonify({"success": False, "error": "No host"})
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO hosts (host, port, last_used) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (host, port))
            conn.execute(
                "INSERT OR REPLACE INTO last_connection (id, host, port) VALUES (1, ?, ?)",
                (host, port))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/history/location", methods=["POST"])
def save_location():
    try:
        d    = request.json or {}
        name = d.get("name")
        if not name:
            return jsonify({"success": False, "error": "No name"})
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO locations (name, x, y, z, pitch, yaw, roll) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name,
                 float(d.get("x",     0)),
                 float(d.get("y",     0)),
                 float(d.get("z",     0)),
                 float(d.get("pitch", 0)),
                 float(d.get("yaw",   0)),
                 float(d.get("roll",  0))))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@blueprint.route("/history/location", methods=["DELETE"])
def delete_location():
    try:
        d = request.json or {}
        name = d.get("name")
        if not name:
            return jsonify({"success": False, "error": "No name provided"})
        with get_db() as conn:
            conn.execute("DELETE FROM locations WHERE name = ?", (name,))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
