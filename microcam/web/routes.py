"""Flaskページルート"""

from __future__ import annotations

from flask import Blueprint, Response, render_template

pages = Blueprint("pages", __name__)

# app.pyからセットされる参照
_app_ref = None


def init_routes(app_ref) -> None:
    global _app_ref
    _app_ref = app_ref


@pages.route("/")
def index():
    return live()


@pages.route("/live")
def live():
    return render_template("live.html")


@pages.route("/video_feed")
def video_feed():
    from ..streaming import generate_mjpeg

    return Response(
        generate_mjpeg(_app_ref.camera, _app_ref.config.camera.fps),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@pages.route("/recordings")
def recordings():
    return render_template("recordings.html")


@pages.route("/settings")
def settings():
    return render_template("settings.html")
