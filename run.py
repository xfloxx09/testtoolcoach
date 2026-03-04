from app import create_app
from app import db
from sqlalchemy import inspect, Table, MetaData, Column, Integer, ForeignKey

app = create_app()

# --- Notfall-Migration: Erstelle team_leaders Tabelle, falls nicht vorhanden ---
with app.app_context():
    inspector = inspect(db.engine)
    if 'team_leaders' not in inspector.get_table_names():
        print("⚠️ Tabelle 'team_leaders' fehlt – wird jetzt erstellt...")
        metadata = MetaData()
        Table(
            'team_leaders', metadata,
            Column('team_id', Integer, ForeignKey('teams.id', ondelete='CASCADE'), primary_key=True),
            Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
        )
        metadata.create_all(db.engine)
        print("✅ Tabelle 'team_leaders' erfolgreich erstellt.")
    else:
        print("✅ Tabelle 'team_leaders' existiert bereits.")
# ---------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
