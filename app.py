from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from Extensions import db
from Database import User, Resource, Employee, Roster, Event, ResourcePreset
from datetime import datetime
from sqlalchemy.exc import OperationalError
from functools import wraps

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rostering.db'
    app.config['SECRET_KEY'] = 'change-me'

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()
        # Ensure certain columns exist in SQLite DB (helpful when evolving schema without migrations)
        def ensure_column(table, column, add_sql):
            try:
                res = db.session.execute(f"PRAGMA table_info('{table}')").fetchall()
                existing = [r[1] for r in res]
                if column not in existing:
                    db.session.execute(add_sql)
                    db.session.commit()
            except Exception:
                db.session.rollback()

        # Add user.employee_id, event.setup_minutes, event.packup_minutes if missing
        ensure_column('user', 'employee_id', "ALTER TABLE user ADD COLUMN employee_id INTEGER")
        ensure_column('event', 'setup_minutes', "ALTER TABLE event ADD COLUMN setup_minutes INTEGER DEFAULT 0")
        ensure_column('event', 'packup_minutes', "ALTER TABLE event ADD COLUMN packup_minutes INTEGER DEFAULT 0")

        # Create admin user if not exists; if schema is out of sync, raise error (do NOT drop data)
        try:
            if not User.query.filter_by(username="admin").first():
                admin = User(username="admin", is_admin=True)
                admin.set_password("Admin123!")
                db.session.add(admin)
                db.session.commit()
        except OperationalError as e:
            # Do NOT drop tables or recreate DB. Instead, raise a clear error.
            raise RuntimeError("Database schema is out of sync with models. Please run a migration or add missing columns manually. No data was deleted.") from e

    # ---------------- LOGIN ----------------

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            user = User.query.filter_by(username=request.form['username']).first()
            if user and user.check_password(request.form['password']):
                login_user(user)
                return redirect(url_for('index'))
            flash("Invalid credentials")
        return render_template('login.html')

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            if User.query.filter_by(username=request.form['username']).first():
                flash("Username already exists")
                return redirect(url_for('signup'))

            user = User(username=request.form['username'])
            user.set_password(request.form['password'])
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.")
            return redirect(url_for('login'))

        return render_template('signup.html')

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('login'))

    # ---------------- DASHBOARD ----------------

    @app.route('/')
    @login_required
    def index():
        events = Event.query.all()
        resources = Resource.query.all()
        employees = Employee.query.all()
        return render_template('index.html', events=events, resources=resources, employees=employees)

    @app.route('/users')
    @login_required
    @admin_required
    def users():
        return render_template('users.html', users=User.query.all())

    # ---------------- RESOURCES ----------------

    @app.route('/resources')
    @login_required
    def resources():
        return render_template('resources.html', resources=Resource.query.all())

    @app.route('/resources/<int:resource_id>')
    @login_required
    def resource_detail(resource_id):
        resource = Resource.query.get_or_404(resource_id)
        return render_template('resource_detail.html', resource=resource)

    @app.route('/resources/new', methods=['POST'])
    @login_required
    @admin_required
    def new_resource():
        item_code = (request.form.get('item_code') or '').strip()

        # log raw form for debugging
        try:
            app.logger.info('new_resource form data: %s', dict(request.form))
        except Exception:
            pass

        # basic required validation
        if not item_code:
            flash('Item code is required.')
            return redirect(url_for('resources'))

        # Check if resource with this item_code already exists
        existing_resource = Resource.query.filter_by(item_code=item_code).first()
        if existing_resource:
            flash(f"A resource with item code '{item_code}' already exists. Please use a different item code or edit the existing resource.")
            return redirect(url_for('resources'))

        # parse optional/numeric fields safely
        try:
            qty = int(request.form.get('qty') or 1)
        except ValueError:
            qty = 1

        lifespan_raw = request.form.get('lifespan_years')
        try:
            lifespan = int(lifespan_raw) if lifespan_raw and lifespan_raw.strip() != '' else None
        except ValueError:
            lifespan = None

        dom = request.form.get('dom')
        try:
            dom_date = datetime.strptime(dom, "%Y-%m-%d").date() if dom and dom.strip() != '' else None
        except Exception:
            dom_date = None

        r = Resource(
            item_code=item_code,
            category=(request.form.get('category') or '').strip(),
            type=(request.form.get('type') or '').strip(),
            description=(request.form.get('description') or '').strip(),
            qty=qty,
            asset_number=(request.form.get('asset_number') or '').strip(),
            dom=dom_date,
            lifespan_years=lifespan
        )
        db.session.add(r)
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            # handle unique constraint or other DB errors gracefully
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc, IntegrityError) or (hasattr(exc, '__cause__') and isinstance(exc.__cause__, IntegrityError)):
                flash(f"A database error occurred while creating resource '{item_code}': duplicate or constraint violation.")
            else:
                flash(f"An error occurred while creating resource: {str(exc)}")
            return redirect(url_for('resources'))

        flash(f"Resource '{item_code}' has been added successfully.")
        return redirect(url_for('resource_detail', resource_id=r.id))

    @app.route('/resources/<int:resource_id>/edit', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def edit_resource(resource_id):
        resource = Resource.query.get_or_404(resource_id)
        if request.method == 'GET':
            return render_template('resource_edit.html', resource=resource)

        # POST: update fields
        item_code = (request.form.get('item_code') or '').strip()
        if not item_code:
            flash('Item code is required.')
            return redirect(url_for('edit_resource', resource_id=resource.id))

        # ensure uniqueness excluding current resource
        existing = Resource.query.filter(Resource.item_code == item_code, Resource.id != resource.id).first()
        if existing:
            flash(f"Another resource with item code '{item_code}' already exists.")
            return redirect(url_for('edit_resource', resource_id=resource.id))

        resource.item_code = item_code
        resource.category = (request.form.get('category') or '').strip()
        resource.type = (request.form.get('type') or '').strip()
        resource.description = (request.form.get('description') or '').strip()
        try:
            resource.qty = int(request.form.get('qty') or resource.qty or 1)
        except ValueError:
            resource.qty = resource.qty or 1
        resource.asset_number = (request.form.get('asset_number') or '').strip()
        dom = request.form.get('dom')
        try:
            resource.dom = datetime.strptime(dom, "%Y-%m-%d").date() if dom and dom.strip() != '' else None
        except Exception:
            pass
        try:
            lifespan = request.form.get('lifespan_years')
            resource.lifespan_years = int(lifespan) if lifespan and lifespan.strip() != '' else None
        except ValueError:
            pass

        db.session.commit()
        flash(f"Resource '{resource.item_code}' updated.")
        return redirect(url_for('resource_detail', resource_id=resource.id))

    @app.route('/resources/<int:resource_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def delete_resource(resource_id):
        resource = Resource.query.get_or_404(resource_id)
        db.session.delete(resource)
        db.session.commit()
        flash(f"Resource '{resource.item_code}' deleted.")
        return redirect(url_for('resources'))

    # ---------------- ROSTERS ----------------

    @app.route('/rosters')
    @login_required
    def rosters():
        if current_user.is_admin:
            rosters_q = Roster.query.all()
            employees_q = Employee.query.all()
        else:
            # non-admins only see rosters where they are the appointed employee
            if getattr(current_user, 'employee', None):
                emp = current_user.employee
                rosters_q = Roster.query.filter_by(employee_id=emp.id).all()
                employees_q = [emp]
            else:
                rosters_q = []
                employees_q = []
        return render_template('rosters.html', rosters=rosters_q, employees=employees_q)

    @app.route('/employees')
    @login_required
    @admin_required
    def employees_overview():
        return render_template('employees_overview.html', employees=Employee.query.all())

    @app.route('/employees/<int:employee_id>')
    @login_required
    def employee_detail(employee_id):
        employee = Employee.query.get_or_404(employee_id)
        return render_template('employee_detail.html', employee=employee)

    @app.route('/employees/<int:employee_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def delete_employee(employee_id):
        employee = Employee.query.get_or_404(employee_id)
        db.session.delete(employee)
        db.session.commit()
        return redirect(url_for('employees_overview'))

    @app.route('/employees/new', methods=['POST'])
    @login_required
    @admin_required
    def new_employee():
        emp = Employee(
            name=request.form['name'],
            age=int(request.form['age']) if request.form.get('age') else None,
            experience_years=int(request.form.get('experience_years') or 0),
            level_of_training=request.form.get('level_of_training'),
            training_status=request.form.get('training_status') or 'Not Trained'
        )
        db.session.add(emp)
        db.session.commit()
        return redirect(url_for('employees_overview'))

    @app.route('/rosters/new', methods=['POST'])
    @login_required
    @admin_required
    def new_roster():
        r = Roster(
            date=datetime.strptime(request.form['date'], "%Y-%m-%d").date(),
            shift_name=request.form['shift_name'],
            employee_id=int(request.form['employee_id']),
            job_description=request.form['job_description']
        )
        db.session.add(r)
        db.session.commit()
        return redirect(url_for('rosters'))

    # ---------------- EVENTS ----------------

    @app.route('/events')
    @login_required
    def events():
        return render_template('events.html',
                               events=Event.query.all(),
                               employees=Employee.query.all(),
                               resources=Resource.query.all(),
                               presets=ResourcePreset.query.all())

    @app.route('/events/new', methods=['POST'])
    @login_required
    @admin_required
    def new_event():
        # parse setup/packup (minutes) and event times
        try:
            setup_minutes = int(request.form.get('setup_minutes') or 0)
        except ValueError:
            setup_minutes = 0
        try:
            packup_minutes = int(request.form.get('packup_minutes') or 0)
        except ValueError:
            packup_minutes = 0

        e = Event(
            title=request.form['title'],
            location=request.form['location'],
            setup_minutes=setup_minutes,
            packup_minutes=packup_minutes,
            start_time=datetime.strptime(request.form['start_time'], "%Y-%m-%dT%H:%M"),
            end_time=datetime.strptime(request.form['end_time'], "%Y-%m-%dT%H:%M")
        )

        # employees (same as before)
        for emp_id in request.form.getlist('employee_ids'):
            emp = Employee.query.get(int(emp_id))
            if emp and emp not in e.employees:
                e.employees.append(emp)

        # if a preset was selected, add its resources first
        preset_id = request.form.get('preset_id')
        if preset_id:
            try:
                preset = ResourcePreset.query.get(int(preset_id))
            except Exception:
                preset = None
            if preset:
                for r in preset.resources:
                    if r not in e.resources:
                        e.resources.append(r)

        # explicit resource selections (also supports additions/removals from UI)
        for res_id in request.form.getlist('resource_ids'):
            try:
                r = Resource.query.get(int(res_id))
            except Exception:
                r = None
            if r and r not in e.resources:
                e.resources.append(r)

        db.session.add(e)
        db.session.commit()
        return redirect(url_for('events'))

    @app.route('/events/<int:event_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def delete_event(event_id):
        event = Event.query.get_or_404(event_id)
        db.session.delete(event)
        db.session.commit()
        return redirect(url_for('events'))

    # ---------------- PRESETS ----------------

    @app.route('/presets/new', methods=['POST'])
    @login_required
    @admin_required
    def new_preset():
        name = (request.form.get('name') or '').strip()
        if not name:
            flash('Preset name is required.')
            return redirect(url_for('events'))
        if ResourcePreset.query.filter_by(name=name).first():
            flash('A preset with that name already exists.')
            return redirect(url_for('events'))
        p = ResourcePreset(name=name, description=(request.form.get('description') or '').strip())
        for res_id in request.form.getlist('resource_ids'):
            r = Resource.query.get(int(res_id))
            if r:
                p.resources.append(r)
        db.session.add(p)
        db.session.commit()
        flash(f"Preset '{p.name}' created.")
        return redirect(url_for('events'))

    @app.route('/presets/<int:preset_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def delete_preset(preset_id):
        p = ResourcePreset.query.get_or_404(preset_id)
        db.session.delete(p)
        db.session.commit()
        flash(f"Preset '{p.name}' deleted.")
        return redirect(url_for('events'))

    # ---------- USER MANAGEMENT ----------

    @app.route('/users/<int:user_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def delete_user(user_id):
        if user_id == current_user.id:
            flash("You cannot delete your own account.")
            return redirect(url_for('users'))
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.username} has been deleted.")
        return redirect(url_for('users'))

    @app.route('/users/<int:user_id>/promote', methods=['POST'])
    @login_required
    @admin_required
    def promote_user(user_id):
        user = User.query.get_or_404(user_id)
        if user.is_admin:
            flash(f"{user.username} is already an administrator.")
        else:
            user.is_admin = True
            db.session.commit()
            flash(f"{user.username} has been promoted to Administrator.")
        return redirect(url_for('users'))

    @app.route('/users/<int:user_id>/demote', methods=['POST'])
    @login_required
    @admin_required
    def demote_user(user_id):
        user = User.query.get_or_404(user_id)
        if not user.is_admin:
            flash(f"{user.username} is not an administrator.")
        else:
            user.is_admin = False
            db.session.commit()
            flash(f"{user.username} has been demoted from Administrator.")
        return redirect(url_for('users'))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)