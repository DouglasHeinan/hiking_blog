"""
This file handles all user signup/login/logout activities of the application.
"""

from flask import Blueprint, render_template, redirect, flash, request, url_for, abort
from flask_login import login_required, logout_user, current_user, login_user
from flask_mail import Message
from functools import wraps
from hiking_blog.forms import SignUpForm, LoginForm, PasswordRecoveryForm, ChangePasswordForm, VerificationForm
from hiking_blog.login_manager import login_manager
from hiking_blog.db import db
from hiking_blog.models import User
from hiking_blog.mail import mail
from datetime import timedelta
import random
# from threading import Thread

CHARACTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
              'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O',
              'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
              '!', '#', '$', '%', '&', '*', '+']
PW_RESET_MESSAGE = "Here is your password reset code:"
DAYS_BEFORE_LOGOUT = timedelta(days=30)


auth_bp = Blueprint(
    "auth_bp", __name__
)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Allows the user to enter their username and password to login.

    If the user enters their username and password while already logged in, user is redirected to the home page.
    If username or password do not match entries in the database, screen is cleared and user is prompted to enter their
    info again. If username and password match an entry in the database, user is logged in and redirected to either the
    home page or whichever page they were originally destined for before being redirected.
    """

    if current_user.is_authenticated:
        flash("You are already logged in.")
        return redirect(url_for('home_bp.home'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            flash("That username does not exist. Please try again.")
            return redirect(url_for("auth_bp.login"))
        if not user.check_password(password=form.password.data):
            flash("Password incorrect. Please Try again.")
            return redirect(url_for("auth_bp.login"))
        login_user(user, remember=True, duration=DAYS_BEFORE_LOGOUT)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("home_bp.home"))
    return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


@auth_bp.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    """
    Allows a user without membership to the site to become a member.

    If the user enters a username that already exists in the application's database, redirects them to the login page.
    If the password doesn't match the verify_password data, the fields are cleared and the user is prompted to reenter
    their info. Otherwise, creates a new user object in the users table.
    """
    form = SignUpForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("You've already signed up!")
            return redirect(url_for("auth_bp.login"))
        if form.password.data != form.verify_password.data:
            flash("Passwords Must Match")
            return redirect(url_for("auth_bp.sign_up"))
        new_user = User(
            username=form.username.data,
            email=form.email.data
        )
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("home_bp.home"))
    return render_template("sign_up.html", form=form, logged_in=current_user.is_authenticated)


@auth_bp.route("/password_recovery", methods=["GET", "POST"])
def password_recovery():
    form = PasswordRecoveryForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            flash("That username has not yet been created.")
            return redirect(url_for("auth_bp.sign_up"))
        if current_user.is_authenticated:
            flash("You are already logged in.")
            return redirect(url_for("home_bp.home"))

        user_email = user.email
        password_code = password_reset_code_generator()
        msg = Message(
            recipients=[user_email]
        )
        msg.body = f"{PW_RESET_MESSAGE} {password_code}"
        mail.send(msg)
        print(msg.body)
        return redirect(url_for("auth_bp.change_password_verify", username=user.username, password_code=password_code))
    return render_template("password_recovery.html", form=form)


def password_reset_code_generator():
    """Generates a random 8 digit security code to verify the user during a password reset."""
    password_characters = [random.choice(CHARACTERS) for i in range(8)]
    random.shuffle(password_characters)
    password_verification = "".join(password_characters)
    return password_verification


@auth_bp.route("/change_password_verify", methods=["GET", "POST"])
def change_password_verify():
    password_code = request.args["password_code"]
    username = request.args["username"]
    user = User.query.filter_by(username=username).first()
    form = VerificationForm()
    if form.validate_on_submit():
        if form.verification_code.data != password_code:
            flash("That code is incorrect!")
            return redirect(url_for("auth_bp.change_password_verify", username=username, password_code=password_code))
        return redirect(url_for("auth_bp.change_password", username=user.username))
    return render_template("change_password_verify.html", form=form, user=user)


@auth_bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    username = request.args["username"]
    user = User.query.filter_by(username=username).first()
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if form.new_password.data != form.verify_password.data:
            flash("Passwords do not match!")
            return redirect(url_for("auth_bp.change_password", username=username))
        user.set_password(form.new_password.data)
        db.session.commit()
        return redirect(url_for("auth_bp.login"))
    return render_template("change_password.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    """Logs the user out and redirects them to the home page."""
    logout_user()
    return redirect(url_for("home_bp.home"))


@login_manager.user_loader
def load_user(user_id):
    """
    Tells flask-login how to load users given an id.

    Parameters
    ----------
    user_id : int
        The primary key from the users table in the database that corresponds to the current user.
    """

    if user_id is not None:
        return User.query.get(user_id)
    return None


@login_manager.unauthorized_handler
def unauthorized():
    """Flashes a message to a logged-out user attempting to access a page only viewable by logged-in users."""
    flash("You must be logged in to view that page")
    return redirect(url_for("auth_bp.login"))


def admin_only(f):
    """
    A wrapper for functions throughout this application that require a user be logged in before they run.

    Parameters
    ----------
    f : function()
        The function being wrapped by admin_only.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function
