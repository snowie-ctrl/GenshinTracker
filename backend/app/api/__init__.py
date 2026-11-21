from app.api import characters, dashboard, img, planner, settings, sync, wishes

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, planner.router, wishes.router,
           img.router]
