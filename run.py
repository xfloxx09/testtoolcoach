from app import create_app, db
from sqlalchemy import inspect, text
from app.models import Project, User, Team, Workshop, Coaching, TeamMember

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    conn = db.engine.connect()

    # 1. Prüfen und Hinzufügen von coachings.team_id
    columns_coachings = [col['name'] for col in inspector.get_columns('coachings')]
    if 'team_id' not in columns_coachings:
        print("⚠️ Spalte 'team_id' in coachings fehlt – wird hinzugefügt...")
        conn.execute(text('ALTER TABLE coachings ADD COLUMN team_id INTEGER REFERENCES teams(id)'))
        conn.commit()
        print("✅ Spalte 'team_id' in coachings hinzugefügt.")
    else:
        print("✅ Spalte 'team_id' in coachings existiert bereits.")

    # 2. Für bestehende Coachings die team_id nachtragen (falls NULL)
    #    Wir setzen team_id = TeamMember.team_id des zugehörigen Mitglieds
    conn.execute(text('''
        UPDATE coachings
        SET team_id = team_members.team_id
        FROM team_members
        WHERE coachings.team_member_id = team_members.id
        AND coachings.team_id IS NULL
    '''))
    conn.commit()
    print("ℹ️ Bestehende Coachings mit team_id aktualisiert.")

    # 3. Prüfen und Hinzufügen von workshop_participants.original_team_id
    #    Da workshop_participants eine Tabelle ist, müssen wir prüfen, ob die Spalte existiert
    #    Wir können nicht einfach inspector.get_columns für eine Tabelle aufrufen, die vielleicht nicht existiert.
    #    Besser: Prüfen, ob die Tabelle existiert, und dann die Spalte.
    if 'workshop_participants' in inspector.get_table_names():
        columns_wp = [col['name'] for col in inspector.get_columns('workshop_participants')]
        if 'original_team_id' not in columns_wp:
            print("⚠️ Spalte 'original_team_id' in workshop_participants fehlt – wird hinzugefügt...")
            conn.execute(text('ALTER TABLE workshop_participants ADD COLUMN original_team_id INTEGER REFERENCES teams(id)'))
            conn.commit()
            print("✅ Spalte 'original_team_id' in workshop_participants hinzugefügt.")
        else:
            print("✅ Spalte 'original_team_id' in workshop_participants existiert bereits.")

        # Bestehende Einträge aktualisieren
        conn.execute(text('''
            UPDATE workshop_participants
            SET original_team_id = team_members.team_id
            FROM team_members
            WHERE workshop_participants.team_member_id = team_members.id
            AND workshop_participants.original_team_id IS NULL
        '''))
        conn.commit()
        print("ℹ️ Bestehende Workshop-Teilnehmer mit original_team_id aktualisiert.")
    else:
        print("✅ Tabelle 'workshop_participants' existiert noch nicht, später automatisch.")

    # 4. Sicherstellen, dass NOT NULL nicht gesetzt wird, da es NULL bleiben kann für alte Einträge
    #    Wir belassen es bei nullable=True, um Altdaten nicht zu blockieren.

    print("✅ Migration für historische Team-Zuordnung abgeschlossen.")

if __name__ == "__main__":
    app.run()
