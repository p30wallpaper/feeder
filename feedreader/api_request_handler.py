from contextlib import contextmanager
import base64
import httplib
import json
import jsonschema
import tornado.web
import pbkdf2

from feedreader import database


class APIRequestHandler(tornado.web.RequestHandler):
    """Base RequestHandler for use by API endpoints."""

    def initialize(self, create_session, tasks, celery_poller,
                   enable_dummy_data=False):
        self.create_session = create_session
        self.tasks = tasks
        self.celery_poller = celery_poller
        self.enable_dummy_data = enable_dummy_data

        self.use_www_authenticate = True

    def require_auth(self, session):
        """Return the authorized user's username.

        If authorization fails, raise HTTPError. This doesn't attempt to
        gracefully handle invalid authentication headers.

        HTTP basic auth is used. If the auth method is xBasic, no
        WWW-Authenticate header will be sent for failed authentication
        attempts, as a workaround for using the API via JavaScript.

        Furthermore, doing authentication in this way will protect us from
        general CSRF attacks. The user's browser will not automatically include
        our auth header in arbitrary requests to our API, even when the user is
        logged in due to our usage of xBasic.
        """
        try:
            auth_header = self.request.headers.get("Authorization")
            if auth_header is None:
                raise ValueError("No Authorization header provided")
            auth_type, auth_digest = auth_header.split(" ", 1)
            user, passwd = base64.decodestring(auth_digest).split(":", 1)
            if auth_type not in ["Basic", "xBasic"]:
                raise ValueError("Authorization type is not Basic")
            self.use_www_authenticate = auth_type == "Basic"
            user_model = session.query(database.User).get(user)
            if user_model is None:
                raise ValueError("Invalid username or password")
            passwd_hash = user_model.password_hash
            if pbkdf2.crypt(passwd, passwd_hash) != passwd_hash:
                raise ValueError("Invalid username or password")
        except ValueError as e:
            msg = "Authorization failed: {}".format(e)
            raise tornado.web.HTTPError(401, msg)
        else:
            return user

    def require_body_schema(self, schema):
        """Return json body of the request.

        Raises 400 if the body does not match the given schema.
        """
        try:
            body_json = json.loads(self.request.body)
            jsonschema.validate(body_json, schema)
            return body_json
        except jsonschema.ValidationError as e:
            reason = "Body input validation failed: {}".format(e.message)
            raise tornado.web.HTTPError(400, reason=reason)

    def write_error(self, status_code, **kwargs):
        #if unauthorized, tell client that authorization is required
        if status_code == 401 and self.use_www_authenticate:
            self.set_header('WWW-Authenticate', 'Basic realm=Restricted')

        # use generic error message, or reason if provided
        message = httplib.responses[status_code]
        if "exc_info" in kwargs:
            e = kwargs["exc_info"][1]
            reason = e.reason if hasattr(e, "reason") else None
            if reason is not None:
                message = reason

        # return errors in JSON
        self.finish({
            "error": {
                "code": status_code,
                "message": message,
            }
        })

    @contextmanager
    def get_db_session(self):
        """Return SQLAlchemy session context manager.

        Commit or rollback is handled authmatically when the context manager
        exits.

        Example:
        with self.get_session() as session:
            session.add(blah)
        """
        session = self.create_session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()
