from app.api import artifacts, characters, dashboard, events, good, img, maps, planner, profile, settings, sync, teams, traveler, wishes

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, planner.router, wishes.router,
           teams.router, events.router, profile.router, maps.router, good.router, img.router,
           traveler.router, artifacts.router]
