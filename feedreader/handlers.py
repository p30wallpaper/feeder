"""APIRequestHandler subclasses for API endpoints."""

from tornado.web import HTTPError, asynchronous
from tornado import gen
import pbkdf2
import tcelery

from feedreader.api_request_handler import APIRequestHandler
from feedreader.database.models import (Entry, Feed, Subscription, User,
                                        Read, and_, exists_feed)
from feedreader.stub import generate_dummy_feed


# tornado-celery magic, not sure what this does
tcelery.setup_nonblocking_producer()


class MainHandler(APIRequestHandler):

    def get(self):
        """Return a hello world message."""
        with self.get_db_session() as session:
            username = self.require_auth(session)
            self.write({"message": "Hello, {}.".format(username)})


class UsersHandler(APIRequestHandler):

    def get(self):
        """Return information about the current user."""
        with self.get_db_session() as session:
            user = session.query(User).get(self.require_auth(session))
            username = user.username
        self.write({'username': username})
        self.set_status(200)

    def post(self):
        """Create a new user."""
        body = self.require_body_schema({
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "pattern": "^[^:\s]*$",
                    "maxLength": 32,
                    "minLength": 1
                },
                "password": {
                    "type": "string",
                    "minLength": 1
                },
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
            session.commit()

            # XXX: Create some dummy feeds for the new user
            if self.enable_dummy_data:
                for _ in xrange(10):
                    generate_dummy_feed(session, new_user.username)
        self.set_status(201)


class FeedsHandler(APIRequestHandler):

    def get(self):
        """Return a list of the user's subscribed feeds."""
        feeds = []
        with self.get_db_session() as session:
            user = session.query(User).get(self.require_auth(session))
            for feed in user.get_feeds(session):
                feeds.append({
                    'id': feed.id,
                    'name': feed.title,
                    'url': feed.site_url,
                    'unreads': user.num_unread_in_feed(session, feed.id),
                })
        self.write({'feeds': feeds})
        self.set_status(200)

    @asynchronous
    @gen.coroutine
    def post(self):
        """Subscribe the user to a new feed."""
        body = self.require_body_schema({
            'type': 'object',
            'properties': {
                'url': {'type': 'string'},
            },
            'required': ['url'],
        })
        with self.get_db_session() as session:
            user = session.query(User).get(self.require_auth(session))

            # verify this feed has not already been added
            feed = session.query(Feed)\
                .filter(Feed.feed_url == body['url']).first()

            # if the feed has not been added, add it
            if feed is None:
                # TODO: we're just assuming this succeeds
                res = yield gen.Task(self.tasks.fetch_feed, body["url"])
                session.add(res["feed"])
                session.commit()  # needed to get the feed's ID
                for entry in res["entries"]:
                    entry.feed_id = res["feed"].id
                session.add_all(res["entries"])
                feed = res["feed"]

            # Check to see if the user already has a subscription to this feed
            if not user.is_sub_of_feed(session, int(feed.id)):
                session.add(Subscription(user.username, feed.id))
            else:
                raise HTTPError(400, reason="Already to subscribed to feed")
        # TODO: we should indicate the ID of the new feed (location header?)
        self.set_status(201)


class FeedHandler(APIRequestHandler):

    def get(self, feed_id):
        """Return metadata for a subscribed feed."""
        with self.get_db_session() as session:
            user = session.query(User).get(self.require_auth(session))
            feed = session.query(Feed).get(int(feed_id))

            # Make sure the feed exists
            if feed is None:
                raise HTTPError(404, reason='This feed does not exist')

            subscription = session.query(Subscription).get((user.username,
                                                            feed.id))
            # Make sure the user is subscribed to this feed
            if subscription is None:
                raise HTTPError(404, reason='This feed does not exist')

            self.write({
                'id': feed.id,
                'name': feed.title,
                'url': feed.site_url,
                'unreads': user.num_unread_in_feed(session, feed.id),
            })
        self.set_status(200)

    def delete(self, feed_id):
        with self.get_db_session() as session:
            user = session.query(User).get(self.require_auth(session))
            if not exists_feed(session, feed_id):
                raise HTTPError(404, reason='This feed does not exist')
            feed = session.query(Feed).get(feed_id)
            if not user.is_sub_of_feed(session, feed_id):
                raise HTTPError(404, reason='This feed does not exist')
            user.unsubscribe(session, feed.id)
            feed.remove(session)
        self.set_status(204)


class FeedEntriesHandler(APIRequestHandler):

    def get(self, feed_id):
        """Return a list of entry IDs for a feed."""
        with self.get_db_session() as session:
            entry_filter = self.get_argument("filter", None)
            user = session.query(User).get(self.require_auth(session))
            # check if the feed exists and user is subscribed to it
            if user.is_sub_of_feed(session, int(feed_id)):
                if entry_filter == "read" or entry_filter == "unread":
                    entries = user.get_feed_entries(
                        session, feed_id, filter=entry_filter)
                elif entry_filter is None:
                    entries = user.get_feed_entries(session, feed_id)
                else:
                    self.set_status(400)
                    return
                entry_ids = [entry.id for entry in entries]
                self.write({'entries': entry_ids})
                self.set_status(200)
            else:
                self.set_status(404)


class EntriesHandler(APIRequestHandler):

    def get(self, entry_ids):
        entry_ids = [int(entry_id) for entry_id in entry_ids.split(",")]
        with self.get_db_session() as session:
            user = self.require_auth(session)
            # TODO: check that the user has permission to see each entry_id
            entries = [session.query(Entry).get(entry_id) for entry_id in
                       entry_ids]
            # if any of the entries do not exist, return 404
            if None in entries:
                raise HTTPError(404, "Entry does not exist.")
            entries_json = [
                {
                    "id": entry.id,
                    "title": entry.title,
                    "pub-date": entry.date,
                    "status": entry.been_read(session, user),
                    "author": entry.author,
                    "feed_id": entry.feed_id,
                    "url": entry.url,
                    "content": entry.content,
                } for entry in entries
            ]
            self.write({'entries': entries_json})
            self.set_status(200)

    def patch(self, entry_ids):
        body = self.require_body_schema({
            "type": "object",
            "properties": {
                "status": {"type": "string"},
            },
            "required": ["status"],
        })
        if body["status"] not in ["read", "unread"]:
            raise HTTPError(400, "That is not a valid status")
        entry_ids = [int(entry_id) for entry_id in entry_ids.split(",")]
        with self.get_db_session() as session:
            user = session.query(User).get(self.require_auth(session))
            entries = session.query(Entry).filter(
                Entry.id.in_(entry_ids)
            ).all()
            if entries == []:
                raise HTTPError(404, "Those entry ids do not exist")
            for entry in entries:
                if not user.is_sub_of_feed(session, entry.feed_id):
                    raise HTTPError(403,
                            "You do not have access to one of these entries"
                                    )
            read_ids = user.get_read_ids(session)
            if body["status"] == "read":
                for entry in entries:
                    if not entry.id in read_ids:
                        update = Read(user.username, entry.id)
                        session.add(update)
            if body["status"] == "unread":
                for entry in entries:
                    if entry.id in read_ids:
                        update = session.query(Read).filter(and_(
                            Read.username == user.username,
                            Read.entry_id == entry.id
                        )).one()
                        session.delete(update)
            self.set_status(200)
