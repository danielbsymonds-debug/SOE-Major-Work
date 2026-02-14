from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from Extensions import db
from Database import User, Resource, Employee, Roster, Event
from datetime import datetime
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

        # Create admin user if not exists
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", is_admin=True)
            admin.set_password("Admin123!")
            db.session.add(admin)
            db.session.commit()

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

    # ---------------- ROSTERS ----------------

    @app.route('/rosters')
    @login_required
    def rosters():
        return render_template('rosters.html', rosters=Roster.query.all(), employees=Employee.query.all())

    @app.route('/employees')
    @login_required
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
                               resources=Resource.query.all())

    @app.route('/events/new', methods=['POST'])
    @login_required
    @admin_required
    def new_event():
        e = Event(
            title=request.form['title'],
            location=request.form['location'],
            start_time=datetime.strptime(request.form['start_time'], "%Y-%m-%dT%H:%M"),
            end_time=datetime.strptime(request.form['end_time'], "%Y-%m-%dT%H:%M")
        )

        for emp_id in request.form.getlist('employee_ids'):
            e.employees.append(Employee.query.get(int(emp_id)))

        for res_id in request.form.getlist('resource_ids'):
            e.resources.append(Resource.query.get(int(res_id)))

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