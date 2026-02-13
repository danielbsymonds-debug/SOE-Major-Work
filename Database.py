from datetime import datetime
from Extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(120), unique=True, nullable=False)
    expiration_date = db.Column(db.Date, nullable=True)
    perishable = db.Column(db.Boolean, default=False)
    condition = db.Column(db.String(120), default="Good")
    in_use = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Resource {self.serial_number}>"

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    experience_years = db.Column(db.Integer, default=0)
    level_of_training = db.Column(db.String(120), nullable=False)
    training_status = db.Column(db.String(120), default="Not Trained")

    def __repr__(self):
        return f"<Employee {self.name}>"

event_employee = db.Table(
    'event_employee',
    db.Column('event_id', db.Integer, db.ForeignKey('event.id'), primary_key=True),
    db.Column('employee_id', db.Integer, db.ForeignKey('employee.id'), primary_key=True)
)

event_resource = db.Table(
    'event_resource',
    db.Column('event_id', db.Integer, db.ForeignKey('event.id'), primary_key=True),
    db.Column('resource_id', db.Integer, db.ForeignKey('resource.id'), primary_key=True)
)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employees = db.relationship('Employee', secondary=event_employee, backref='events')
    resources = db.relationship('Resource', secondary=event_resource, backref='events')

    def __repr__(self):
        return f"<Event {self.title}>"

class Roster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    shift_name = db.Column(db.String(120), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    job_description = db.Column(db.String(200), nullable=True)

    employee = db.relationship('Employee', backref='rosters')

    def __repr__(self):
        return f"<Roster {self.date} {self.shift_name}>"
    
class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)