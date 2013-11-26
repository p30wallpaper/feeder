"""Main entry point for API server."""

import tornado.ioloop
import tornado.web
from tornado import gen
import sys
import pbkdf2
from datetime import timedelta

from feedreader.celery_poller import CeleryPoller
from feedreader.database import models
from feedreader import handlers
from feedreader.tasks.core import Tasks
from feedreader.updater import Updater


def get_application(db_setup_f=None, enable_dummy_data=False,
                    periodic_updates=False):
    """Return Tornado application instance."""
    # initialize the DB so sessions can be created
    create_session = models.initialize_db()

    if db_setup_f is not None:
        db_setup_f(create_session)

    # XXX create test user
    session = create_session()
    user = models.User("username", pbkdf2.crypt("password"))
    if not session.query(models.User).filter(
            models.User.username == user.username
            ).count():
        session.add(user)
        session.commit()


    # TODO: make this configurable
    tasks = Tasks(debug=True)

    celery_poller = CeleryPoller(timedelta(milliseconds=5))

    if enable_dummy_data:
        # add some test feeds
        # don't any anything that we aren't ok with hammering with requests
        TEST_FEEDS = [
            "http://feeds.feedburner.com/Tombuntu",
            "https://mtomwing.com/blog/feed",
            "http://awesome-blog.github.io/atom.xml",
        ]
        for url in TEST_FEEDS:
            @gen.coroutine
            def add_feed():
                # This fails for MySQL once the test data has been added before
                try:
                    yield handlers.FeedsHandler.subscribe_feed(
                        session, user, celery_poller, tasks, url
                    )
                # Ignore exceptions for now
                except:
                    pass
            tornado.ioloop.IOLoop.instance().run_sync(add_feed)

    session.commit()
    session.close()

    CHECK_UPDATE_PERIOD = timedelta(seconds=1)
    UPDATE_PERIOD = timedelta(seconds=5)
    if periodic_updates:
        # create updater and attach to IOLoop
        updater = Updater(UPDATE_PERIOD)
        periodic_callback = tornado.ioloop.PeriodicCallback(
            updater.do_updates, CHECK_UPDATE_PERIOD.total_seconds() * 1000
        )
        periodic_callback.start()

    # create tornado application and listen on the provided port
    default_injections = dict(
        create_session=create_session,
        enable_dummy_data=enable_dummy_data,
        tasks=tasks,
        celery_poller=celery_poller,
    )
    return tornado.web.Application([
        (r"^/?$", handlers.MainHandler, default_injections),
        (r"^/users/?$", handlers.UsersHandler, default_injections),
        (r'^/feeds/?$', handlers.FeedsHandler, default_injections),
        (r'^/feeds/(?P<feed_id>[0-9]+)$', handlers.FeedHandler,
         default_injections),
        (r'^/feeds/(?P<feed_id>[0-9]+)/entries/?$', handlers.FeedEntriesHandler,
         default_injections),
        (r'^/entries/(?P<entry_ids>(?:\d+,)*\d+)$', handlers.EntriesHandler,
         default_injections),
    ])


def main():
    """Main entry point for the server."""
    port = int(sys.argv[1])
    get_application(enable_dummy_data=True).listen(port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
