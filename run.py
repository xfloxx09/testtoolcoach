from app import create_app, db
from sqlalchemy import inspect, text
from app.models import Project, User, Team, Workshop, Coaching

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    conn = db.engine.connect()

    # 1. Tabelle 'projects' anlegen, falls nicht vorhanden
    if 'projects' not in inspector.get_table_names():
        print("⚠️ Tabelle 'projects' fehlt – wird jetzt erstellt...")
        db.create_all()  # erstellt alle fehlenden Tabellen (inkl. projects)
        print("✅ Tabelle 'projects' erstellt.")
    else:
        print("✅ Tabelle 'projects' existiert bereits.")

    # 2. Prüfen, ob Spalte 'project_id' in 'users' existiert – wenn nicht, hinzufügen
    def column_exists(table, column):
        return column in [col['name'] for col in inspector.get_columns(table)]

    tables_to_update = [
        ('users', 'project_id', 'INTEGER REFERENCES projects(id)'),
        ('teams', 'project_id', 'INTEGER REFERENCES projects(id)'),
        ('workshops', 'project_id', 'INTEGER REFERENCES projects(id)'),
        ('coachings', 'project_id', 'INTEGER REFERENCES projects(id)')
    ]

    for table, col, col_def in tables_to_update:
        if not column_exists(table, col):
            print(f"⚠️ Spalte '{col}' in Tabelle '{table}' fehlt – wird hinzugefügt...")
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {col} {col_def}'))
            conn.commit()
            print(f"✅ Spalte '{col}' in '{table}' hinzugefügt.")
        else:
            print(f"✅ Spalte '{col}' in '{table}' existiert bereits.")

    # 3. Default-Projekt "GK-Mobilfunk" sicherstellen (ID 1)
    default_project = Project.query.filter_by(name='GK-Mobilfunk').first()
    if not default_project:
        print("⚠️ Default-Projekt 'GK-Mobilfunk' fehlt – wird erstellt...")
        default_project = Project(name='GK-Mobilfunk', description='Standard-Projekt für bestehende Daten')
        db.session.add(default_project)
        db.session.commit()
        print("✅ Default-Projekt 'GK-Mobilfunk' mit ID 1 erstellt.")
    else:
        print("✅ Default-Projekt 'GK-Mobilfunk' existiert bereits.")

    # 4. Bestehende Datensätze mit dem Default-Projekt verknüpfen (falls NULL)
    #    Wir setzen project_id = 1 für alle Zeilen, die noch NULL haben.
    for table in ['users', 'teams', 'workshops', 'coachings']:
        if column_exists(table, 'project_id'):
            result = conn.execute(text(f'UPDATE "{table}" SET project_id = 1 WHERE project_id IS NULL'))
            if result.rowcount > 0:
                print(f"ℹ️ {result.rowcount} Zeilen in '{table}' mit Projekt 1 verknüpft.")
            conn.commit()

    # 5. Sicherstellen, dass 'project_id' jetzt NOT NULL ist (falls nicht bereits)
    #    Wir ändern die Spalte auf NOT NULL, wenn noch NULL-Werte existieren (sollten keine mehr).
    for table in ['users', 'teams', 'workshops', 'coachings']:
        if column_exists(table, 'project_id'):
            # Prüfen, ob noch NULL vorkommen
            null_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}" WHERE project_id IS NULL')).scalar()
            if null_count == 0:
                # Spalte auf NOT NULL setzen
                try:
                    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN project_id SET NOT NULL'))
                    conn.commit()
                    print(f"✅ Spalte 'project_id' in '{table}' auf NOT NULL gesetzt.")
                except Exception as e:
                    print(f"⚠️ Konnte NOT NULL nicht setzen in '{table}': {e}")
            else:
                print(f"⚠️ In '{table}' gibt es noch {null_count} NULL-Werte – bitte manuell prüfen.")

    print("✅ Migration für Multi-Projekt abgeschlossen.")

if __name__ == "__main__":
    app.run()
