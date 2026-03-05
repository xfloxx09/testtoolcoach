from app import create_app, db
from sqlalchemy import inspect

app = create_app()

# --- Automatische Tabellenerstellung für fehlende Tabellen ---
with app.app_context():
    inspector = inspect(db.engine)
    
    # Prüfe und erstelle team_leaders (falls fehlt)
    if 'team_leaders' not in inspector.get_table_names():
        print("⚠️ Tabelle 'team_leaders' fehlt – wird jetzt erstellt...")
        db.create_all()
        print("✅ Tabelle 'team_leaders' erfolgreich erstellt.")
    else:
        print("✅ Tabelle 'team_leaders' existiert bereits.")
    
    # Prüfe und erstelle workshops und workshop_participants (falls fehlen)
    if 'workshops' not in inspector.get_table_names():
        print("⚠️ Tabelle 'workshops' fehlt – wird jetzt erstellt...")
        db.create_all()  # erstellt auch workshop_participants automatisch mit
        print("✅ Tabellen für Workshops erfolgreich erstellt.")
    else:
        print("✅ Workshops-Tabellen existieren bereits.")
# ---------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
