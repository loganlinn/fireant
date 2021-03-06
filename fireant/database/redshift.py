from pypika import RedshiftQuery

from .postgresql import PostgreSQLDatabase


class RedshiftDatabase(PostgreSQLDatabase):
    """
    Redshift client that uses the psycopg module.
    """

    # The pypika query class to use for constructing queries
    query_cls = RedshiftQuery

    def __init__(self, host='localhost', port=5439, database=None,
                 user=None, password=None, **kwags):
        super(RedshiftDatabase, self).__init__(host, port, database, user, password, **kwags)
