def register_blueprints(app):
    from .engagements import bp as engagements_bp
    from .meta import bp as meta_bp
    from .runs import bp as runs_bp
    from .static_serve import bp as static_bp

    app.register_blueprint(meta_bp, url_prefix="/api")
    app.register_blueprint(engagements_bp, url_prefix="/api")
    app.register_blueprint(runs_bp, url_prefix="/api")
    app.register_blueprint(static_bp)
