from app import create_app, db
from sqlalchemy import inspect

app = create_app()

# --- Automatische Tabellenerstellung für team_leaders (falls fehlend) ---
with app.app_context():
    inspector = inspect(db.engine)
    if 'team_leaders' not in inspector.get_table_names():
        print("⚠️ Tabelle 'team_leaders' fehlt – wird jetzt erstellt...")
        db.create_all()  # Erstellt alle fehlenden Tabellen (inkl. team_leaders)
        print("✅ Tabelle 'team_leaders' erfolgreich erstellt.")
    else:
        print("✅ Tabelle 'team_leaders' existiert bereits.")
# ---------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
