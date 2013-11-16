(function(angular) {

  angular.module('feeder.services', [])

  /**
   * Creates a `User` model.
   *
   * @factory
   * @var {Function} User `User` constructor.
   * @var {String} cookieKey The identifier for the user cookie.
   * @var {Function} genAuth Creates a base64 encoding of the username/password.
   */
  .factory('User', function($q, $cookieStore, Restangular) {
    var User = angular.noop
      , cookieKey = 'auth';

    function genAuth(username, password) {
      return btoa(username + ':' + password);
    }

    /**
     * Registers a new user.
     *
     * @param {String} username The new user's username.
     * @param {String} password The new user's password.
     * @returns {Promise} Returns the promise of the registration API hit.
     */
    function register(username, password) {
      return Restangular.all('users').post({
        username: username,
        password: password
      }).then(function(result) {
        $cookieStore.put(cookieKey, genAuth(username, password));
      }, $q.reject);
    }

    /**
     * Logs in a user by checking the server to see if the user exists and the
     * password matches.
     *
     * @param {String} username The user's username.
     * @param {String} password The user's password.
     * @returns {Promise} Returns the promise of the login API hit.
     */
    function login(username, password) {
      var auth = genAuth(username, password);

      Restangular = Restangular.withConfig(function(RestangularProvider) {
        RestangularProvider.setDefaultHeaders({
          Authorization: 'xBasic ' + auth
        });
      });

      return Restangular.one('users').get().then(function(result) {
        $cookieStore.put(cookieKey, auth);
      }, $q.reject);
    };

    /**
     * Logs out a user by deleting the session cookie.
     */
    function logout() {
      $cookieStore.remove(cookieKey);
    }

    /**
     * Checks to see if an user is logged in.
     *
     * @returns {Boolean} Returns whether or not a user is currently logged in.
     */
    function isLoggedIn() {
      return !!$cookieStore.get(cookieKey);
    }

    /**
     * Returns the current user's username by checking the server.
     *
     * @returns {Promise} Returns the promise of the API hit.
     */
    function getUsername() {
      Restangular = Restangular.withConfig(function(RestangularProvider) {
        RestangularProvider.setDefaultHeaders({
          Authorization: 'xBasic ' + $cookieStore.get(cookieKey)
        });
      });

      return Restangular.one('users').get().then(function(result) {
        return result.username;
      }, $q.reject);
    }

    function getAuth() {
      return $cookieStore.get(cookieKey);
    }

    return {
      getAuth: getAuth,
      genAuth: genAuth,
      getUsername: getUsername,
      isLoggedIn: isLoggedIn,
      login: login,
      logout: logout,
      register: register
    };
  })

  .factory('Articles', function($q, User, Article, Restangular) {
    var Articles = angular.noop;

    Restangular = Restangular.withConfig(function(RestangularProvider) {
      RestangularProvider.setDefaultHeaders({
        Authorization: 'xBasic ' + User.getAuth()
      });
    });

    function get(id) {
      if (!id) {
        return $q.reject();
      }

      return Restangular.one('feeds', id).getList('entries').then(function(result) {
        return Article.get(result.entries).then(function(result) {
          return result.entries;
        }, $q.reject);
      }, $q.reject);
    }

    return {
      get: get
    };
  })

  .factory('Article', function($q, User, Restangular) {
    var Articles = angular.noop;

    Restangular = Restangular.withConfig(function(RestangularProvider) {
      RestangularProvider.setDefaultHeaders({
        Authorization: 'xBasic ' + User.getAuth()
      });
    });

    function get(id) {
      if (!id) {
        return $q.reject();
      }

      return Restangular.one('entries').getList(id);
    }

    return {
      get: get
    };
  })

  /**
   * Creates a `User` model.
   *
   * @factory
   * @var {Function} User `User` constructor.
   * @var {String} cookieKey The identifier for the user cookie.
   * @var {Function} genAuth Creates a base64 encoding of the username/password.
   */
  .factory('Feeds', function($q, User, Restangular) {
    var Feeds = angular.noop;

    Restangular = Restangular.withConfig(function(RestangularProvider) {
      RestangularProvider.setDefaultHeaders({
        Authorization: 'xBasic ' + User.getAuth()
      });
    });

    function add(URL) {
      return Restangular.all('feeds').post({
        url: URL
      });
    }

    function get() {
      return Restangular.all('feeds').getList().then(function(result) {
        return result.feeds;
      }, $q.reject);
    }

    return {
      add: add,
      get: get
    };
  });

}).call(this, angular);
