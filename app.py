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

    # ---------------- RESOURCES ----------------

    @app.route('/resources')
    @login_required
    def resources():
        return render_template('resources.html', resources=Resource.query.all())

    @app.route('/resources/new', methods=['POST'])
    @login_required
    @admin_required
    def new_resource():
        dom = request.form.get('dom')
        dom_date = datetime.strptime(dom, "%Y-%m-%d").date() if dom else None

        r = Resource(
            item_code=request.form['item_code'],
            category=request.form['category'],
            type=request.form['type'],
            description=request.form['description'],
            qty=int(request.form['qty']),
            asset_number=request.form['asset_number'],
            dom=dom_date,
            lifespan_years=int(request.form['lifespan_years'])
        )
        db.session.add(r)
        db.session.commit()
        return redirect(url_for('resources'))

    # ---------------- ROSTERS ----------------

    @app.route('/rosters')
    @login_required
    def rosters():
        return render_template('rosters.html', rosters=Roster.query.all(), employees=Employee.query.all())

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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)