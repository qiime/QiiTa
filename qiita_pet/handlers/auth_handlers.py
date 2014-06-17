#!/usr/bin/env python

from tornado.escape import url_escape, json_encode

from qiita_pet.handlers.base_handlers import BaseHandler
from qiita_core.util import send_email
from qiita_core.exceptions import IncorrectPasswordError, IncorrectEmailError
from qiita_db.user import User
from qiita_db.exceptions import QiitaDBUnknownIDError
# login code modified from https://gist.github.com/guillaumevincent/4771570


class AuthCreateHandler(BaseHandler):
    """User Creation"""
    def get(self):
        try:
            error_message = self.get_argument("error")
        # Tornado can raise an Exception directly, not a defined type
        except Exception:
            error_message = ""
        self.render("create_user.html", user=self.get_current_user(),
                    error=error_message)

    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("pass", "")
        info = {}
        for info_column in ("name", "affiliation", "address", "phone"):
            hold = self.get_argument(info_column, None)
            if hold:
                info[info_column] = hold

        created, msg = User.create(username, password, info)

        if created:
            send_email(username, "FORGE: Verify Email Address", "Please click "
                       "the following link to verify email address: "
                       "http://forge-dev.colorado.edu/auth/verify/%s" % msg)
            self.redirect(u"/")
        else:
            error_msg = u"?error=" + url_escape(msg)
            self.redirect(u"/auth/create/" + error_msg)


class AuthVerifyHandler(BaseHandler):
    def get(self):
        email = self.get_argument("email")
        code = self.get_argument("code")
        try:
            User(email).status = 3
            msg = "Successfully verified user!"
        except QiitaDBUnknownIDError:
            msg = "Code not valid!"

        self.render("user_verified.html", user=None, error=msg)


class AuthLoginHandler(BaseHandler):
    """user login, no page necessary"""
    def post(self):
        username = self.get_argument("username", "")
        passwd = self.get_argument("password", "")
        # check the user status
        try:
            if User(username).status == 4:  # 4 is id for unverified
                # email not verified so dont log in
                msg = "Email not verified"
        except QiitaDBUnknownIDError:
            msg = "Unknown user"

        # Check the login information
        login = None
        try:
            login = User.login(username, passwd)
        except IncorrectEmailError:
            msg = "Unknown user"
        except IncorrectPasswordError:
            msg = "Incorrect password"

        if login:
            # everthing good so log in
            self.set_current_user(username)
            self.redirect("/")
            return
        self.render("index.html", user=None, loginerror=msg)

    def set_current_user(self, user):
        if user:
            self.set_secure_cookie("user", json_encode(user))
        else:
            self.clear_cookie("user")


class AuthLogoutHandler(BaseHandler):
    """Logout handler, no page necessary"""
    def get(self):
        self.clear_cookie("user")
        self.redirect("/")
