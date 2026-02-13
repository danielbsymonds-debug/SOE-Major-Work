from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from Extensions import db
from Database import User, Resource, Employee, Event, Roster, Users
from datetime import datetime
from flask_login import login_required
from functools import wraps
from flask import abort



def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rostering.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'change-me'

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()
        # Create default admin if none exists
        if not User.query.first():
            admin = User(username="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()

    # -------------------------
    # LOGIN ROUTES
    # -------------------------

    def admin_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_admin:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return wrapper

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for('index'))
            flash("Invalid username or password")

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            # Check if username exists
            if User.query.filter_by(username=username).first():
                flash("Username already exists")
                return redirect(url_for('signup'))

            new_user = User(username=username)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            flash("Account created successfully. You can now log in.")
            return redirect(url_for('login'))

        return render_template('signup.html')

    # -------------------------
    # PROTECTED ROUTES
    # -------------------------

    @app.route('/')
    @login_required
    def index():
        upcoming_events = Event.query.order_by(Event.start_time.asc()).limit(5).all()
        available_resources = Resource.query.filter_by(in_use=False).all()
        employees = Employee.query.all()
        return render_template('index.html', events=upcoming_events, resources=available_resources, employees=employees)

    @app.route('/resources')
    @login_required
    @admin_required
    def resources():
        resources = Resource.query.all()
        return render_template('resources.html', resources=resources)

    @app.route('/resources/new', methods=['POST'])
    @login_required
    def new_resource():
        serial_number = request.form['serial_number']
        expiration_date = request.form.get('expiration_date') or None
        perishable = bool(request.form.get('perishable'))
        condition = request.form.get('condition', 'Good')
        in_use = bool(request.form.get('in_use'))

        exp_date_obj = None
        if expiration_date:
            exp_date_obj = datetime.strptime(expiration_date, '%Y-%m-%d').date()

        r = Resource(
            serial_number=serial_number,
            expiration_date=exp_date_obj,
            perishable=perishable,
            condition=condition,
            in_use=in_use
        )
        db.session.add(r)
        db.session.commit()
        return redirect(url_for('resources'))

    @app.route('/rosters')
    @login_required
    def rosters():
        rosters = Roster.query.order_by(Roster.date.desc()).all()
        employees = Employee.query.all()
        return render_template('rosters.html', rosters=rosters, employees=employees)

    @app.route('/employees/new', methods=['POST'])
    @login_required
    @admin_required
    def new_employee():
        name = request.form['name']
        age = int(request.form['age'])
        experience_years = int(request.form.get('experience_years', 0))
        level_of_training = request.form['level_of_training']
        training_status = request.form.get('training_status', 'Not Trained')

        e = Employee(
            name=name,
            age=age,
            experience_years=experience_years,
            level_of_training=level_of_training,
            training_status=training_status
        )
        db.session.add(e)
        db.session.commit()
        return redirect(url_for('rosters'))

    @app.route('/rosters/new', methods=['POST'])
    @login_required
    @admin_required
    def new_roster():
        date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        shift_name = request.form['shift_name']
        employee_id = int(request.form['employee_id'])
        job_description = request.form.get('job_description')

        r = Roster(
            date=date,
            shift_name=shift_name,
            employee_id=employee_id,
            job_description=job_description
        )
        db.session.add(r)
        db.session.commit()
        return redirect(url_for('rosters'))

    @app.route('/events')
    @login_required
    def events():
        events = Event.query.order_by(Event.start_time.desc()).all()
        employees = Employee.query.all()
        resources = Resource.query.all()
        return render_template('events.html', events=events, employees=employees, resources=resources)

    @app.route('/events/new', methods=['POST'])
    @login_required
    @admin_required
    def new_event():
        title = request.form['title']
        location = request.form['location']
        start_time = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')

        event = Event(title=title, location=location, start_time=start_time, end_time=end_time)

        employee_ids = request.form.getlist('employee_ids')
        resource_ids = request.form.getlist('resource_ids')

        for eid in employee_ids:
            emp = Employee.query.get(int(eid))
            if emp:
                event.employees.append(emp)

        for rid in resource_ids:
            res = Resource.query.get(int(rid))
            if res:
                event.resources.append(res)
                res.in_use = True

        db.session.add(event)
        db.session.commit()
        return redirect(url_for('events'))

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)