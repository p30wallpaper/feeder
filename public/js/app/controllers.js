(function(angular, _) {

  angular.module('feeder.controllers', [])

  /**
   * Routes the user to their home page.
   * Routes a visitor to the login page.
   *
   * @controller
   * @route '/'
   */
  .controller('IndexCtrl', function($location, User) {
    if (User.isLoggedIn()) {
      $location.path('/home');
    } else {
      $location.path('/login');
    }
  })

  /**
   * Displays a user's list of subscriptions.
   * Allows a user to add subscriptions.
   *
   * @controller
   * @route '/home'
   * @scope {Function} addFeed Adds a new feed.
   * @scope {String} newFeed The URL of the new feed to add.
   */
  .controller('HomeCtrl', function($scope, $location, User, Feeds) {
    if (!User.isLoggedIn()) {
      $location.path('/login');
    }

    function updateFeeds() {
      Feeds.get().then(function(feeds) {
        $scope.subscriptions = feeds;
      });
    }

    $scope.addFeed = function() {
      Feeds.add($scope.newFeed).then(function(feeds) {
        updateFeeds();
      });
    }

    updateFeeds();
  })

  /**
   * Displays a list of articles for a subscription.
   *
   * @controller
   * @route '/home/:feed'
   * @scope {Number} feedId The id of the current subscription.
   * @scope {Object} feed The data of the current subscription.
   */
  .controller('FeedCtrl', function($scope, $location, Feed, User, Articles) {
    if (!User.isLoggedIn()) {
      $location.path('/login');
    }

    $scope.feed = Feed;

    Articles.get(Feed.id).then(function(articles) {
      $scope.articles = articles;
    });
  })

  /**
   * Registers a new user.
   * Routes the user to their home page upon successful registration.
   *
   * @controller
   * @route '/register'
   */
  .controller('RegisterCtrl', function($scope, $location, $timeout, User) {
    var timeout;

    $scope.error = false;
    $scope.loading = false;

    $scope.register = function() {
      $timeout.cancel(timeout);

      $scope.loading = true;
      User.register($scope.username, $scope.password).then(function() {
        $location.path('/');
      }, function() {
        $scope.error = true;

        timeout = $timeout(function() {
          $scope.error = false;
        }, 200);
      }).then(function() {
        $scope.loading = false;
      });
    }
  })

  /**
   * Routes the user to their home page upon successful authentication.
   *
   * @controller
   * @route '/login'
   * @scope {Function} login Hits the authentication server on button click.
   * @scope {String} username Value of the username input field.
   * @scope {String} password Value of the password input field.
   * @scope {Boolean} error Error state of authentication.
   * @scope {Boolean} loading Loading state of authentication.
   */
  .controller('LoginCtrl', function($scope, $location, $timeout, User) {
    var timeout;

    $scope.error = false;
    $scope.loading = false;

    $scope.login = function() {
      $timeout.cancel(timeout);

      $scope.loading = true;
      User.login($scope.username, $scope.password).then(function() {
        $location.path('/');
      }, function() {
        $scope.error = true;

        timeout = $timeout(function() {
          $scope.error = false;
        }, 200);
      }).then(function() {
        $scope.loading = false;
      });
    }
  })

  .controller('LogoutCtrl', function($location, User) {
    User.logout();
    $location.path('/login');
  });

}).call(this, angular, _);
