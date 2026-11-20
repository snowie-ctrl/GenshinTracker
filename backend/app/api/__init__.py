from app.api import characters, dashboard, img, planner, settings, sync

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, planner.router, img.router]
