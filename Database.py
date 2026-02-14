from Extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    qty = db.Column(db.Integer, default=1)
    asset_number = db.Column(db.String(120))
    dom = db.Column(db.Date)  # Date of Manufacture
    lifespan_years = db.Column(db.Integer)


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer)
    experience_years = db.Column(db.Integer)
    level_of_training = db.Column(db.String(120))
    training_status = db.Column(db.String(120))


class Roster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    shift_name = db.Column(db.String(120), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    job_description = db.Column(db.String(255))

    employee = db.relationship("Employee")


event_employee = db.Table(
    'event_employee',
    db.Column('event_id', db.Integer, db.ForeignKey('event.id')),
    db.Column('employee_id', db.Integer, db.ForeignKey('employee.id'))
)

event_resource = db.Table(
    'event_resource',
    db.Column('event_id', db.Integer, db.ForeignKey('event.id')),
    db.Column('resource_id', db.Integer, db.ForeignKey('resource.id'))
)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    location = db.Column(db.String(200))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    employees = db.relationship("Employee", secondary=event_employee)
    resources = db.relationship("Resource", secondary=event_resource)