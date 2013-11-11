"""APIRequestHandler subclasses for API endpoints."""

from lxml import html
from tornado.web import HTTPError
import requests
import pbkdf2

from feedreader.api_request_handler import APIRequestHandler
from feedreader.database.models import Feed, User
from feedreader.stub import generate_slipsum_entry


class MainHandler(APIRequestHandler):

    def get(self):
        with self.get_db_session() as session:
            username = self.require_auth(session)
            self.write({"message": "Hello, {}.".format(username)})


class UsersHandler(APIRequestHandler):

    def post(self):
        """Create a new user."""
        body = self.require_body_schema({
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["username", "password"],
        })

        with self.get_db_session() as session:
            # check if username already exists
            if session.query(User).get(body["username"]) is not None:
                raise HTTPError(400, reason="Username already registered")
            # save new user
            password_hash = pbkdf2.crypt(body["password"])
            new_user = User(body["username"], password_hash)
            session.add(new_user)
        self.set_status(201)


class FeedsHandler(APIRequestHandler):

    def get(self):
        feeds = []
        with self.get_db_session() as session:
            self.require_auth(session)
            for feed in session.query(Feed).all():
                feeds.append({
                    'id': feed.id,
                    'name': feed.title,
                    'url': feed.site_url,
                    'unreads': 1337,
                })
        self.write({'feeds': feeds})
        self.set_status(200)

    def post(self):
        body = self.require_body_schema({
            'type': 'object',
            'properties': {
                'url': {'type': 'string'},
            },
            'required': ['url'],
        })
        with self.get_db_session() as session:
            self.require_auth(session)
            dom = html.fromstring(requests.get(body['url']).content)
            title = dom.cssselect('title')[0].text_content()
            session.add(Feed(title, body['url'], body['url']))
        self.set_status(201)


class EntriesHandler(APIRequestHandler):

    def get(self, dirty_entry_ids):
        with self.get_db_session() as session:
            self.require_auth(session)
        entries = [generate_slipsum_entry() for _ in
                   dirty_entry_ids.split(',')]
        self.write({'entries': entries})
        self.set_status(200)
