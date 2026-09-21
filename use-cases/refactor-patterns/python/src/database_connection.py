# Database connection system using the Factory pattern.
#
# - `Connection`: common interface implemented by each database-specific class
# - `MySQLConnection`, `PostgreSQLConnection`, `MongoDBConnection`, `RedisConnection`:
#   concrete connection types, each owning its own connection-string rules
# - `DatabaseConnectionFactory`: central creation point; maps db_type -> class
# - `DatabaseConnection`: public facade that keeps the original API intact and
#   delegates creation to the factory (lazily, so unsupported types still raise
#   the original ValueError when connect() is called)


class Connection:
    """Common interface for all concrete database connections."""

    db_name = None
    label = None

    def __init__(self, host, port, username, password, database, **options):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.options = options
        self.connection = None

    def connect(self):
        print(f"Connecting to {self.db_name} database...")
        print(f"{self.label} Connection: {self.build_connection_string()}")
        print("Connection successful!")
        return self.connection

    def build_connection_string(self):
        raise NotImplementedError


class MySQLConnection(Connection):
    db_name = 'mysql'
    label = 'MySQL'

    def build_connection_string(self):
        connection_string = f"mysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        connection_string += f"?charset={self.options.get('charset', 'utf8')}"
        connection_string += f"&connectionTimeout={self.options.get('connection_timeout', 30)}"

        if self.options.get('use_ssl'):
            connection_string += "&useSSL=true"

        return connection_string


class PostgreSQLConnection(Connection):
    db_name = 'postgresql'
    label = 'PostgreSQL'

    def build_connection_string(self):
        connection_string = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

        if self.options.get('use_ssl'):
            connection_string += "?sslmode=require"

        return connection_string


class MongoDBConnection(Connection):
    db_name = 'mongodb'
    label = 'MongoDB'

    def build_connection_string(self):
        connection_string = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        connection_string += f"?retryAttempts={self.options.get('retry_attempts', 3)}"
        connection_string += f"&poolSize={self.options.get('pool_size', 5)}"

        if self.options.get('use_ssl'):
            connection_string += "&ssl=true"

        return connection_string


class RedisConnection(Connection):
    db_name = 'redis'
    label = 'Redis'

    def build_connection_string(self):
        return f"{self.host}:{self.port}/{self.database}"


class DatabaseConnectionFactory:
    """Creates the correct connection implementation for a database type."""

    _registry = {
        'mysql': MySQLConnection,
        'postgresql': PostgreSQLConnection,
        'mongodb': MongoDBConnection,
        'redis': RedisConnection,
    }

    @classmethod
    def register(cls, db_type, connection_class):
        """Register a new connection type without modifying existing code."""
        cls._registry[db_type] = connection_class

    @classmethod
    def create(cls, db_type, **config):
        connection_class = cls._registry.get(db_type)
        if connection_class is None:
            raise ValueError(f"Unsupported database type: {db_type}")
        return connection_class(**config)


class DatabaseConnection:
    """Public facade preserving the original DatabaseConnection API."""

    def __init__(self, db_type, host, port, username, password, database,
                 use_ssl=False, connection_timeout=30, retry_attempts=3,
                 pool_size=5, charset='utf8'):
        self.db_type = db_type
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.use_ssl = use_ssl
        self.connection_timeout = connection_timeout
        self.retry_attempts = retry_attempts
        self.pool_size = pool_size
        self.charset = charset
        self.connection = None
        self._implementation = None

    @property
    def _impl(self):
        if self._implementation is None:
            self._implementation = DatabaseConnectionFactory.create(
                self.db_type,
                host=self.host, port=self.port, username=self.username,
                password=self.password, database=self.database,
                use_ssl=self.use_ssl, connection_timeout=self.connection_timeout,
                retry_attempts=self.retry_attempts, pool_size=self.pool_size,
                charset=self.charset)
        return self._implementation

    def connect(self):
        self.connection = self._impl.connect()
        return self.connection


if __name__ == "__main__":
    # Example usage
    # Creating different database connections with various configurations
    mysql_db = DatabaseConnection(
        db_type='mysql',
        host='localhost',
        port=3306,
        username='db_user',
        password='password123',
        database='app_db',
        use_ssl=True
    )
    mysql_db.connect()

    mongo_db = DatabaseConnection(
        db_type='mongodb',
        host='mongodb.example.com',
        port=27017,
        username='mongo_user',
        password='mongo123',
        database='analytics',
        pool_size=10,
        retry_attempts=5
    )
    mongo_db.connect()