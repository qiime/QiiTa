#!/usr/bin/env python

from tornado.escape import url_escape, json_encode
from tornado.web import HTTPError

from moi import r_client

from qiita_pet.handlers.base_handlers import BaseHandler
from qiita_core.qiita_settings import qiita_config
from qiita_core.util import send_email
from qiita_core.exceptions import (IncorrectPasswordError, IncorrectEmailError,
                                   UnverifiedEmailError)
from qiita_db.user import User
from qiita_db.exceptions import QiitaDBUnknownIDError, QiitaDBDuplicateError
# login code modified from https://gist.github.com/guillaumevincent/4771570


class AuthCreateHandler(BaseHandler):
    """User Creation"""
    def get(self):
        try:
            error_message = self.get_argument("error")
        # Tornado can raise an Exception directly, not a defined type
        except:
            error_message = ""
        self.render("create_user.html", error=error_message)

    def post(self):
        username = self.get_argument("email", "").strip().lower()
        password = self.get_argument("newpass", "")
        info = {}
        for info_column in ("name", "affiliation", "address", "phone"):
            hold = self.get_argument(info_column, None)
            if hold:
                info[info_column] = hold

        created = False
        try:
            created = User.create(username, password, info)
        except QiitaDBDuplicateError:
            msg = "Email already registered as a user"

        if created:
            info = created.info
            try:
                send_email(username, "QIITA: Verify Email Address", "Please "
                           "click the following link to verify email address: "
                           "%s/auth/verify/%s?email=%s"
                           % (qiita_config.base_url, info['user_verify_code'],
                              url_escape(username)))
            except:
                msg = ("Unable to send verification email. Please contact the "
                       "qiita developers at <a href='mailto:qiita-help"
                       "@gmail.com'>qiita-help@gmail.com</a>")
                error_msg = u"?error=" + url_escape(msg)
                self.redirect(u"/?level=danger&message=" + error_msg)
                return
            self.redirect(u"/")
        else:
            error_msg = u"?error=" + url_escape(msg)
            self.redirect(u"/auth/create/" + error_msg)


class AuthVerifyHandler(BaseHandler):
    def get(self, code):
        email = self.get_argument("email").strip().lower()
        if User.verify_code(email, code, "create"):
            msg = "Successfully verified user! You are now free to log in."
        else:
            msg = "Code not valid!"
        self.render("user_verified.html", msg=msg)


class AuthLoginHandler(BaseHandler):
    """user login, no page necessary"""
    def get(self):
        self.redirect("/")

    def post(self):
        if r_client.get('maintenance') is not None:
            raise HTTPError(503, "Site is down for maintenance")

        username = self.get_argument("username", "").strip().lower()
        passwd = self.get_argument("password", "")
        nextpage = self.get_argument("next", None)
        if nextpage is None:
            if "auth/" not in self.request.headers['Referer']:
                nextpage = self.request.headers['Referer']
            else:
                nextpage = "/"

        msg = ""
        # check the user level
        try:
            if User(username).level == "unverified":
                # email not verified so dont log in
                msg = "Email not verified"
        except QiitaDBUnknownIDError:
            msg = "Unknown user"
        except RuntimeError:
            # means DB not available, so set maintenance mode and failover
            r_client.set("maintenance", "Database connection unavailable, "
                         "please try again later.")
            self.redirect("/")
            return

        # Check the login information
        login = None
        try:
            login = User.login(username, passwd)
        except IncorrectEmailError:
            msg = "Unknown user"
        except IncorrectPasswordError:
            msg = "Incorrect password"
        except UnverifiedEmailError:
            msg = "You have not verified your email address"

        if login:
            # everything good so log in
            self.set_current_user(username)
            self.redirect(nextpage)
        else:
            self.render("index.html", message=msg, level='danger')

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
