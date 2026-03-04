# app/admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc, or_
from app import db
from app.models import User, Team, TeamMember, Coaching
from app.forms import RegistrationForm, TeamForm, TeamMemberForm, CoachingForm
from app.utils import role_required, ROLE_ADMIN, ROLE_TEAMLEITER, get_or_create_archiv_team, ARCHIV_TEAM_NAME
from app.main_routes import calculate_date_range, get_month_name_german
from datetime import datetime, timezone

bp = Blueprint('admin', __name__)

@bp.route('/')
@login_required
@role_required(ROLE_ADMIN)
def panel():
    users = User.query.order_by(User.username).all()
    teams = Team.query.filter(Team.name != ARCHIV_TEAM_NAME).order_by(Team.name).all()
    team_members = TeamMember.query.order_by(TeamMember.name).all()
    archiv_team = Team.query.filter_by(name=ARCHIV_TEAM_NAME).first()
    archived_members = archiv_team.members.all() if archiv_team else []
    return render_template('admin/admin_panel.html', title='Admin Panel',
                           users=users, teams=teams, team_members=team_members,
                           archived_members=archived_members,
                           config=current_app.config)

# --- User Management ---
@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required(ROLE_ADMIN)
def create_user():
    form = RegistrationForm()
    # form.team_ids.choices werden bereits im __init__ gesetzt
    if form.validate_on_submit():
        try:
            user = User(
                username=form.username.data,
                email=form.email.data if form.email.data else None,
                role=form.role.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()  # um user.id zu erhalten

            # Team-Zuordnungen für Teamleiter
            if user.role == ROLE_TEAMLEITER and form.team_ids.data:
                selected_teams = Team.query.filter(Team.id.in_(form.team_ids.data)).all()
                user.teams_led = selected_teams  # ersetzt die Beziehung
            else:
                user.teams_led = []

            db.session.commit()
            flash('Benutzer erfolgreich erstellt!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"FEHLER beim Erstellen des Benutzers: {str(e)}")
            flash(f'Fehler beim Erstellen des Benutzers: {str(e)}', 'danger')
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Fehler im Feld '{form[field].label.text if hasattr(form[field], 'label') else field}': {error}", 'danger')
    return render_template('admin/create_user.html', title='Benutzer erstellen', form=form, config=current_app.config)

@bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required(ROLE_ADMIN)
def edit_user(user_id):
    user_to_edit = User.query.get_or_404(user_id)
    form = RegistrationForm(obj=user_to_edit, original_username=user_to_edit.username)

    if not form.password.data:
        form.password.validators = []
        form.password2.validators = []

    if form.validate_on_submit():
        try:
            user_to_edit.username = form.username.data
            user_to_edit.email = form.email.data if form.email.data else None
            user_to_edit.role = form.role.data

            if form.password.data:
                user_to_edit.set_password(form.password.data)

            # Team-Zuordnungen aktualisieren
            if user_to_edit.role == ROLE_TEAMLEITER and form.team_ids.data:
                selected_teams = Team.query.filter(Team.id.in_(form.team_ids.data)).all()
                user_to_edit.teams_led = selected_teams
            else:
                user_to_edit.teams_led = []

            db.session.commit()
            flash('Benutzer erfolgreich aktualisiert!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"FEHLER beim Aktualisieren des Benutzers: {str(e)}")
            flash(f'Fehler beim Aktualisieren des Benutzers: {str(e)}', 'danger')
    elif request.method == 'GET':
        form.username.data = user_to_edit.username
        form.email.data = user_to_edit.email
        form.role.data = user_to_edit.role
        # Vorauswahl der Teams setzen
        form.team_ids.data = [team.id for team in user_to_edit.teams_led.all()]
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Fehler im Feld '{form[field].label.text if hasattr(form[field], 'label') else field}': {error}", 'danger')

    return render_template('admin/edit_user.html', title='Benutzer bearbeiten', form=form, user=user_to_edit, config=current_app.config)

@bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required(ROLE_ADMIN)
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.username == 'admin' or user.id == current_user.id:
        flash('Dieser Benutzer kann nicht gelöscht werden.', 'danger')
        return redirect(url_for('admin.panel'))

    try:
        # Beziehung zu Teams auflösen (wird wegen ondelete=CASCADE automatisch gelöscht, aber zur Sicherheit)
        user.teams_led = []
        Coaching.query.filter_by(coach_id=user_id).update({"coach_id": None})
        db.session.delete(user)
        db.session.commit()
        flash('Benutzer gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fehler beim Löschen von User ID {user_id}: {e}")
        flash(f'Fehler beim Löschen des Benutzers. Es könnten noch verbundene Daten existieren (z.B. Coachings). Details im Log.', 'danger')
    return redirect(url_for('admin.panel'))

# --- Team Management ---
@bp.route('/teams/create', methods=['GET', 'POST'])
@login_required
@role_required(ROLE_ADMIN)
def create_team():
    form = TeamForm()
    if form.validate_on_submit():
        if form.name.data.strip().upper() == ARCHIV_TEAM_NAME:
            flash(f'Der Teamname "{ARCHIV_TEAM_NAME}" ist für das System reserviert.', 'danger')
            return render_template('admin/create_team.html', title='Team erstellen', form=form, config=current_app.config)
        try:
            team = Team(name=form.name.data)
            db.session.add(team)
            db.session.flush()

            # Teamleiter zuordnen
            if form.team_leaders.data:
                leaders = User.query.filter(User.id.in_(form.team_leaders.data), User.role == ROLE_TEAMLEITER).all()
                team.leaders = leaders
            else:
                team.leaders = []

            db.session.commit()
            flash('Team erfolgreich erstellt!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Fehler beim Erstellen des Teams: {e}")
            flash(f'Fehler beim Erstellen des Teams: {str(e)}', 'danger')
    return render_template('admin/create_team.html', title='Team erstellen', form=form, config=current_app.config)

@bp.route('/teams/edit/<int:team_id>', methods=['GET', 'POST'])
@login_required
@role_required(ROLE_ADMIN)
def edit_team(team_id):
    team_to_edit = Team.query.get_or_404(team_id)
    form = TeamForm(obj=team_to_edit, original_name=team_to_edit.name)

    if team_to_edit.name == ARCHIV_TEAM_NAME and request.method == 'GET':
        flash('Das ARCHIV-Team kann nicht bearbeitet werden.', 'info')
        form.name.render_kw = {'readonly': True}
        form.team_leaders.render_kw = {'disabled': True}

    if form.validate_on_submit():
        if team_to_edit.name == ARCHIV_TEAM_NAME:
            flash('Das ARCHIV-Team kann nicht geändert werden.', 'danger')
            return redirect(url_for('admin.edit_team', team_id=team_id))

        try:
            team_to_edit.name = form.name.data

            # Teamleiter aktualisieren
            if form.team_leaders.data:
                leaders = User.query.filter(User.id.in_(form.team_leaders.data), User.role == ROLE_TEAMLEITER).all()
                team_to_edit.leaders = leaders
            else:
                team_to_edit.leaders = []

            db.session.commit()
            flash('Team erfolgreich aktualisiert!', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Fehler beim Bearbeiten des Teams {team_id}: {e}")
            flash(f'Fehler beim Bearbeiten des Teams: {str(e)}', 'danger')

    elif request.method == 'GET':
        form.name.data = team_to_edit.name
        # Vorauswahl der Teamleiter setzen
        form.team_leaders.data = [leader.id for leader in team_to_edit.leaders.all()]

    return render_template('admin/edit_team.html', title='Team bearbeiten', form=form, team=team_to_edit, config=current_app.config)

@bp.route('/teams/delete/<int:team_id>', methods=['POST'])
@login_required
@role_required(ROLE_ADMIN)
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    if team.name == ARCHIV_TEAM_NAME:
        flash('Das ARCHIV-Team kann nicht gelöscht werden.', 'danger')
        return redirect(url_for('admin.panel'))
    if team.members.count() > 0:
        flash('Team kann nicht gelöscht werden, da ihm noch Mitglieder zugeordnet sind. Verschieben Sie die Mitglieder zuerst ins Archiv.', 'danger')
        return redirect(url_for('admin.panel'))

    try:
        # Beziehung zu Teamleitern auflösen (wird durch ondelete=CASCADE automatisch gelöscht)
        team.leaders = []
        db.session.delete(team)
        db.session.commit()
        flash('Team gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fehler beim Löschen von Team ID {team_id}: {e}")
        flash('Fehler beim Löschen des Teams.', 'danger')
    return redirect(url_for('admin.panel'))

# --- Team Member Management (unverändert) ---
@bp.route('/teammembers/create', methods=['GET', 'POST'])
@login_required
@role_required(ROLE_ADMIN)
def create_team_member():
    form = TeamMemberForm()
    # ... (bleibt wie gehabt, keine Änderung)
    # (hier aus Platzgründen nicht vollständig, aber in der echten Datei bleibt der Originalcode erhalten)
    # Bitte den Originalcode aus deiner bestehenden Datei für create_team_member, edit_team_member, move_to_archiv übernehmen.
    # Da diese Funktionen keine Teamleiter betreffen, sind sie unverändert.
    # Ich empfehle, den Rest der Datei (ab hier) aus deinem Original zu belassen.
    # Wichtig: Die Funktionen create_team_member, edit_team_member, move_to_archiv, manage_coachings, edit_coaching_entry, delete_coaching_entry bleiben unverändert.
    # Stelle sicher, dass du sie nicht überschreibst.
    pass
