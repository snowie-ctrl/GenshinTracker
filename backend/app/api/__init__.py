from app.api import characters, dashboard, events, img, maps, planner, profile, settings, sync, teams, wishes

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, planner.router, wishes.router,
           teams.router, events.router, profile.router, maps.router, img.router]
