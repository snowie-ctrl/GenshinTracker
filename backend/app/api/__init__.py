from app.api import characters, dashboard, img, settings, sync

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, img.router]
