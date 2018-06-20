"""
Plugins are responsible for fetching and parsing the stats from the service
being profiled.

"""
available = {
    'apache_httpd': 'graphite_plugin_agent.plugins.apache_httpd.ApacheHTTPD',
    'couchdb': 'graphite_plugin_agent.plugins.couchdb.CouchDB',
    'edgecast': 'graphite_plugin_agent.plugins.edgecast.Edgecast',
    'elasticsearch':
        'graphite_plugin_agent.plugins.elasticsearch.ElasticSearch',
    'haproxy': 'graphite_plugin_agent.plugins.haproxy.HAProxy',
    'memcached': 'graphite_plugin_agent.plugins.memcached.Memcached',
    'mongodb': 'graphite_plugin_agent.plugins.mongodb.MongoDB',
    'nginx': 'graphite_plugin_agent.plugins.nginx.Nginx',
    'pgbouncer': 'graphite_plugin_agent.plugins.pgbouncer.PgBouncer',
    'php_apc': 'graphite_plugin_agent.plugins.php_apc.APC',
    'php_fpm': 'graphite_plugin_agent.plugins.php_fpm.FPM',
    'postgresql': 'graphite_plugin_agent.plugins.postgresql.PostgreSQL',
    'rabbitmq': 'graphite_plugin_agent.plugins.rabbitmq.RabbitMQ',
    'redis': 'graphite_plugin_agent.plugins.redis.Redis',
    'riak': 'graphite_plugin_agent.plugins.riak.Riak',
    'uwsgi': 'graphite_plugin_agent.plugins.uwsgi.uWSGI'}
